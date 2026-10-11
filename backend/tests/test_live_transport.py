import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import Scenario, WeatherSample, _local_wind, _puff_state, make_frame
from app.services.context import ProviderConfig, _cache_ttl_seconds, _noaa_weather_fallback, normalize_weather_timeline


def test_forecast_is_aligned_to_current_time_not_midnight():
    payload = {
        "current": {"time": "2026-10-11T12:30", "wind_speed_10m": 6, "wind_direction_10m": 350, "temperature_2m": 18},
        "hourly": {"time": ["2026-10-11T00:00", "2026-10-11T12:00", "2026-10-11T13:00", "2026-10-11T14:00", "2026-10-11T15:00"], "wind_speed_10m": [70, 4, 8, 10, 12], "wind_direction_10m": [180, 340, 10, 30, 40], "temperature_2m": [0, 17, 19, 20, 21]},
    }
    samples = normalize_weather_timeline(payload)
    assert samples[0].windSpeedMetersPerSecond == 6
    assert samples[1].windSpeedMetersPerSecond == pytest.approx(6 + 2 / 6)
    assert samples[1].validAt == "2026-10-11T12:35:00Z"
    assert samples[1].sampleKind == "INTERPOLATED_FORECAST"
    assert samples[1].nativeIntervalMinutes == 60
    assert 350 < samples[1].windDirectionFromDegrees < 360


@pytest.mark.parametrize("override", ["900", "-1", "nan", "inf"])
def test_weather_refresh_cannot_exceed_five_minutes(monkeypatch, override):
    monkeypatch.setenv("WEATHER_CACHE_MAX_AGE_SECONDS", override)
    assert 0 <= _cache_ttl_seconds("Weather provider") <= 300


def test_missing_forecast_timestamps_are_not_invented():
    assert normalize_weather_timeline({"hourly": {"wind_speed_10m": [4], "wind_direction_10m": [180], "temperature_2m": [18]}}) == []


def test_mass_drives_concentration_and_particles_conserve_release():
    small = Scenario()
    large = small.model_copy(deep=True)
    large.release.rateKgPerSecond *= 2
    a, b = make_frame(small, 30), make_frame(large, 30)
    assert a.releasedMassKg == pytest.approx(10)
    assert sum(p.massKg for p in a.particles) == pytest.approx(10)
    assert b.maxConcentration == pytest.approx(a.maxConcentration * 2)
    assert b.affectedAreaSqKm >= a.affectedAreaSqKm
    assert a.populationAtRisk is None
    assert a.concentrationUnit == "ppm"
    assert len(a.windVectors) == 49


def test_impulse_survives_shutoff_and_partial_minutes_advect():
    scenario = Scenario(release={"mode": "IMPULSIVE", "impulseMassKg": 10, "impulseTimeMinutes": 5})
    before, at_release, later = make_frame(scenario, 4), make_frame(scenario, 5), make_frame(scenario, 7)
    assert before.maxConcentration == 0
    assert at_release.maxConcentration > 0
    assert later.maxConcentration > 0
    assert sum(p.massKg for p in later.particles) == pytest.approx(10)
    assert later.particles[0].longitude != at_release.particles[0].longitude


def test_future_direction_changes_preserve_earlier_puff_history():
    original = Scenario(weatherTimeline=[WeatherSample(minutesFromNow=minute, windSpeedMetersPerSecond=4, windDirectionFromDegrees=0, temperatureCelsius=18, source="LIVE") for minute in range(0, 121, 5)])
    turning = original.model_copy(deep=True)
    for sample in turning.weatherTimeline:
        if sample.minutesFromNow > 10:
            sample.windDirectionFromDegrees = 90
    assert _puff_state(original, 10) == _puff_state(turning, 10)
    initial = _puff_state(turning, 10)[0]
    later = _puff_state(turning, 20)[0]
    assert later["east"] < initial["east"] - 1000
    assert later["north"] < initial["north"]
    assert later["north"] < -2000  # Previous southward displacement was not rotated west.


def test_obstacle_flow_is_spatial_and_bounded():
    scenario = Scenario(weather={"windDirectionFromDegrees": 270, "windSpeedMetersPerSecond": 4}, terrainFeatures=[{"featureId": "building", "kind": "BUILDING", "eastMeters": 30, "northMeters": 10, "radiusMeters": 30, "heightMeters": 20}])
    vx, vy = _local_wind(scenario, 0, 0, 0, 2)
    assert 0 < vx < 4
    assert vy < 0
    assert _local_wind(scenario, 0, -500, 0, 2)[0] == pytest.approx(4)


def test_noaa_fallback_is_labeled_forecast_and_converts_units(tmp_path):
    import httpx

    class Client:
        def get(self, url, params=None):
            payload = {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/PHI/65,100/forecast/hourly"}} if "/points/" in url else {"properties": {"periods": [{"startTime": "2026-10-11T08:00:00-04:00", "windSpeed": "4 to 6 mph", "windDirection": "NE", "temperature": 68, "temperatureUnit": "F"}]}}
            return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    payload, source = _noaa_weather_fallback(40, -74, tmp_path, "test", ProviderConfig(), Client())
    assert source == "LIVE"
    assert payload["_provider"] == "NOAA hourly forecast"
    assert payload["hourly"]["wind_speed_10m"][0] == pytest.approx(2.2352)
    assert payload["hourly"]["temperature_2m"][0] == pytest.approx(20)
    assert payload["hourly"]["wind_direction_10m"][0] == 45
