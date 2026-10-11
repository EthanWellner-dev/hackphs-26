import asyncio
import sys
from pathlib import Path

import httpx
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import HAZARD_LIBRARY, Scenario, app
from app.services.context import demo_context


async def request(method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_health_and_hazard_contracts() -> None:
    async def exercise() -> None:
        health = await request("get", "/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "aero-hazard-demo"}

        hazards = await request("get", "/api/hazards")
        assert hazards.status_code == 200
        assert set(HAZARD_LIBRARY).issubset(hazards.json())
        for hazard in hazards.json().values():
            assert hazard["traceThreshold"] <= hazard["pelThreshold"] <= hazard["idlhThreshold"]

    asyncio.run(exercise())


def test_map_session_falls_back_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    async def exercise() -> None:
        response = await request("get", "/api/map/session")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "OPEN_3D"
        assert body["googleMapsApiKey"] is None
        assert body["sessionId"] is None

    asyncio.run(exercise())


def test_scenario_and_plume_contracts_clamp_time_and_preserve_version() -> None:
    async def exercise() -> None:
        scenario_response = await request("get", "/api/scenario")
        assert scenario_response.status_code == 200
        scenario = scenario_response.json()
        assert scenario["version"] == 1

        plume_response = await request("get", "/api/plume", params={"timeMinutes": -40})
        assert plume_response.status_code == 200
        plume = plume_response.json()
        assert plume["timeMinutes"] == 0
        assert len(plume["particles"]) == 18
        assert len(plume["volumeCells"]) == 10
        assert plume["isApproximation"] is True
        assert plume["assumptions"]

        update = await request("post", "/api/scenario", json={"scenario": scenario})
        assert update.status_code == 200
        assert update.json()["version"] == 2

    asyncio.run(exercise())


def test_bootstrap_applies_context_weather_before_plume(monkeypatch) -> None:
    def fake_live_context(latitude: float, longitude: float):
        context = demo_context(latitude, longitude)
        context.weather.windSpeedMetersPerSecond = 7.25
        context.weather.windDirectionFromDegrees = 135.0
        context.weather.source = "CACHED"
        context.provenance["weather"] = "CACHED"
        context.weatherTimeline = [context.weatherTimeline[0].model_copy(update={"windSpeedMetersPerSecond": 7.25, "windDirectionFromDegrees": 135.0, "source": "CACHED"})]
        return context

    monkeypatch.setattr("app.main.get_live_context", fake_live_context)

    async def exercise() -> None:
        response = await request("get", "/api/bootstrap", params={"mapMode": "OPEN_3D"})
        assert response.status_code == 200
        body = response.json()
        assert body["context"]["weather"]["source"] == "CACHED"
        assert body["scenario"]["weather"]["windSpeedMetersPerSecond"] == 7.25
        assert body["scenario"]["weather"]["windDirectionFromDegrees"] == 135.0
        assert body["frame"]["scenarioVersion"] == body["scenario"]["version"]
        assert body["map"]["mode"] == "OPEN_3D"

    asyncio.run(exercise())


def test_context_contracts_validate_coordinates() -> None:
    async def exercise() -> None:
        demo = await request("get", "/api/context")
        assert demo.status_code == 200
        body = demo.json()
        assert body["provenance"]["context"] == "DEMO"
        assert body["weather"]["precipitationType"] == "NONE"
        assert body["airQuality"]["source"] == "DEMO"
        assert body["elevation"]["source"] == "DEMO"

        invalid_demo = await request("get", "/api/context", params={"longitude": 181})
        assert invalid_demo.status_code == 422
        invalid_live = await request("get", "/api/context/live", params={"latitude": -91})
        assert invalid_live.status_code == 422

    asyncio.run(exercise())


def test_dispatch_contract_rejects_invalid_payloads_and_returns_audio_shape(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    async def exercise() -> None:
        scenario = Scenario().model_dump(mode="json")
        empty_text = await request("post", "/api/dispatch", json={"text": "", "scenario": scenario})
        assert empty_text.status_code == 422
        oversized = await request("post", "/api/dispatch", json={"text": "x" * 1001, "scenario": scenario})
        assert oversized.status_code == 422
        missing_scenario = await request("post", "/api/dispatch", json={"text": "status"})
        assert missing_scenario.status_code == 422

        response = await request("post", "/api/dispatch", json={"text": "I don't know", "scenario": scenario})
        assert response.status_code == 200
        body = response.json()
        assert body["commands"][0]["commandType"] == "NO_OP"
        assert len(body["clarifyingQuestions"]) == 1
        assert body["audio"]["status"] == "TEXT_ONLY"
        assert body["frame"]["scenarioVersion"] == 2
        assert body["actionPlan"]["scenarioId"] == body["scenario"]["scenarioId"]
        assert body["actionPlan"]["disclaimer"].startswith("SIMULATION ONLY")
        assert body["actionPlan"]["assumptions"]
        assert body["frame"]["assumptions"] == ["Real-time plume projection from wind, release, terrain, and hazard inputs."]

    asyncio.run(exercise())


def test_scenario_validation_rejects_invalid_weather_release_and_terrain() -> None:
    async def exercise() -> None:
        base = Scenario().model_dump(mode="json")
        invalid_cases = [
            ("weather.precipitationMillimetersPerHour", {"weather": {**base["weather"], "precipitationMillimetersPerHour": -1}}),
            ("weather.precipitationType", {"weather": {**base["weather"], "precipitationType": "HAIL"}}),
            ("release.rateKgPerSecond", {"release": {**base["release"], "rateKgPerSecond": -1}}),
            ("terrainFeatures", {"terrainFeatures": [{"featureId": "bad", "kind": "BUILDING", "eastMeters": 0, "northMeters": 0, "radiusMeters": 0, "heightMeters": 10, "porosity": 0}]}),
        ]
        for field, patch in invalid_cases:
            candidate = dict(base)
            candidate.update(patch)
            response = await request("post", "/api/scenario", json={"scenario": candidate})
            assert response.status_code == 422, field

    asyncio.run(exercise())
