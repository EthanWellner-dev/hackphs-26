import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.context import (
    demo_context,
    load_json_cache,
    fetch_json_with_cache,
    normalize_open_meteo,
    normalize_weather_timeline,
    normalize_air_quality,
    normalize_elevation,
    normalize_noaa_alerts,
    normalize_osrm_route,
    normalize_overpass,
    provider_headers,
    save_json_cache,
    straight_line_route,
)


def test_open_meteo_normalization_uses_current_sample() -> None:
    weather = normalize_open_meteo(
        {
            "current": {
                "time": "2026-10-10T12:00",
                "wind_speed_10m": 6.25,
                "wind_direction_10m": 405,
                "temperature_2m": 19.5,
                "precipitation": 2.4,
                "precipitation_probability": 80,
                "rain": 2.4,
                "snowfall": 0,
            }
        }
    )
    assert weather.windSpeedMetersPerSecond == 6.25
    assert weather.precipitationMillimetersPerHour == 2.4
    assert weather.precipitationProbabilityPercent == 80.0
    assert weather.precipitationType == "RAIN"
    assert weather.windDirectionFromDegrees == 45.0
    assert weather.source == "LIVE"


def test_open_meteo_normalization_converts_provider_units() -> None:
    weather = normalize_open_meteo(
        {
            "current_units": {"wind_speed_10m": "km/h"},
            "current": {
                "wind_speed_10m": 36.0,
                "wind_direction_10m": 180,
                "temperature_2m": 17.0,
            },
        }
    )
    assert weather.windSpeedMetersPerSecond == pytest.approx(10.0)


def test_open_meteo_normalization_falls_back_to_hourly() -> None:
    weather = normalize_open_meteo(
        {
            "hourly": {
                "wind_speed_10m": [4.0],
                "wind_direction_10m": [180],
                "temperature_2m": [17.0],
                "precipitation": [0.0],
                "precipitation_probability": [0],
            }
        },
        source="CACHED",
    )
    assert weather.windSpeedMetersPerSecond == 4.0
    assert weather.precipitationMillimetersPerHour == 0.0
    assert weather.precipitationType == "NONE"
    assert weather.windDirectionFromDegrees == 180.0
    assert weather.source == "CACHED"


def test_weather_timeline_interpolates_every_five_minutes() -> None:
    samples = normalize_weather_timeline({"current": {"time": "2026-10-11T06:00"}, "hourly": {"time": ["2026-10-11T06:00", "2026-10-11T07:00", "2026-10-11T08:00"], "wind_speed_10m": [4.0, 8.0, 8.0], "wind_direction_10m": [350, 10, 10], "temperature_2m": [10.0, 20.0, 20.0]}, "hourly_units": {"wind_speed_10m": "m/s"}}, source="LIVE")
    assert len(samples) == 25
    assert samples[1].minutesFromNow == 5
    assert samples[1].windSpeedMetersPerSecond == 4.333333333333333
    assert samples[1].windDirectionFromDegrees == pytest.approx(351.6666666666667)


def test_open_meteo_rejects_incomplete_response() -> None:
    with pytest.raises(ValueError, match="complete weather sample"):
        normalize_open_meteo({})


def test_air_quality_normalization_reads_current_values() -> None:
    air = normalize_air_quality({"current": {"pm2_5": 12.5, "pm10": 22, "us_aqi": 48, "ozone": 90}})
    assert air.pm25MicrogramsPerCubicMeter == 12.5
    assert air.pm10MicrogramsPerCubicMeter == 22.0
    assert air.usAqi == 48.0
    assert air.ozoneMicrogramsPerCubicMeter == 90.0


def test_elevation_and_noaa_alert_normalization() -> None:
    elevation = normalize_elevation({"elevation": [31.4]})
    assert elevation.elevationMeters == 31.4
    alerts = normalize_noaa_alerts({"features": [{"id": "alert-1", "properties": {"event": "Flood Warning", "headline": "Demo flood warning", "severity": "Moderate"}}]})
    assert alerts[0].alertId == "alert-1"
    assert alerts[0].severity == "Moderate"


def test_osrm_normalization_and_provider_headers() -> None:
    route = normalize_osrm_route({"routes": [{"distance": 1200, "duration": 180, "geometry": {"coordinates": [[-74.0, 40.0], [-74.01, 40.01]]}}]}, 40.0, -74.0, 40.01, -74.01)
    assert route.approximate is False
    assert route.distanceMeters == 1200
    assert provider_headers()["User-Agent"].startswith("Aero-Hazard-Demo/")
    assert "Accept" in provider_headers()


def test_overpass_normalization_filters_unknown_elements_and_sorts() -> None:
    features = normalize_overpass(
        {
            "elements": [
                {"type": "node", "id": 1, "lat": 40.349, "lon": -74.658, "tags": {"amenity": "school", "name": "Demo School"}},
                {"type": "node", "id": 2, "lat": 40.3488, "lon": -74.659, "tags": {"amenity": "drinking_water"}},
                {"type": "node", "id": 3, "lat": 40.3487, "lon": -74.6593, "tags": {"amenity": "bench"}},
            ]
        },
        40.3487,
        -74.6593,
    )
    assert [feature.featureType for feature in features] == ["WATER_SOURCE", "SCHOOL"]
    assert features[1].displayName == "Demo School"
    assert features[0].source == "LIVE"


def test_straight_line_route_is_approximate_and_has_two_points() -> None:
    route = straight_line_route(40.0, -74.0, 40.001, -74.002)
    assert route.approximate is True
    assert route.source == "DEMO"
    assert len(route.geometry) == 2
    assert route.distanceMeters > 0
    assert route.durationSeconds > 0


