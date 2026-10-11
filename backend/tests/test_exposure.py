import asyncio
import sys
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app import main
from app.main import Scenario, _PuffTransportHistory, _field_concentration, _puff_state, make_exposure
from app.services.context import BuildingFootprint, demo_context


def context_at_source(scenario, count=1):
    source = scenario.sourceLocation or scenario.location
    context = demo_context(source.latitude, source.longitude)
    lon, lat = source.longitude, source.latitude
    context.buildings = [BuildingFootprint(footprintId=f"house-{i}", displayName=f"House {i}",
        longitude=lon, latitude=lat,
        polygon=[[lon-.00005, lat-.00005], [lon+.00005, lat-.00005], [lon+.00005, lat+.00005], [lon-.00005, lat-.00005]],
        source="DEMO", retrievedAt="2026-10-11T00:00:00Z") for i in range(count)]
    return context


def test_zero_release_contract_offline_and_single_batch(monkeypatch):
    scenario = Scenario(release={"rateKgPerSecond": 0})
    calls = []
    original = main._puff_state
    transport_calls = []
    transport = main._transport_scenario
    monkeypatch.setattr(main, "_puff_state", lambda s, t, history=None: (calls.append(t), original(s, t, history))[1])
    monkeypatch.setattr(main, "_transport_scenario", lambda s, c: (transport_calls.append(1), transport(s, c))[1])
    monkeypatch.setattr(main, "get_live_context", lambda *args: pytest.fail("exposure must be offline"))
    monkeypatch.setattr(main, "make_frame", lambda *args: pytest.fail("must not generate 25 frames"))

    async def request():
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            return await client.post("/api/exposure", json={"scenario": scenario.model_dump(mode="json")})

    response = asyncio.run(request())
    assert response.status_code == 200
    body = response.json()
    assert calls == list(range(0, 121, 5))
    assert len(transport_calls) == 1
    assert (body["startMinutes"], body["endMinutes"], body["sampleCount"], body["timeStepMinutes"]) == (0, 120, 25, 5)
    assert body["exposureUnit"] == "ppm·min"
    assert body["concentrationUnit"] == "ppm"
    assert body["colorBasis"] == "MEAN_CONCENTRATION"
    assert body["buildings"] == []
    assert body["dataAvailability"]["buildings"].startswith("UNAVAILABLE")
    assert body["areas"]
    assert all(area["timeIntegratedConcentration"] == 0 and area["color"] == "#64748b" for area in body["areas"])
    assert "not inhaled/absorbed dose" in body["disclaimer"]


def test_mass_scaling_monotonic_cumulative_and_mean_coloring():
    small = Scenario(weather={"windSpeedMetersPerSecond": 0})
    large = small.model_copy(deep=True)
    large.release.rateKgPerSecond *= 2
    context = context_at_source(small)
    a, b = make_exposure(small, context), make_exposure(large, context)
    for before, after in zip(a.buildings + a.areas, b.buildings + b.areas):
        assert after.timeIntegratedConcentration == pytest.approx(2 * before.timeIntegratedConcentration)
        assert after.peakConcentration == pytest.approx(2 * before.peakConcentration)
        assert before.meanConcentration == pytest.approx(before.timeIntegratedConcentration / 120)
        assert before.band == main.band_for(small, before.meanConcentration)
        assert before.color == main._band_color(before.band)
        cumulative = before.cumulativeTimeIntegratedConcentration
        assert len(cumulative) == 25 and cumulative[0] == 0
        assert cumulative == sorted(cumulative)
        assert cumulative[-1] == before.timeIntegratedConcentration
    assert a.buildings[0].timeIntegratedConcentration > 0


