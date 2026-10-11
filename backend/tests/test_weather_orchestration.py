import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.main import Scenario, make_frame, scenario_with_context
from app.services import context


@pytest.mark.parametrize('fallback_available', [True, False])
def test_weather_failure_calls_secondary_and_preserves_other_context(monkeypatch, tmp_path, fallback_available):
    calls = []
    now = datetime.now(timezone.utc).isoformat()

    def provider(url, cache_path, params, config, client, label, **kwargs):
        calls.append(label)
        if label == 'Elevation provider':
            return {'elevation': [42]}, 'LIVE', []
        return None, 'DEMO', ['Provider unavailable']

    def secondary(*args):
        calls.append('NOAA weather fallback')
        if not fallback_available:
            return None, 'DEMO'
        return {'hourly': {'time': [now], 'wind_speed_10m': [3], 'wind_direction_10m': [180], 'temperature_2m': [20]}, '_provider': 'NOAA hourly forecast'}, 'LIVE'

    monkeypatch.setattr(context, '_provider_cache_dir', lambda: tmp_path)
    monkeypatch.setattr(context, '_load_provider_sample', provider)
    monkeypatch.setattr(context, '_noaa_weather_fallback', secondary)
    result = context._get_live_context_uncached(40, -74)
    assert 'NOAA weather fallback' in calls
    assert 'OpenStreetMap building footprint provider' in calls
    assert result.elevation.elevationMeters == 42
    assert result.weather.source == ('LIVE' if fallback_available else 'DEMO')
    if fallback_available:
        assert result.weather.provider == 'NOAA hourly forecast'
        assert result.weather.sampleKind == 'FORECAST'
    else:
        assert result.warnings


def test_incident_epoch_survives_api_roundtrip():
    scenario = scenario_with_context(context.demo_context(40, -74))
    assert scenario.incidentStartedAt.tzinfo is not None
    restored = Scenario.model_validate_json(scenario.model_dump_json())
    assert restored.incidentStartedAt == scenario.incidentStartedAt


def test_non_gas_concentration_is_mass_not_ppm():
    scenario = Scenario()
    scenario.hazard.category = 'BIOLOGICAL'
    assert make_frame(scenario, 5).concentrationUnit == 'mg/m³'