def test_building_normalization_accepts_geometry_without_center() -> None:
    from app.services.context import normalize_buildings

    buildings = normalize_buildings({"elements": [{"type": "way", "id": 1, "geometry": [{"lat": 40.0, "lon": -74.0}, {"lat": 40.0, "lon": -74.001}, {"lat": 40.001, "lon": -74.001}], "tags": {"building": "yes"}}]})
    assert len(buildings) == 1
    assert buildings[0].latitude == pytest.approx(40.0003333333)
    assert buildings[0].longitude == pytest.approx(-74.0006666667)


def test_demo_context_has_provenance_and_fixture_features() -> None:
    context = demo_context(40.3487, -74.6593)
    assert context.provenance["weather"] == "DEMO"
    assert context.provenance["context"] == "DEMO"
    assert {feature.featureType for feature in context.features} == {"WATER_SOURCE", "HVAC_RELATED"}
    assert context.warnings


def test_json_cache_round_trip_and_corrupt_cache(tmp_path) -> None:
    cache_path = tmp_path / "context.json"
    payload = {"source": "CACHED", "value": 3}
    save_json_cache(cache_path, payload)
    assert load_json_cache(cache_path) == payload
    cache_path.write_text("not json", encoding="utf-8")
    assert load_json_cache(cache_path) is None


def test_fetch_json_with_cache_uses_live_payload_and_writes_cache(tmp_path) -> None:
    cache_path = tmp_path / "provider.json"
    request = httpx.Request("GET", "https://provider.test/data")
    response = httpx.Response(200, json={"value": 7}, request=request)

    class FakeClient:
        def get(self, url, params=None):
            return response

    payload, source, warnings = fetch_json_with_cache("https://provider.test/data", cache_path, client=FakeClient())
    assert payload == {"value": 7}
    assert source == "LIVE"
    assert warnings == []
    assert load_json_cache(cache_path) == payload


def test_fetch_json_with_cache_falls_back_after_provider_error(tmp_path) -> None:
    cache_path = tmp_path / "provider.json"
    save_json_cache(cache_path, {"value": 9})

    class FailingClient:
        def get(self, url, params=None):
            raise httpx.ConnectError("offline")

    payload, source, warnings = fetch_json_with_cache("https://provider.test/data", cache_path, client=FailingClient())
    assert payload == {"value": 9}
    assert source == "CACHED"
    assert warnings


def test_fetch_json_with_cache_reuses_fresh_cache_without_provider_call(tmp_path) -> None:
    cache_path = tmp_path / "provider.json"
    save_json_cache(cache_path, {"value": 11})

    class UnexpectedClient:
        def get(self, url, params=None):
            raise AssertionError("fresh cache should prevent a provider request")

    payload, source, warnings = fetch_json_with_cache(
        "https://provider.test/data",
        cache_path,
        client=UnexpectedClient(),
        max_age_seconds=86_400,
    )
    assert payload == {"value": 11}
    assert source == "CACHED"
    assert warnings and "cached" in warnings[0].lower()


def test_live_context_uses_provider_headers_and_demo_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CONTEXT_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("OPEN_METEO_BASE_URL", "https://weather.test/v1")
    monkeypatch.setenv("OPEN_METEO_AIR_QUALITY_URL", "https://air.test/v1/air-quality")
    monkeypatch.setenv("NWS_BASE_URL", "https://nws.test")

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self):
            self.urls = []
        def get(self, url, params=None):
            self.urls.append((url, params))
            if url.endswith("/forecast"):
                return FakeResponse({"current": {"time": "2026-10-10T12:00", "wind_speed_10m": 5, "wind_direction_10m": 180, "temperature_2m": 20, "precipitation": 1.5, "rain": 1.5}})
            if "air-quality" in url:
                return FakeResponse({"current": {"pm2_5": 8}})
            if url.endswith("/elevation"):
                return FakeResponse({"elevation": [42]})
            if "route/v1/driving" in url:
                return FakeResponse({"routes": [{"distance": 1200, "duration": 180, "geometry": {"coordinates": [[-74.0, 40.0], [-74.01, 40.01]]}}]})
            return FakeResponse({"features": []})

    client = FakeClient()
    from app.services.context import get_live_context
    monkeypatch.setenv("DEMO_ROUTE_DESTINATION_LATITUDE", "40.01")
    monkeypatch.setenv("DEMO_ROUTE_DESTINATION_LONGITUDE", "-74.01")
    client = FakeClient()
    context = get_live_context(40.0, -74.0, client=client)
    assert context.provenance["weather"] == "CACHED"
    assert context.weather.stale is True
    assert context.weather.precipitationMillimetersPerHour == 1.5
    assert context.airQuality is not None and context.airQuality.pm25MicrogramsPerCubicMeter == 8.0
    assert context.elevation is not None and context.elevation.elevationMeters == 42.0
    assert context.provenance["alerts"] == "LIVE"
    assert context.provenance["context"] == "LIVE"
    assert context.features == []
    assert context.route is not None and context.route.source == "LIVE"
    assert any(url.endswith("/alerts/active") for url, _ in client.urls)
    assert any("overpass" in url for url, _ in client.urls)
    assert any("route/v1/driving" in url for url, _ in client.urls)

    class OfflineClient:
        def get(self, url, params=None):
            raise httpx.ConnectError("offline")
    offline = get_live_context(41.0, -74.0, client=OfflineClient())
    assert offline.provenance["weather"] == "DEMO"
    assert offline.warnings
