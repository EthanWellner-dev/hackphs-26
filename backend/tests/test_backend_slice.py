import sys
from pathlib import Path

import asyncio
import httpx
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import HAZARD_LIBRARY, Hazard, Scenario, TerrainFeature, WeatherSample, app, build_action_plan, concentration_at, dispersion_coefficients, make_frame
from app.services.agent import process_dispatch
from app.services.voice import _safe_cache_key, synthesize_dispatch


async def _request(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def test_plume_uses_five_minute_wind_timeline_and_varies_vertical_shape() -> None:
    scenario = Scenario(weatherTimeline=[WeatherSample(minutesFromNow=0, windSpeedMetersPerSecond=2.0, windDirectionFromDegrees=0.0, temperatureCelsius=18.0, source="LIVE"), WeatherSample(minutesFromNow=5, windSpeedMetersPerSecond=8.0, windDirectionFromDegrees=90.0, temperatureCelsius=19.0, source="LIVE"), WeatherSample(minutesFromNow=10, windSpeedMetersPerSecond=3.0, windDirectionFromDegrees=180.0, temperatureCelsius=20.0, source="LIVE")])
    frame = make_frame(scenario, 10)
    assert len(scenario.weatherTimeline) == 3
    assert len({round(p.altitudeMeters, 2) for p in frame.particles}) > 4
    assert len({round(v.heightMeters, 2) for v in frame.volumeCells}) > 4
    assert any("not validated" in assumption for assumption in frame.assumptions)
    assert max(p.altitudeMeters for p in frame.particles) - min(p.altitudeMeters for p in frame.particles) > 20.0


def test_continuous_release_is_present_before_duration_but_impulse_is_time_gated() -> None:
    continuous = make_frame(Scenario(), 5)
    impulse = make_frame(Scenario(release={"mode": "IMPULSIVE", "impulseMassKg": 300.0, "impulseTimeMinutes": 20}), 5)
    assert continuous.maxConcentration > 0
    assert impulse.maxConcentration == 0
    assert make_frame(Scenario(release={"mode": "IMPULSIVE", "impulseMassKg": 300.0, "impulseTimeMinutes": 20}), 20).maxConcentration > 0


def test_mixture_uses_weighted_density_and_preserves_components() -> None:
    scenario = Scenario(gases=[{"name": "Chlorine", "category": "CHEMICAL", "massFraction": 0.6, "densityRelativeToAir": 2.47, "traceThreshold": 0.5, "pelThreshold": 1.0, "idlhThreshold": 10.0}, {"name": "Ammonia", "category": "CHEMICAL", "massFraction": 0.4, "densityRelativeToAir": 0.6, "traceThreshold": 0.5, "pelThreshold": 25.0, "idlhThreshold": 300.0}])
    assert len(scenario.gases) == 2
    assert make_frame(scenario, 30).maxConcentration > 0


def test_plume_changes_transport_direction_with_wind_direction() -> None:
    south_wind = Scenario()
    south_wind.weather.windDirectionFromDegrees = 0
    north_wind = Scenario()
    north_wind.weather.windDirectionFromDegrees = 180

    south_frame = make_frame(south_wind, 30)
    north_frame = make_frame(north_wind, 30)

    south_particle = south_frame.particles[-1]
    north_particle = north_frame.particles[-1]
    assert south_particle.latitude < south_wind.location.latitude
    assert north_particle.latitude > north_wind.location.latitude


def test_stable_atmosphere_has_narrower_crosswind_spread() -> None:
    unstable = Scenario()
    unstable.weather.pasquillStabilityClass = "A"
    stable = Scenario()
    stable.weather.pasquillStabilityClass = "F"

    unstable_sigma_y, unstable_sigma_z = dispersion_coefficients(unstable, 250.0)
    stable_sigma_y, stable_sigma_z = dispersion_coefficients(stable, 250.0)
    assert stable_sigma_y < unstable_sigma_y
    assert stable_sigma_z < unstable_sigma_z


def test_deterministic_agent_applies_explosion_command(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    scenario = Scenario()
    result = process_dispatch("The tank exploded", scenario)
    assert result.provider.startswith("DETERMINISTIC")
    assert result.decision.commands[0].commandType == "TRIGGER_EVENT"


def test_deterministic_agent_asks_one_follow_up_for_missing_details(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = process_dispatch("I don't know", Scenario())
    assert result.decision.commands[0].commandType == "NO_OP"
    assert len(result.decision.clarifyingQuestions) == 1
    assert "substance" in result.decision.clarifyingQuestions[0]
    assert "will not guess" in result.decision.assistantText


def test_deterministic_agent_accepts_unknown_after_a_follow_up(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    scenario = Scenario(version=2)
    result = process_dispatch("unknown", scenario)
    assert result.decision.commands[0].commandType == "NO_OP"
    assert "release is unconfirmed" in result.decision.assistantText
    assert result.decision.clarifyingQuestions


def test_agent_cache_returns_copy_without_provider(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    scenario = Scenario()
    first = process_dispatch("Increase wind", scenario)
    first.decision.commands.clear()
    second = process_dispatch("Increase wind", scenario)
    assert second.provider == "DETERMINISTIC_CACHE"
    assert second.decision.commands[0].commandType == "UPDATE_WEATHER"


def test_concentration_is_zero_upwind() -> None:
    assert concentration_at(Scenario(), 30, 0.0, 0.0, 2.0) == 0.0


def test_extremely_stable_class_is_narrower_than_neutral() -> None:
    neutral = Scenario()
    stable = Scenario()
    stable.weather.pasquillStabilityClass = "G"
    assert dispersion_coefficients(stable, 250.0)[0] < dispersion_coefficients(neutral, 250.0)[0]


def test_half_life_and_settling_reduce_concentration_at_later_times() -> None:
    baseline = Scenario()
    decaying = Scenario(hazard=Hazard(decayHalfLifeMinutes=10.0, settlingVelocityMetersPerSecond=0.02))
    early = concentration_at(decaying, 5, 250.0, 0.0, 2.0)
    late = concentration_at(decaying, 60, 250.0, 0.0, 2.0)
    baseline_value = concentration_at(baseline, 30, 250.0, 0.0, 2.0)
    decaying_value = concentration_at(decaying, 30, 250.0, 0.0, 2.0)
    assert 0.0 < early
    assert 0.0 <= late < early
    assert 0.0 < decaying_value < baseline_value


def test_precipitation_reduces_airborne_concentration() -> None:
    dry = Scenario()
    rainy = Scenario()
    rainy.weather.precipitationMillimetersPerHour = 25.0
    rainy.weather.precipitationType = "RAIN"
    dry_value = concentration_at(dry, 30, 250.0, 0.0, 2.0)
    rainy_value = concentration_at(rainy, 30, 250.0, 0.0, 2.0)
    assert 0.0 < rainy_value < dry_value


def test_snow_has_less_scavenging_than_rain_in_bounded_model() -> None:
    rain = Scenario()
    rain.weather.precipitationMillimetersPerHour = 20.0
    rain.weather.precipitationType = "RAIN"
    snow = Scenario()
    snow.weather.precipitationMillimetersPerHour = 20.0
    snow.weather.precipitationType = "SNOW"
    assert concentration_at(snow, 30, 250.0, 0.0, 2.0) > concentration_at(rain, 30, 250.0, 0.0, 2.0)


def test_building_obstruction_reduces_concentration_but_leaves_wake() -> None:
    clear = Scenario()
    blocked = Scenario(terrainFeatures=[TerrainFeature(featureId="b1", kind="BUILDING", eastMeters=100.0, northMeters=0.0, radiusMeters=40.0, heightMeters=20.0)])
    clear_value = concentration_at(clear, 30, 100.0, 0.0, 2.0, 100.0, 0.0)
    blocked_value = concentration_at(blocked, 30, 100.0, 0.0, 2.0, 100.0, 0.0)
    assert 0.0 < blocked_value < clear_value


def test_hazard_library_thresholds_are_ordered() -> None:
    assert {"chlorine", "ammonia", "methane", "iodine-131", "cesium-137", "anthrax"} <= HAZARD_LIBRARY.keys()
    for hazard in HAZARD_LIBRARY.values():
        assert hazard.traceThreshold <= hazard.pelThreshold <= hazard.idlhThreshold


def test_action_plan_is_conservative_and_uses_context_provenance() -> None:
    scenario = Scenario()
    scenario.weather.precipitationMillimetersPerHour = 12.0
    frame = make_frame(scenario, 30)
    plan = build_action_plan(scenario, frame)
    assert plan.hazardSeverity in {"UNKNOWN", "ADVISORY", "CRITICAL"}
    assert plan.immediateActions
    assert plan.firstResponderPpe
    assert "SIMULATION ONLY" in plan.disclaimer
    assert "rainfall as decontamination" in plan.shelterGuidance
    assert plan.provenance["context"] == "UNKNOWN"


def test_exploded_action_plan_is_critical() -> None:
    scenario = Scenario()
    scenario.release.hasExploded = True
    plan = build_action_plan(scenario, make_frame(scenario, 30))
    assert plan.hazardSeverity == "CRITICAL"
    assert plan.isolationRadiusMeters >= 0


def test_surface_loading_is_exposed_for_depositing_hazards() -> None:
    frame = make_frame(Scenario(), 30)
    assert frame.surfaceZones
    assert all(zone.sanitationStatus == "CANDIDATE_REVIEW" for zone in frame.surfaceZones)
    assert all(zone.surfaceLoading > 0 for zone in frame.surfaceZones)


def test_non_depositing_hazard_has_no_surface_zones() -> None:
    scenario = Scenario(hazard=Hazard(surfaceDepositionPotential=False, surfaceRetentionFraction=0.0, surfacePersistenceMinutes=0, surfaceFateNote="No surface persistence modeled."))
    assert make_frame(scenario, 30).surfaceZones == []


def test_invalid_hazard_surface_retention_is_rejected() -> None:
    scenario = Scenario().model_dump(mode="json")
    scenario["hazard"]["surfaceRetentionFraction"] = 2.0
    response = asyncio.run(_request("post", "/api/scenario", json={"scenario": scenario}))
    assert response.status_code == 422


def test_invalid_hazard_thresholds_are_rejected() -> None:
    scenario = Scenario().model_dump(mode="json")
    scenario["hazard"]["pelThreshold"] = 20.0
    scenario["hazard"]["idlhThreshold"] = 10.0
    response = asyncio.run(_request("post", "/api/scenario", json={"scenario": scenario}))
    assert response.status_code == 422


def test_context_endpoint_returns_demo_provenance() -> None:
    response = asyncio.run(_request("get", "/api/context"))
    assert response.status_code == 200
    assert response.json()["provenance"]["context"] == "DEMO"
    assert len(response.json()["features"]) == 2
    assert response.json()["weather"]["precipitationMillimetersPerHour"] == 0.0


def test_live_context_endpoint_rejects_invalid_coordinates() -> None:
    response = asyncio.run(_request("get", "/api/context/live", params={"latitude": 95}))
    assert response.status_code == 422


def test_api_health_scenario_plume_and_validation() -> None:
    async def exercise() -> None:
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/health")).json()["status"] == "ok"
            scenario_response = await client.get("/api/scenario")
            assert scenario_response.status_code == 200
            plume_response = await client.get("/api/plume", params={"timeMinutes": 999})
            assert plume_response.status_code == 200
            assert plume_response.json()["timeMinutes"] == 120
            invalid = await client.post("/api/dispatch", json={"text": "", "scenario": {}})
            assert invalid.status_code == 422

    asyncio.run(exercise())


def test_manual_scenario_update_increments_version() -> None:
    response = asyncio.run(_request("post", "/api/scenario", json={"scenario": Scenario().model_dump(mode="json")}))
    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_dispatch_applies_explosion_wind_and_deployment(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    scenario = Scenario().model_dump(mode="json")
    explosion = asyncio.run(_request("post", "/api/dispatch", json={"text": "The tank exploded", "scenario": scenario}))
    assert explosion.status_code == 200
    exploded = explosion.json()["scenario"]
    assert exploded["release"]["hasExploded"] is True
    assert exploded["release"]["rateKgPerSecond"] == Scenario().release.rateKgPerSecond
    assert exploded["release"]["impulseMassKg"] == 0
    assert explosion.json()["clarifyingQuestions"]

    weather = asyncio.run(_request("post", "/api/dispatch", json={"text": "Increase wind", "scenario": scenario}))
    assert weather.json()["scenario"]["weather"]["windSpeedMetersPerSecond"] == 5.5

    deployment = asyncio.run(_request("post", "/api/dispatch", json={"text": "Deploy Engine 4", "scenario": scenario}))
    assert deployment.json()["scenario"]["location"]["label"] == scenario["location"]["label"]
    assert deployment.json()["scenario"]["activeUnits"] == []
    assert deployment.json()["clarifyingQuestions"]
    located = asyncio.run(_request("post", "/api/dispatch", json={"text": "Deploy Engine 4 to source", "scenario": scenario}))
    assert located.json()["scenario"]["activeUnits"][0]["unitId"] == "engine-4"


def test_voice_missing_configuration_is_text_only(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))
    result = synthesize_dispatch("Status update")
    assert result.status == "TEXT_ONLY"
    assert result.audio_url is None
    assert result.cache_key == _safe_cache_key("Status update", "default")