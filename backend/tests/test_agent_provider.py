import asyncio
import json
import sys
from pathlib import Path

from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app import main
from app.main import Scenario, app
from app.services import agent
from app.services.agent import AgentCommand, AgentDecision, AgentResult, process_dispatch


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class FakeModels:
    def __init__(self, response: FakeGeminiResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeGeminiClient:
    models: FakeModels

    def __init__(self, response: FakeGeminiResponse | None = None, error: Exception | None = None):
        self.models = FakeModels(response, error)
        self.api_key = None


def test_gemini_structured_response_is_validated_and_cached(monkeypatch) -> None:
    decision_json = json.dumps({
        "assistantText": "Explosion confirmed. Recalculating the simulated release.",
        "commands": [{"commandType": "TRIGGER_EVENT", "value": "EXPLOSION"}],
        "confidence": "HIGH",
        "clarifyingQuestions": [],
    })
    fake_client = FakeGeminiClient(FakeGeminiResponse(decision_json))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FAST_MODEL", "test-model-structured")
    monkeypatch.setattr(agent.genai, "Client", lambda api_key: fake_client)

    scenario = Scenario(scenarioId="LLM-STRUCTURED-TEST")
    result = process_dispatch("The leak just exploded", scenario)

    assert result.provider == "GEMINI:test-model-structured"
    assert result.decision.commands[0].commandType == "TRIGGER_EVENT"
    assert result.decision.confidence == "HIGH"
    assert len(fake_client.models.calls) == 1
    request = fake_client.models.calls[0]
    assert request["config"]["response_mime_type"] == "application/json"
    assert request["config"]["response_schema"]["title"] == "AgentDecision"

    cached = process_dispatch("The leak just exploded", scenario)
    assert cached.provider == "GEMINI_CACHE:test-model-structured"
    assert len(fake_client.models.calls) == 1


def test_malformed_gemini_response_uses_deterministic_live_update_fallback(monkeypatch) -> None:
    fake_client = FakeGeminiClient(FakeGeminiResponse("not valid json"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FAST_MODEL", "test-model-malformed")
    monkeypatch.setattr(agent.genai, "Client", lambda api_key: fake_client)

    result = process_dispatch("The leak just exploded", Scenario(scenarioId="LLM-MALFORMED-TEST"))

    assert result.provider == "DETERMINISTIC_FALLBACK_AFTER_PROVIDER_ERROR"
    assert result.decision.commands[0].commandType == "TRIGGER_EVENT"
    assert result.decision.commands[0].value == "EXPLOSION"
    assert len(fake_client.models.calls) == 1


def test_gemini_provider_exception_uses_fallback_without_leaking_error(monkeypatch) -> None:
    fake_client = FakeGeminiClient(error=TimeoutError("provider timed out"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_FAST_MODEL", "test-model-error")
    monkeypatch.setattr(agent.genai, "Client", lambda api_key: fake_client)

    result = process_dispatch("The leak just exploded", Scenario(scenarioId="LLM-ERROR-TEST"))

    assert result.provider == "DETERMINISTIC_FALLBACK_AFTER_PROVIDER_ERROR"
    assert result.decision.commands[0].commandType == "TRIGGER_EVENT"
    assert "timed out" not in result.decision.assistantText


def test_structured_llm_explosion_command_updates_scenario_live(monkeypatch) -> None:
    fake_decision = AgentDecision(
        assistantText="Explosion confirmed. Updating the live simulation.",
        commands=[AgentCommand(commandType="TRIGGER_EVENT", value="EXPLOSION")],
        confidence="HIGH",
    )
    monkeypatch.setattr(main, "process_dispatch", lambda text, scenario: AgentResult(fake_decision, "GEMINI:test-model"))
    monkeypatch.setattr(main, "synthesize_dispatch", lambda text: type("Voice", (), {"status": "TEXT_ONLY", "cache_key": "test", "audio_url": None, "provider": "TEST"})())

    async def exercise() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            scenario = Scenario(scenarioId="LIVE-UPDATE-TEST").model_dump(mode="json")
            response = await client.post("/api/dispatch", json={"text": "The leak just exploded", "scenario": scenario})
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "GEMINI:test-model"
        assert body["commands"] == [{"commandType": "TRIGGER_EVENT", "value": "EXPLOSION"}]
        assert body["scenario"]["release"]["hasExploded"] is True
        assert body["scenario"]["release"]["rateKgPerSecond"] == 20.25
        assert body["scenario"]["version"] == 2
        assert body["frame"]["scenarioVersion"] == 2
        assert body["actionPlan"]["hazardSeverity"] == "CRITICAL"

    asyncio.run(exercise())