def test_incremental_transport_exact_and_shutoff_still_drifts():
    scenario = Scenario(release={"durationMinutes": 1}, weather={"windSpeedMetersPerSecond": 1, "windDirectionFromDegrees": 270})
    history = _PuffTransportHistory()
    for minute in range(0, 121, 5):
        assert _puff_state(scenario, minute, history) == _puff_state(scenario, minute)
    earlier, later = _puff_state(scenario, 5), _puff_state(scenario, 10)
    assert len(earlier) == len(later) == 1
    assert later[0]["east"] > earlier[0]["east"]
    assert later[0]["mass"] == earlier[0]["mass"]
    source = scenario.location
    context = context_at_source(scenario)
    shift = later[0]["east"] / (111_320 * main.cos(main.radians(source.latitude)))
    context.buildings[0].longitude = source.longitude + shift
    context.buildings[0].polygon = [[lon + shift, lat] for lon, lat in context.buildings[0].polygon]
    result = make_exposure(scenario, context).buildings[0]
    assert result.cumulativeTimeIntegratedConcentration[2] > result.cumulativeTimeIntegratedConcentration[1]


def test_overlap_sums_before_integrating_and_matches_field():
    scenario = Scenario(weather={"windSpeedMetersPerSecond": 0}, release={"mode": "CONTINUOUS_THEN_IMPULSIVE", "impulseMassKg": 3, "impulseTimeMinutes": 10})
    context = context_at_source(scenario)
    transported = main._transport_scenario(scenario, context)
    values = [_field_concentration(transported, _puff_state(transported, t), 0, 0, 2) for t in range(0, 121, 5)]
    result = make_exposure(scenario, context).buildings[0]
    assert result.timeIntegratedConcentration == pytest.approx(sum((a + b) * 2.5 for a, b in zip(values, values[1:])))
    assert result.peakConcentration == pytest.approx(max(values))
    continuous = scenario.model_copy(deep=True)
    continuous.release.mode = "CONTINUOUS"
    impulse = scenario.model_copy(deep=True)
    impulse.release.mode = "IMPULSIVE"
    assert result.timeIntegratedConcentration == pytest.approx(make_exposure(continuous, context).buildings[0].timeIntegratedConcentration + make_exposure(impulse, context).buildings[0].timeIntegratedConcentration)


def test_source_pin_units_and_bounded_domain():
    scenario = Scenario(sourceLocation={"latitude": 41, "longitude": -75}, hazard={"category": "BIOLOGICAL", "molecularWeightGPerMol": None}, weather={"windSpeedMetersPerSecond": 80, "windDirectionFromDegrees": 270})
    result = make_exposure(scenario, context_at_source(scenario))
    assert result.sourceLocation == scenario.sourceLocation
    assert result.location == scenario.location
    assert result.buildings[0].longitude == -75
    assert result.exposureUnit == "mg·min/m³"
    assert result.concentrationUnit == "mg/m³"
    assert len(result.areas) <= 400
    assert 50 <= result.gridResolutionMeters <= 2000
    assert max(abs(v) for v in result.domain.localBoundsMeters.values()) <= 20_000
    assert result.domainTruncated
    assert any("domain cap" in reason for reason in result.domain.truncationReasons)


@pytest.mark.parametrize("mode", ["CONTINUOUS", "IMPULSIVE", "CONTINUOUS_THEN_IMPULSIVE"])
def test_release_mass_accounting(mode):
    scenario = Scenario(release={"mode": mode, "rateKgPerSecond": 0.1, "durationMinutes": 5, "impulseMassKg": 7, "impulseTimeMinutes": 10})
    for minute in (0, 5, 9, 10, 20):
        expected = (0 if mode == "IMPULSIVE" else min(minute, 5) * 6) + (7 if mode != "CONTINUOUS" and minute >= 10 else 0)
        assert sum(puff["mass"] for puff in _puff_state(scenario, minute)) == pytest.approx(expected)
        frame = main.make_frame(scenario, minute)
        assert frame.releasedMassKg == pytest.approx(expected)
        assert sum(p.massKg for p in frame.particles) == pytest.approx(expected)


