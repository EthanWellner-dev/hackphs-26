from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

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
You may propose only UPDATE_RELEASE, UPDATE_WEATHER, TRIGGER_EVENT, DEPLOY_UNIT, or NO_OP.
When required incident details are missing, ask one concise clarifying question at a time.
An operator may answer that they do not know; accept that answer without guessing, state the conservative simulation assumption, and ask the next question.
Never invent safety thresholds, PPE requirements, coordinates, or live resources.
This is a simulated decision-support tool, not an emergency authority.
"""

_AGENT_CACHE_MAX_ENTRIES = 128
_AGENT_CACHE: OrderedDict[str, AgentDecision] = OrderedDict()


def _cache_key(text: str, scenario: Any, model: str) -> str:
    payload = json.dumps(
        {"text": text, "scenario": scenario.model_dump(mode="json"), "model": model},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cached_decision(key: str) -> AgentDecision | None:
    decision = _AGENT_CACHE.get(key)
    if decision is None:
        return None
    _AGENT_CACHE.move_to_end(key)
    return decision.model_copy(deep=True)


def _store_decision(key: str, decision: AgentDecision) -> AgentDecision:
    _AGENT_CACHE[key] = decision.model_copy(deep=True)
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
    if "explod" in normalized or "blast" in normalized:
        commands.append(AgentCommand(commandType="TRIGGER_EVENT", value="EXPLOSION"))
        return AgentDecision(
            assistantText="Explosion state recorded. I am increasing the simulated release intensity and recalculating the plume.",
            commands=commands,
            confidence="HIGH",
        )
    if "increase" in normalized and "wind" in normalized:
        commands.append(AgentCommand(commandType="UPDATE_WEATHER", value="INCREASE_WIND_1_MPS"))
        return AgentDecision(
            assistantText="Wind speed override increased by one meter per second for this simulation.",
            commands=commands,
            confidence="HIGH",
        )
    if "deploy" in normalized or "engine" in normalized:
        commands.append(AgentCommand(commandType="DEPLOY_UNIT", value=text[:120]))
        return AgentDecision(
            assistantText="Unit deployment noted. Maintain an upstream position outside the visible plume boundary.",
            commands=commands,
            confidence="MEDIUM",
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
        if not api_key or genai is None:
            return AgentResult(cached, "DETERMINISTIC_CACHE")
        return AgentResult(cached, f"GEMINI_CACHE:{model}")

    if not api_key or genai is None:
        return AgentResult(_store_decision(key, _deterministic_decision(text, scenario)), "DETERMINISTIC_FALLBACK")

    try:
        client = genai.Client(api_key=api_key)
        prompt = {
            "instruction": SYSTEM_INSTRUCTION,
            "currentScenario": scenario.model_dump(mode="json"),
            "userMessage": text,
            "responseSchema": _schema(),
        }
        response = client.models.generate_content(
            model=model,
            contents=json.dumps(prompt),
            config={"response_mime_type": "application/json", "response_schema": _schema()},
        )
        decision = AgentDecision.model_validate_json(response.text)
        return AgentResult(_store_decision(key, decision), f"GEMINI:{model}")
    except Exception:
        return AgentResult(_store_decision(key, _deterministic_decision(text, scenario)), "DETERMINISTIC_FALLBACK_AFTER_PROVIDER_ERROR")
