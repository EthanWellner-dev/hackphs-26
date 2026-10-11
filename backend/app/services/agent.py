from __future__ import annotations

import hashlib
import json
import os
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar
from queue import Empty, Queue
from threading import BoundedSemaphore, Thread
import math

_T = TypeVar("_T")
_PROVIDER_SLOTS = BoundedSemaphore(4)


def bounded_provider_call(call: Callable[[], _T], timeout: float) -> _T:
    """Bound caller latency and abandoned provider work, including streamed audio."""
    if not _PROVIDER_SLOTS.acquire(blocking=False):
        raise TimeoutError("Provider capacity exhausted")
    result: Queue[tuple[bool, Any]] = Queue(maxsize=1)

    def run() -> None:
        try:
            result.put((True, call()))
        except Exception as exc:
            result.put((False, exc))
        finally:
            _PROVIDER_SLOTS.release()

    Thread(target=run, daemon=True).start()
    try:
        success, value = result.get(timeout=timeout)
    except Empty:
        raise TimeoutError("Provider deadline exceeded") from None
    if not success:
        raise value
    return value


def provider_timeout(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return min(15.0, max(0.1, value)) if math.isfinite(value) else default
    except ValueError:
        return default

try:
    from google import genai
except ImportError:  # The deterministic fallback must work without provider extras.
    genai = None  # type: ignore[assignment]

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.main import Scenario


CommandType = Literal[
    "UPDATE_RELEASE",
    "UPDATE_WEATHER",
    "TRIGGER_EVENT",
    "DEPLOY_UNIT",
    "ASSIGN_PROPERTY",
    "NO_OP",
]


class AgentCommand(BaseModel):
    commandType: CommandType
    value: str | None = None


class AgentDecision(BaseModel):
    assistantText: str = Field(min_length=1, max_length=500)
    commands: list[AgentCommand] = Field(default_factory=list, max_length=4)
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    clarifyingQuestions: list[str] = Field(default_factory=list, max_length=3)


@dataclass
class AgentResult:
    decision: AgentDecision
    provider: str


INTAKE_QUESTIONS = (
    ("hazard", "Do you know what substance or hazard was released? If unknown, say so and I will leave it unconfirmed."),
    ("release", "Is the release still active, or has it stopped? If unknown, I will keep the release active in the simulation."),
    ("weather", "Do you have a current wind speed or direction? If unknown, I will use the modeled weather and mark it as an assumption."),
    ("source", "Do you know the breach or source location? If unknown, I will use the incident location."),
)
_UNKNOWN_ANSWERS = ("don't know", "do not know", "unknown", "not sure", "unsure", "no idea", "cannot tell", "can't tell")


SYSTEM_INSTRUCTION = """You are Aero-Hazard's emergency operations dispatcher.
Return only JSON matching the supplied schema. Keep assistantText concise and operational.
LIVE means recently fetched provider model data, not a local observation. CACHED may be stale.
Never invent wind, population counts, concentrations, or precision beyond provider cadence.
When the operator reports wind direction, emit UPDATE_WEATHER value DIRECTION_<degrees>, meteorological direction FROM.
For release mass changes emit UPDATE_RELEASE value MASS_KG_<number>; for wind speed use INCREASE_WIND_1_MPS or DECREASE_WIND_1_MPS.
You may propose only UPDATE_RELEASE, UPDATE_WEATHER, TRIGGER_EVENT, DEPLOY_UNIT, ASSIGN_PROPERTY, or NO_OP.
When required incident details are missing, ask one concise clarifying question at a time.
An operator may answer that they do not know; accept that answer without guessing, state the provisional simulation assumption, and ask the next question. Never promise a conservative or guaranteed worst case. For an explosion, emit TRIGGER_EVENT EXPLOSION; the server uses configured release mass as a clearly provisional simulation estimate. If none exists, ask whether this is a small pipe or storage tank, not for exact kilograms. A mass follow-up after an explosion updates its impulse, not the continuous leak.
Never invent safety thresholds, PPE requirements, coordinates, or live resources.
DEPLOY_UNIT value must preserve the operator's unit label and supplied location, e.g. "deploy Engine 4 at 40.36, -74.65" or "deploy Ambulance 2 to source". A JSON string containing label, latitude, longitude and optional unitId is also accepted only for coordinates explicitly supplied by the operator.
Unit details may be supplied explicitly as '; teamType: hazmat; equipment: radio, monitor; task: assist residents', or JSON fields teamType, equipment (string array), task. Natural reports such as 'I have a fire team with hazmat responding on 40.36, -74.65' are DEPLOY_UNIT with the original operator text; preserve Fire team as the label and hazmat as teamType. Never invent equipment or assignments. For 'assign 3 nearby homes to Hazmat 1', emit ASSIGN_PROPERTY with the original text; the server chooses nearest unassigned known residential footprints relative to that unit.
For property assignment emit ASSIGN_PROPERTY value 'assign <operator-supplied building name or footprintId> to <existing unit label or ID>', or a JSON string with propertyId/propertyName and unitId/unitLabel. The server validates against loaded map buildings; never invent homes or claim known occupancy. Do not include assignments inside DEPLOY_UNIT.
Never turn street names into coordinates. Ask for coordinates or map place selection instead. Cardinal offsets from source are simulated, not geocoded. Do not claim actual dispatch or a safe route.
This is a simulated decision-support tool, not an emergency authority.
"""

_AGENT_CACHE_MAX_ENTRIES = 128
_AGENT_CACHE: OrderedDict[str, AgentResult] = OrderedDict()


def _cache_key(text: str, scenario: Any, model: str) -> str:
    payload = json.dumps(
        {"text": text, "scenario": scenario.model_dump(mode="json"), "model": model},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cached_decision(key: str) -> AgentResult | None:
    result = _AGENT_CACHE.get(key)
    if result is None:
        return None
    _AGENT_CACHE.move_to_end(key)
    provider = result.provider.replace("GEMINI:", "GEMINI_CACHE:") if result.provider.startswith("GEMINI:") else "DETERMINISTIC_CACHE"
    return AgentResult(result.decision.model_copy(deep=True), provider)


def _store_decision(key: str, decision: AgentDecision, provider: str) -> AgentDecision:
    _AGENT_CACHE[key] = AgentResult(decision.model_copy(deep=True), provider)
    _AGENT_CACHE.move_to_end(key)
    while len(_AGENT_CACHE) > _AGENT_CACHE_MAX_ENTRIES:
        _AGENT_CACHE.popitem(last=False)
    return decision


def _is_unknown_answer(normalized: str) -> bool:
    return any(answer in normalized for answer in _UNKNOWN_ANSWERS)


def _next_intake_question(text: str, scenario: Any) -> AgentDecision | None:
    normalized = text.lower().strip()
    if not normalized or _is_unknown_answer(normalized):
        question_index = min(scenario.version - 1, len(INTAKE_QUESTIONS) - 1)
        topic, question = INTAKE_QUESTIONS[question_index]
        if _is_unknown_answer(normalized):
            return AgentDecision(
                assistantText=f"Understood; {topic} is unconfirmed. I will not guess and will use the current simulated assumption. {question}",
                commands=[AgentCommand(commandType="NO_OP")],
                confidence="LOW",
                clarifyingQuestions=[question],
            )
        return AgentDecision(
            assistantText=question,
            commands=[AgentCommand(commandType="NO_OP")],
            confidence="LOW",
            clarifyingQuestions=[question],
        )
    return None


def _deterministic_decision(text: str, scenario: Any) -> AgentDecision:
    normalized = text.lower()
    intake_question = _next_intake_question(text, scenario)
    if intake_question is not None:
        return intake_question
    commands: list[AgentCommand] = []
    if re.match(r"(?:please\s+)?assign\b", normalized.strip()):
        return AgentDecision(
            assistantText="Checking the loaded map property and existing simulated unit; occupancy and access are not verified.",
            commands=[AgentCommand(commandType="ASSIGN_PROPERTY", value=text)],
            confidence="MEDIUM",
        )
    if re.search(r"\b(?:deploy|responding)\b", normalized):
        return AgentDecision(
            assistantText="Updating the simulated unit position only; no live dispatch or safe route is implied. Cardinal offsets are approximate distances from source (100 m when unspecified).",
            commands=[AgentCommand(commandType="DEPLOY_UNIT", value=text)],
            confidence="MEDIUM",
        )
    mass_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b", normalized)
    if mass_match:
        mass = min(100_000.0, float(mass_match.group(1)))
        return AgentDecision(assistantText=f"Simulation release mass set to {mass:g} kg over the configured duration; this is not a measured concentration.", commands=[AgentCommand(commandType="UPDATE_RELEASE", value=f"MASS_KG_{mass}")], confidence="HIGH")
    if "wind" in normalized:
        directions = {"northeast": 45, "southeast": 135, "southwest": 225, "northwest": 315, "north": 0, "east": 90, "south": 180, "west": 270}
        for name, degrees in directions.items():
            if re.search(rf"\b{name}\b", normalized):
                return AgentDecision(assistantText=f"Future simulated wind set from {name}; previous plume transport is preserved.", commands=[AgentCommand(commandType="UPDATE_WEATHER", value=f"DIRECTION_{degrees}")], confidence="MEDIUM")
    if any(word in normalized for word in ("explod", "explosion", "blast")):
        commands.append(AgentCommand(commandType="TRIGGER_EVENT", value="EXPLOSION"))
        return AgentDecision(
            assistantText="Recording the reported explosion in the simulation. Any release estimate is provisional, not measured or a guaranteed worst case.",
            commands=commands,
            confidence="HIGH",
        )
    if "increase" in normalized and "wind" in normalized:
        commands.append(AgentCommand(commandType="UPDATE_WEATHER", value="INCREASE_WIND_1_MPS"))
        return AgentDecision(
            assistantText="Wind speed override increased by one meter per second for this simulation; live weather remains the baseline.",
            commands=commands,
            confidence="HIGH",
        )
    return AgentDecision(
        assistantText="I can help with that. What changed at the incident: release status, wind, explosion, or unit deployment? If you do not know, say unknown and I will keep the current assumption.",
        commands=[AgentCommand(commandType="NO_OP")],
        confidence="LOW",
        clarifyingQuestions=["What changed at the incident: release status, wind, explosion, or unit deployment? If unknown, should I keep the current assumption?"],
    )


def _schema() -> dict[str, Any]:
    return AgentDecision.model_json_schema()


def process_dispatch(text: str, scenario: Any) -> AgentResult:
    model = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
    key = _cache_key(text, scenario, model)
    cached = _cached_decision(key)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if cached is not None:
        return cached

    if not api_key or genai is None:
        provider = "DETERMINISTIC_FALLBACK"
        return AgentResult(_store_decision(key, _deterministic_decision(text, scenario), provider), provider)

    timeout = provider_timeout("GEMINI_TIMEOUT_SECONDS", 6.0)

    def generate() -> AgentDecision:
        client = genai.Client(api_key=api_key)
        prompt = {
            "instruction": SYSTEM_INSTRUCTION,
            "currentScenario": scenario.model_dump(mode="json"),
            "userMessage": text,
            "responseSchema": _schema(),
        }
        try:
            response = client.models.generate_content(
                model=model,
                contents=json.dumps(prompt),
                config={"response_mime_type": "application/json", "response_schema": _schema(),
                        "http_options": {"timeout": max(10_000, int(timeout * 1000)), "retry_options": {"attempts": 1}}},
            )
            return AgentDecision.model_validate_json(response.text)
        finally:
            close = getattr(client, "close", None)
            if close:
                close()

    try:
        decision = bounded_provider_call(generate, timeout)
        # Explicit map actions retain operator text rather than model-invented details.
        explicit = _deterministic_decision(text, scenario)
        if explicit.commands and explicit.commands[0].commandType in {"DEPLOY_UNIT", "ASSIGN_PROPERTY", "UPDATE_RELEASE", "TRIGGER_EVENT"}:
            decision.commands = explicit.commands
        provider = f"GEMINI:{model}"
        return AgentResult(_store_decision(key, decision, provider), provider)
    except Exception:
        # Transient failures are not cached, so the next request can recover.
        return AgentResult(_deterministic_decision(text, scenario), "DETERMINISTIC_FALLBACK_AFTER_PROVIDER_ERROR")