def test_gas_molecular_weight_and_density_are_distinct():
    light = Scenario(weather={"windSpeedMetersPerSecond": 0})
    heavy = light.model_copy(deep=True)
    heavy.hazard.molecularWeightGPerMol *= 2
    light_peak = max(area.timeIntegratedConcentration for area in make_exposure(light).areas)
    heavy_peak = max(area.timeIntegratedConcentration for area in make_exposure(heavy).areas)
    assert light_peak > 0
    assert heavy_peak == pytest.approx(light_peak / 2)
    heavy.hazard.densityRelativeToAir = 0.5
    assert main.plume_rise_meters(heavy) > main.plume_rise_meters(light)


def test_explosion_dispatch_uses_configured_impulse_without_rewriting_past(monkeypatch):
    from app.services.agent import AgentCommand, AgentDecision, AgentResult
    monkeypatch.setattr(main, "process_dispatch", lambda text, scenario: AgentResult(AgentDecision(assistantText="Explosion", commands=[AgentCommand(commandType="TRIGGER_EVENT", value="EXPLOSION")], confidence="HIGH"), "TEST"))
    monkeypatch.setattr(main, "synthesize_dispatch", lambda text: type("Voice", (), {"status": "TEXT_ONLY", "cache_key": "test", "audio_url": None, "provider": "TEST"})())
    original = Scenario(release={"impulseMassKg": 4})
    response = main.dispatch(main.DispatchRequest(text="explosion", scenario=original, timeMinutes=10))
    changed = response.scenario
    assert changed.release.mode == "CONTINUOUS_THEN_IMPULSIVE"
    assert changed.release.impulseTimeMinutes == 10
    assert changed.release.rateKgPerSecond == original.release.rateKgPerSecond
    assert _puff_state(changed, 5) == _puff_state(original, 5)
    assert response.frame.releasedMassKg == pytest.approx(original.release.rateKgPerSecond * 600 + 4)
    repeated = main.dispatch(main.DispatchRequest(text="explosion", scenario=changed, timeMinutes=15))
    assert repeated.scenario.release.impulseTimeMinutes == 10
    assert repeated.scenario.release.impulseMassKg == 4


def test_exact_cache_is_bounded_isolated_and_invalidates_all_inputs(monkeypatch):
    main._cached_exposure.cache_clear()
    scenario = Scenario(weather={"windSpeedMetersPerSecond": 0})
    context = context_at_source(scenario)
    calls = []
    compute = main.make_exposure
    monkeypatch.setattr(main, "make_exposure", lambda s, c: (calls.append(1), compute(s, c))[1])
    patch = main.ScenarioPatch(scenario=scenario, context=context)
    first = main.post_exposure(patch)
    second = main.post_exposure(patch)
    assert first == second and len(calls) == 1
    first.areas.clear()
    assert main.post_exposure(patch).areas
    patch.scenario.release.rateKgPerSecond *= 2
    main.post_exposure(patch)
    assert len(calls) == 2
    patch.context.buildings[0].displayName = "Updated house"
    assert main.post_exposure(patch).buildings[0].displayName == "Updated house"
    assert len(calls) == 3
    for version in range(4, 8):
        patch.scenario.version = version
        main.post_exposure(patch)
    assert main._cached_exposure.cache_info().currsize == 4
    main._cached_exposure.cache_clear()


def test_maximum_receptor_budget_responsive():
    scenario = Scenario(release={"durationMinutes": 120})
    started = time.perf_counter()
    result = make_exposure(scenario, context_at_source(scenario, 250))
    elapsed = time.perf_counter() - started
    assert len(result.buildings) == 250
    assert len(result.areas) <= 400
    assert elapsed < 20  # Generous shared-CI bound; printed timings are the reference benchmark.
    print(f"Exposure benchmark: 250 buildings, {len(result.areas)} cells, 25 samples: {elapsed:.3f}s")
