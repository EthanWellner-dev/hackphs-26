from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from google import genai
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


SYSTEM_INSTRUCTION = """You are Aero-Hazard's emergency operations dispatcher.
Return only JSON matching the supplied schema. Keep assistantText concise and operational.
You may propose only UPDATE_RELEASE, UPDATE_WEATHER, TRIGGER_EVENT, DEPLOY_UNIT, or NO_OP.
Never invent safety thresholds, PPE requirements, coordinates, or live resources.
This is a simulated decision-support tool, not an emergency authority.
"""


def _deterministic_decision(text: str) -> AgentDecision:
    normalized = text.lower()
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
        assistantText="Dispatch note logged. State the hazard, release status, wind override, or unit command to change the simulation.",
        commands=[AgentCommand(commandType="NO_OP")],
        confidence="LOW",
        clarifyingQuestions=["What changed at the incident: release, wind, explosion, or unit deployment?"],
    )


def _schema() -> dict[str, Any]:
    return AgentDecision.model_json_schema()


def process_dispatch(text: str, scenario: Any) -> AgentResult:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return AgentResult(_deterministic_decision(text), "DETERMINISTIC_FALLBACK")

    try:
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
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
        return AgentResult(decision, f"GEMINI:{model}")
    except Exception:
        return AgentResult(_deterministic_decision(text), "DETERMINISTIC_FALLBACK_AFTER_PROVIDER_ERROR")
