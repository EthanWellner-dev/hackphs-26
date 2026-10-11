from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field


Provenance = Literal["LIVE", "CACHED", "DEMO"]
FeatureType = Literal[
    "WATER_SOURCE",
    "FIRE_HYDRANT",
    "SCHOOL",
    "HOSPITAL",
    "ROAD",
    "BUILDING",
    "HVAC_RELATED",
]


class WeatherContext(BaseModel):
    windSpeedMetersPerSecond: float = Field(ge=0.0, le=80.0)
    windDirectionFromDegrees: float = Field(ge=0.0, le=360.0)
    temperatureCelsius: float
    precipitationMillimetersPerHour: float = Field(default=0.0, ge=0.0, le=500.0)
    precipitationProbabilityPercent: float | None = Field(default=None, ge=0.0, le=100.0)
    precipitationType: Literal["NONE", "RAIN", "SNOW", "MIXED"] = "NONE"
    source: Provenance
    selectedAt: str
    retrievedAt: str | None = None
    provider: str = "Open-Meteo"
    sampleKind: str = "MODEL_CURRENT"
    stale: bool = False
    ageSeconds: float | None = None
    refreshAfterSeconds: int = 300
    nativeIntervalMinutes: int = 15


class WeatherSample(BaseModel):
    """A simulation step, not a claim of five-minute weather observations."""

    minutesFromNow: int = Field(ge=0, le=120)
    windSpeedMetersPerSecond: float = Field(ge=0.0, le=80.0)
    windDirectionFromDegrees: float = Field(ge=0.0, le=360.0)
    temperatureCelsius: float
    source: Provenance
    validAt: str | None = None
    sampleKind: str = "UNSPECIFIED"
    nativeIntervalMinutes: int | None = None


class AirQualityContext(BaseModel):
    pm25MicrogramsPerCubicMeter: float | None = Field(default=None, ge=0.0)
    pm10MicrogramsPerCubicMeter: float | None = Field(default=None, ge=0.0)
    usAqi: float | None = Field(default=None, ge=0.0)
    europeanAqi: float | None = Field(default=None, ge=0.0)
    ozoneMicrogramsPerCubicMeter: float | None = Field(default=None, ge=0.0)
    nitrogenDioxideMicrogramsPerCubicMeter: float | None = Field(default=None, ge=0.0)
    source: Provenance
    selectedAt: str


class ElevationContext(BaseModel):
    elevationMeters: float
    source: Provenance
    selectedAt: str


class WeatherAlert(BaseModel):
    alertId: str
    event: str
    headline: str
    description: str = ""
    severity: str = "Unknown"
    urgency: str = "Unknown"
    certainty: str = "Unknown"
    onset: str | None = None
    expires: str | None = None
    source: Provenance
    retrievedAt: str


class ContextFeature(BaseModel):
    featureId: str
    featureType: FeatureType
    displayName: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    distanceMeters: float = Field(ge=0.0)
    tags: dict[str, str] = Field(default_factory=dict)
    source: Provenance
    retrievedAt: str


class BuildingFootprint(BaseModel):
    """An OSM building way reduced to a lightweight map-ready footprint."""

    footprintId: str
    displayName: str = "Building"
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    polygon: list[list[float]] = Field(min_length=3, max_length=80)
    levels: int | None = Field(default=None, ge=1, le=100)
    buildingType: str = "yes"
    source: Provenance
    retrievedAt: str


class RouteContext(BaseModel):
    routeId: str
    originLatitude: float
    originLongitude: float
    destinationLatitude: float
    destinationLongitude: float
    distanceMeters: float = Field(ge=0.0)
    durationSeconds: float = Field(ge=0.0)
    geometry: list[list[float]] = Field(min_length=2)
    approximate: bool = True
    source: Provenance


class ContextSnapshot(BaseModel):
    latitude: float
    longitude: float
    weather: WeatherContext
    weatherTimeline: list[WeatherSample] = Field(default_factory=list, max_length=25)
    airQuality: AirQualityContext | None = None
    elevation: ElevationContext | None = None
    alerts: list[WeatherAlert] = Field(default_factory=list, max_length=25)
    features: list[ContextFeature] = Field(default_factory=list, max_length=100)
    buildings: list[BuildingFootprint] = Field(default_factory=list, max_length=250)
    route: RouteContext | None = None
    provenance: dict[str, Provenance]
    warnings: list[str] = Field(default_factory=list, max_length=10)


@dataclass(frozen=True)
class ProviderConfig:
    timeout_seconds: float = 8.0
    user_agent: str = "Aero-Hazard-Demo/0.1 (hackathon simulator)"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2
    return 2.0 * radius * math.asin(math.sqrt(min(1.0, haversine)))


def straight_line_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    source: Provenance = "DEMO",
) -> RouteContext:
    distance = _distance_meters(origin_latitude, origin_longitude, destination_latitude, destination_longitude)
    # A conservative demo driving estimate; OSRM can replace this without changing the contract.
    duration = distance / 8.33 if distance else 0.0
    return RouteContext(
        routeId=f"straight-{origin_latitude:.5f}-{origin_longitude:.5f}-{destination_latitude:.5f}-{destination_longitude:.5f}",
        originLatitude=origin_latitude,
        originLongitude=origin_longitude,
        destinationLatitude=destination_latitude,
        destinationLongitude=destination_longitude,
        distanceMeters=distance,
        durationSeconds=duration,
        geometry=[[origin_longitude, origin_latitude], [destination_longitude, destination_latitude]],
        approximate=True,
        source=source,
    )


def _wind_speed_meters_per_second(value: Any, unit: Any = "m/s") -> float:
    """Normalize provider wind speed before it reaches the transport solver."""
    speed = float(value)
    normalized_unit = str(unit or "m/s").strip().lower().replace(" ", "")
    if normalized_unit in {"km/h", "kmh", "kph"}:
        return speed / 3.6
    if normalized_unit in {"mph", "mi/h"}:
        return speed * 0.44704
    if normalized_unit in {"kn", "kt", "knots"}:
        return speed * 0.514444
    return speed


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def normalize_weather_timeline(payload: dict[str, Any], source: Provenance = "LIVE", anchor_at: str | None = None) -> list[WeatherSample]:
    """Timestamp-aligned hourly forecast interpolation; never five-minute observations."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    speeds = hourly.get("wind_speed_10m") or []
    directions = hourly.get("wind_direction_10m") or []
    temperatures = hourly.get("temperature_2m") or []
    current = payload.get("current") or {}
    anchor = _parse_time(anchor_at) or _parse_time(current.get("time")) or datetime.now(timezone.utc)
    unit = (payload.get("hourly_units") or {}).get("wind_speed_10m", "m/s")
    knots: list[tuple[datetime, float, float, float]] = []
    for timestamp, speed, direction, temperature in zip(times, speeds, directions, temperatures):
        valid = _parse_time(timestamp)
        try:
            if valid is not None:
                knots.append((valid, _wind_speed_meters_per_second(speed, unit), float(direction) % 360, float(temperature)))
        except (TypeError, ValueError):
            continue
    # A timestamped current model sample anchors t=0 while future knots remain forecasts.
    current_time = _parse_time(current.get("time"))
    if current_time is not None:
        try:
            current_unit = (payload.get("current_units") or {}).get("wind_speed_10m", unit)
            current_knot = (current_time, _wind_speed_meters_per_second(current["wind_speed_10m"], current_unit), float(current["wind_direction_10m"]) % 360, float(current["temperature_2m"]))
            knots = [knot for knot in knots if knot[0] != current_time]
            knots.append(current_knot)
        except (KeyError, TypeError, ValueError):
            pass
    knots.sort(key=lambda knot: knot[0])
    if not knots:
        return []
    samples: list[WeatherSample] = []
    for minute in range(0, 121, 5):
        target = anchor + timedelta(minutes=minute)
        before = max((knot for knot in knots if knot[0] <= target), default=knots[0], key=lambda knot: knot[0])
        after = min((knot for knot in knots if knot[0] >= target), default=knots[-1], key=lambda knot: knot[0])
        span = (after[0] - before[0]).total_seconds()
        fraction = max(0.0, min(1.0, (target - before[0]).total_seconds() / span)) if span > 0 else 0.0
        delta = (after[2] - before[2] + 540.0) % 360.0 - 180.0
        samples.append(WeatherSample(
            minutesFromNow=minute,
            windSpeedMetersPerSecond=before[1] + (after[1] - before[1]) * fraction,
            windDirectionFromDegrees=(before[2] + delta * fraction) % 360,
            temperatureCelsius=before[3] + (after[3] - before[3]) * fraction,
            source=source,
            validAt=target.isoformat().replace("+00:00", "Z"),
            sampleKind="INTERPOLATED_FORECAST" if span > 0 else ("MODEL_CURRENT" if target == current_time else "FORECAST" if target == before[0] else "PERSISTENCE"),
            nativeIntervalMinutes=60,
        ))
    return samples


def normalize_open_meteo(payload: dict[str, Any], selected_at: str | None = None, source: Provenance = "LIVE") -> WeatherContext:
    current = payload.get("current") or {}
    current_units = payload.get("current_units") or {}
    hourly_units = payload.get("hourly_units") or {}
    speed = current.get("wind_speed_10m")
    speed_unit = current_units.get("wind_speed_10m", hourly_units.get("wind_speed_10m", "m/s"))
    direction = current.get("wind_direction_10m")
    temperature = current.get("temperature_2m")
    precipitation = current.get("precipitation")
    precipitation_probability = current.get("precipitation_probability")
    rain = current.get("rain")
    snowfall = current.get("snowfall")
    if speed is None or direction is None or temperature is None:
        hourly = payload.get("hourly") or {}
        now = datetime.now(timezone.utc)
        timestamped = [(index, _parse_time(value)) for index, value in enumerate(hourly.get("time") or [])]
        valid_times = [(index, value) for index, value in timestamped if value is not None]
        index = min(valid_times, key=lambda pair: abs((pair[1] - now).total_seconds()))[0] if valid_times else 0
        def hourly_value(name: str) -> Any:
            values = hourly.get(name) or []
            return values[index] if index < len(values) else None
        speed = hourly_value("wind_speed_10m")
        speed_unit = hourly_units.get("wind_speed_10m", "m/s")
        direction = hourly_value("wind_direction_10m")
        temperature = hourly_value("temperature_2m")
        precipitation = hourly_value("precipitation")
        precipitation_probability = hourly_value("precipitation_probability")
        rain = hourly_value("rain")
        snowfall = hourly_value("snowfall")
        selected_at = selected_at or (hourly.get("time") or [""])[index]
    if speed is None or direction is None or temperature is None:
        raise ValueError("Open-Meteo response does not contain a complete weather sample")
    precipitation_rate = float(precipitation if precipitation is not None else (rain or 0.0) + (snowfall or 0.0))
    precipitation_type: Literal["NONE", "RAIN", "SNOW", "MIXED"] = "NONE"
    if precipitation_rate > 0.0:
        if float(snowfall or 0.0) > 0.0 and float(rain or 0.0) > 0.0:
            precipitation_type = "MIXED"
        elif float(snowfall or 0.0) > 0.0:
            precipitation_type = "SNOW"
        else:
            precipitation_type = "RAIN"
    return WeatherContext(
        windSpeedMetersPerSecond=_wind_speed_meters_per_second(speed, speed_unit),
        windDirectionFromDegrees=float(direction) % 360.0,
        temperatureCelsius=float(temperature),
        precipitationMillimetersPerHour=max(0.0, precipitation_rate),
        precipitationProbabilityPercent=float(precipitation_probability) if precipitation_probability is not None else None,
        precipitationType=precipitation_type,
        source=source,
        selectedAt=str(selected_at or current.get("time") or ""),
        sampleKind="MODEL_CURRENT" if current.get("wind_speed_10m") is not None else "FORECAST",
        nativeIntervalMinutes=15 if current.get("wind_speed_10m") is not None else 60,
    )


def normalize_air_quality(payload: dict[str, Any], selected_at: str | None = None, source: Provenance = "LIVE") -> AirQualityContext:
    current = payload.get("current") or {}
    hourly = payload.get("hourly") or {}

    def first_value(name: str) -> Any:
        value = current.get(name)
        if value is not None:
            return value
        values = hourly.get(name)
        return values[0] if values else None

    return AirQualityContext(
        pm25MicrogramsPerCubicMeter=_optional_float(first_value("pm2_5")),
        pm10MicrogramsPerCubicMeter=_optional_float(first_value("pm10")),
        usAqi=_optional_float(first_value("us_aqi")),
        europeanAqi=_optional_float(first_value("european_aqi")),
        ozoneMicrogramsPerCubicMeter=_optional_float(first_value("ozone")),
        nitrogenDioxideMicrogramsPerCubicMeter=_optional_float(first_value("nitrogen_dioxide")),
        source=source,
        selectedAt=selected_at or str(current.get("time") or _now()),
    )


def normalize_elevation(payload: dict[str, Any], selected_at: str | None = None, source: Provenance = "LIVE") -> ElevationContext:
    elevations = payload.get("elevation")
    if isinstance(elevations, list):
        elevation = elevations[0] if elevations else None
    else:
        elevation = elevations
    if elevation is None:
        elevation = payload.get("elevationMeters")
    if elevation is None:
        raise ValueError("elevation response does not contain an elevation sample")
    return ElevationContext(elevationMeters=float(elevation), source=source, selectedAt=selected_at or _now())


def normalize_osrm_route(payload: dict[str, Any], origin_latitude: float, origin_longitude: float, destination_latitude: float, destination_longitude: float, source: Provenance = "LIVE") -> RouteContext:
    routes = payload.get("routes") or []
    if not routes:
        raise ValueError("OSRM response does not contain a route")
    route = routes[0]
    geometry = route.get("geometry") or {}
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else geometry
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("OSRM response does not contain route geometry")
    return RouteContext(
        routeId=f"osrm-{origin_latitude:.5f}-{origin_longitude:.5f}-{destination_latitude:.5f}-{destination_longitude:.5f}",
        originLatitude=origin_latitude,
        originLongitude=origin_longitude,
        destinationLatitude=destination_latitude,
        destinationLongitude=destination_longitude,
        distanceMeters=float(route.get("distance", 0.0)),
        durationSeconds=float(route.get("duration", 0.0)),
        geometry=[[float(point[0]), float(point[1])] for point in coordinates if isinstance(point, list) and len(point) >= 2],
        approximate=False,
        source=source,
    )


def normalize_noaa_alerts(payload: dict[str, Any], source: Provenance = "LIVE") -> list[WeatherAlert]:
    alerts: list[WeatherAlert] = []
    retrieved_at = _now()
    for index, feature in enumerate(payload.get("features") or []):
        properties = feature.get("properties") or {}
        alert_id = str(properties.get("id") or feature.get("id") or f"noaa-alert-{index}")
        alerts.append(
            WeatherAlert(
                alertId=alert_id,
                event=str(properties.get("event") or "Weather alert"),
                headline=str(properties.get("headline") or properties.get("event") or "Weather alert"),
                description=str(properties.get("description") or ""),
                severity=str(properties.get("severity") or "Unknown"),
                urgency=str(properties.get("urgency") or "Unknown"),
                certainty=str(properties.get("certainty") or "Unknown"),
                onset=properties.get("onset"),
                expires=properties.get("expires"),
                source=source,
                retrievedAt=retrieved_at,
            )
        )
    return alerts[:25]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _feature_type(tags: dict[str, Any]) -> FeatureType | None:
    amenity = str(tags.get("amenity", "")).lower()
    building = str(tags.get("building", "")).lower()
    highway = str(tags.get("highway", "")).lower()
    if amenity in {"drinking_water", "water_point", "fountain"}:
        return "WATER_SOURCE"
    if emergency := str(tags.get("emergency", "")).lower():
        if emergency == "fire_hydrant":
            return "FIRE_HYDRANT"
    if amenity in {"school", "college", "university"} or building in {"school", "college", "university"}:
        return "SCHOOL"
    if amenity == "hospital" or building == "hospital":
        return "HOSPITAL"
    if highway:
        return "ROAD"
    if building:
        return "BUILDING"
    if any(key.startswith("hvac") for key in tags):
        return "HVAC_RELATED"
    return None


def normalize_buildings(payload: dict[str, Any], source: Provenance = "LIVE") -> list[BuildingFootprint]:
    buildings: list[BuildingFootprint] = []
    retrieved_at = _now()
    for index, element in enumerate(payload.get("elements") or []):
        geometry = element.get("geometry") or []
        if len(geometry) < 3:
            continue
        polygon = [[float(point["lon"]), float(point["lat"])] for point in geometry if point.get("lat") is not None and point.get("lon") is not None]
        if len(polygon) < 3:
            continue
        tags = {str(key): str(value) for key, value in (element.get("tags") or {}).items()}
        center = element.get("center") or {}
        if center.get("lat") is None or center.get("lon") is None:
            # Some cached Overpass responses include geometry but omit `center`.
            # Derive a stable centroid so real OSM footprints are not discarded.
            center = {
                "lat": sum(point[1] for point in polygon) / len(polygon),
                "lon": sum(point[0] for point in polygon) / len(polygon),
            }
        levels = _optional_float(tags.get("building:levels"))
        buildings.append(BuildingFootprint(
            footprintId=f"osm-building-{element.get('id', index)}",
            displayName=tags.get("name") or "Building",
            latitude=float(center["lat"]),
            longitude=float(center["lon"]),
            polygon=polygon[:80],
            levels=int(levels) if levels is not None else None,
            buildingType=tags.get("building", "yes"),
            source=source,
            retrievedAt=retrieved_at,
        ))
    return buildings[:100]


def normalize_overpass(payload: dict[str, Any], latitude: float, longitude: float, source: Provenance = "LIVE") -> list[ContextFeature]:
    features: list[ContextFeature] = []
    retrieved_at = _now()
    for index, element in enumerate(payload.get("elements") or []):
        tags = {str(key): str(value) for key, value in (element.get("tags") or {}).items()}
        feature_type = _feature_type(tags)
        if feature_type is None:
            continue
        feature_lat = element.get("lat")
        feature_lon = element.get("lon")
        center = element.get("center") or {}
        feature_lat = feature_lat if feature_lat is not None else center.get("lat")
        feature_lon = feature_lon if feature_lon is not None else center.get("lon")
        if feature_lat is None or feature_lon is None:
            continue
        display_name = tags.get("name") or feature_type.replace("_", " ").title()
        features.append(
            ContextFeature(
                featureId=f"osm-{element.get('type', 'element')}-{element.get('id', index)}",
                featureType=feature_type,
                displayName=display_name,
                latitude=float(feature_lat),
                longitude=float(feature_lon),
                distanceMeters=_distance_meters(latitude, longitude, float(feature_lat), float(feature_lon)),
                tags=tags,
                source=source,
                retrievedAt=retrieved_at,
            )
        )
    return sorted(features, key=lambda feature: feature.distanceMeters)[:100]


def demo_context(latitude: float, longitude: float) -> ContextSnapshot:
    timestamp = _now()
    features = [
        ContextFeature(
            featureId="demo-water-1",
            featureType="WATER_SOURCE",
            displayName="Demo drinking-water point",
            latitude=latitude + 0.0004,
            longitude=longitude + 0.0001,
            distanceMeters=45.0,
            tags={"amenity": "drinking_water"},
            source="DEMO",
            retrievedAt=timestamp,
        ),
        ContextFeature(
            featureId="demo-hvac-1",
            featureType="HVAC_RELATED",
            displayName="Demo HVAC intake (fixture)",
            latitude=latitude - 0.0001,
            longitude=longitude + 0.0001,
            distanceMeters=12.0,
            tags={"hvac": "intake", "source": "demo-fixture"},
            source="DEMO",
            retrievedAt=timestamp,
        ),
    ]
    return ContextSnapshot(
        latitude=latitude,
        longitude=longitude,
        weather=WeatherContext(
            windSpeedMetersPerSecond=4.5,
            windDirectionFromDegrees=225.0,
            temperatureCelsius=18.0,
            precipitationMillimetersPerHour=0.0,
            precipitationProbabilityPercent=10.0,
            precipitationType="NONE",
            source="DEMO",
            selectedAt=timestamp,
            provider="Demo fixture",
            sampleKind="DEMO",
        ),
        weatherTimeline=[WeatherSample(minutesFromNow=minutes, windSpeedMetersPerSecond=4.5, windDirectionFromDegrees=225.0, temperatureCelsius=18.0, source="DEMO") for minutes in range(0, 121, 5)],
        airQuality=AirQualityContext(source="DEMO", selectedAt=timestamp),
        elevation=ElevationContext(elevationMeters=40.0, source="DEMO", selectedAt=timestamp),
        alerts=[],
        features=features,
        buildings=[],
        provenance={"weather": "DEMO", "airQuality": "DEMO", "elevation": "DEMO", "alerts": "DEMO", "context": "DEMO", "buildings": "DEMO", "routing": "DEMO"},
        warnings=["Context is a demo fixture; verify live conditions before operational use."],
    )


def _provider_cache_dir() -> Path:
    return Path(os.getenv("CONTEXT_CACHE_DIR", str(Path(__file__).resolve().parents[3] / "backend-cache")))


def _provider_url(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


def _cache_ttl_seconds(label: str) -> float | None:
    """Return the freshness window that prevents repeated paid/shared-provider calls."""
    default_ttls = {
        "Weather provider": 300.0,
        "Air-quality provider": 900.0,
        "NOAA alerts provider": 300.0,
        "Elevation provider": 86_400.0,
        "OpenStreetMap context provider": 86_400.0,
        "OpenStreetMap building footprint provider": 86_400.0,
        "OSRM routing provider": 86_400.0,
    }
    override_name = {
        "Weather provider": "WEATHER_CACHE_MAX_AGE_SECONDS",
        "Air-quality provider": "AIR_QUALITY_CACHE_MAX_AGE_SECONDS",
        "NOAA alerts provider": "ALERTS_CACHE_MAX_AGE_SECONDS",
        "Elevation provider": "ELEVATION_CACHE_MAX_AGE_SECONDS",
        "OpenStreetMap context provider": "FEATURES_CACHE_MAX_AGE_SECONDS",
        "OpenStreetMap building footprint provider": "OVERPASS_BUILDING_CACHE_MAX_AGE_SECONDS",
        "OSRM routing provider": "ROUTE_CACHE_MAX_AGE_SECONDS",
    }.get(label, "CONTEXT_CACHE_MAX_AGE_SECONDS")
    raw_value = os.getenv(override_name)
    if raw_value is None:
        return default_ttls.get(label, 900.0)
    try:
        value = float(raw_value)
    except ValueError:
        return default_ttls.get(label, 900.0)
    if label == "Weather provider":
        return min(300.0, max(0.0, value)) if math.isfinite(value) else 300.0
    return None if value < 0 else value


def _coordinate_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.4f}_{longitude:.4f}".replace("-", "m")


def _load_provider_sample(
    url: str,
    cache_path: Path,
    params: dict[str, Any],
    config: ProviderConfig,
    client: httpx.Client | None,
    label: str,
    *,
    max_age_seconds: float | None = None,
) -> tuple[dict[str, Any] | None, Provenance, list[str]]:
    try:
        payload, source, warnings = fetch_json_with_cache(
            url,
            cache_path,
            params=params,
            config=config,
            client=client,
            max_age_seconds=max_age_seconds,
        )
        return payload, source, warnings
    except RuntimeError as error:
        return None, "DEMO", [f"{label} unavailable; using DEMO context: {type(error.__cause__ or error).__name__}."]


_CACHE_WRITE_LOCK = threading.Lock()
_CONTEXT_CACHE_LOCK = threading.Lock()
_CONTEXT_IN_FLIGHT: dict[str, dict[str, Any]] = {}


def get_live_context(
    latitude: float,
    longitude: float,
    *,
    destination_latitude: float | None = None,
    destination_longitude: float | None = None,
    config: ProviderConfig = ProviderConfig(),
    client: httpx.Client | None = None,
) -> ContextSnapshot:
    """Return one shared live snapshot for concurrent callers at the same coordinates."""
    key = f"{latitude:.4f}:{longitude:.4f}:{destination_latitude}:{destination_longitude}"
    with _CONTEXT_CACHE_LOCK:
        entry = _CONTEXT_IN_FLIGHT.get(key)
        if entry is None:
            entry = {"event": threading.Event(), "value": None, "error": None}
            _CONTEXT_IN_FLIGHT[key] = entry
            owner = True
        else:
            owner = False
    if not owner:
        entry["event"].wait()
        if entry["error"] is not None:
            raise entry["error"]
        return entry["value"]  # type: ignore[return-value]
    try:
        value = _get_live_context_uncached(
            latitude,
            longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            config=config,
            client=client,
        )
        entry["value"] = value
        return value
    except BaseException as error:
        entry["error"] = error
        raise
    finally:
        with _CONTEXT_CACHE_LOCK:
            _CONTEXT_IN_FLIGHT.pop(key, None)
            entry["event"].set()


def _noaa_weather_fallback(latitude: float, longitude: float, cache_dir: Path, key: str, config: ProviderConfig, client: httpx.Client | None) -> tuple[dict[str, Any] | None, Provenance]:
    """NOAA hourly model forecast fallback, explicitly not station observations."""
    try:
        points, _, _ = fetch_json_with_cache(f"https://api.weather.gov/points/{latitude:.4f},{longitude:.4f}", cache_dir / f"noaa-points-{key}.json", config=config, client=client, max_age_seconds=86400)
        url = (points.get("properties") or {}).get("forecastHourly", "")
        if not url.startswith("https://api.weather.gov/"):
            return None, "DEMO"
        payload, source, _ = fetch_json_with_cache(url, cache_dir / f"noaa-weather-{key}.json", config=config, client=client, max_age_seconds=300)
        periods = (payload.get("properties") or {}).get("periods") or []
        compass = {name: index * 22.5 for index, name in enumerate(["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"])}
        hourly: dict[str, list[Any]] = {name: [] for name in ["time", "wind_speed_10m", "wind_direction_10m", "temperature_2m"]}
        for period in periods:
            speed_text = str(period.get("windSpeed", "")).split()
            speeds = [float(token) for token in speed_text if token.replace(".", "", 1).isdigit()]
            direction = compass.get(period.get("windDirection"))
            timestamp = _parse_time(period.get("startTime"))
            if not speeds or direction is None or timestamp is None:
                continue
            temperature = float(period["temperature"])
            if period.get("temperatureUnit") == "F":
                temperature = (temperature - 32) * 5 / 9
            hourly["time"].append(timestamp.isoformat())
            hourly["wind_speed_10m"].append(_wind_speed_meters_per_second(sum(speeds) / len(speeds), speed_text[-1]))
            hourly["wind_direction_10m"].append(direction)
            hourly["temperature_2m"].append(temperature)
        if not hourly["time"]:
            return None, "DEMO"
        return {"hourly": hourly, "hourly_units": {"wind_speed_10m": "m/s"}, "_provider": "NOAA hourly forecast", "_cache_name": f"noaa-weather-{key}.json"}, source
    except (RuntimeError, ValueError, TypeError, KeyError):
        return None, "DEMO"


def _get_live_context_uncached(
    latitude: float,
    longitude: float,
    *,
    destination_latitude: float | None = None,
    destination_longitude: float | None = None,
    config: ProviderConfig = ProviderConfig(),
    client: httpx.Client | None = None,
) -> ContextSnapshot:
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise ValueError("coordinates are outside the valid geographic range")
    cache_dir = _provider_cache_dir()
    key = _coordinate_key(latitude, longitude)
    warnings: list[str] = []

    weather_payload, weather_source, weather_warnings = _load_provider_sample(
        f"{_provider_url('OPEN_METEO_BASE_URL', 'https://api.open-meteo.com/v1')}/forecast",
        cache_dir / f"weather-{key}.json",
        {"latitude": latitude, "longitude": longitude, "current": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,rain,snowfall", "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,rain,snowfall,precipitation_probability", "wind_speed_unit": "ms", "timezone": "UTC", "forecast_hours": 4, "past_hours": 1},
        config,
        client,
        "Weather provider",
        max_age_seconds=_cache_ttl_seconds("Weather provider"),
    )
    warnings.extend(weather_warnings)
    if weather_payload is None or weather_warnings:
        fallback_payload, fallback_source = _noaa_weather_fallback(latitude, longitude, cache_dir, key, config, client)
        if fallback_payload is not None and (fallback_source == "LIVE" or weather_payload is None):
            weather_payload, weather_source = fallback_payload, fallback_source
            warnings.append("Primary weather unavailable; using NOAA hourly forecast, not station observations.")
    if weather_payload is None:
        weather_payload = {}
        weather_source = "DEMO"
        warnings.append("Both weather providers unavailable; other context providers are still queried.")
    try:
        weather = normalize_open_meteo(weather_payload, source=weather_source)
        cache_path = cache_dir / weather_payload.get("_cache_name", f"weather-{key}.json")
        retrieved = datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc) if cache_path.exists() else datetime.now(timezone.utc)
        weather.retrievedAt = retrieved.isoformat().replace("+00:00", "Z")
        selected = _parse_time(weather.selectedAt)
        weather.ageSeconds = max(0.0, (datetime.now(timezone.utc) - selected).total_seconds()) if selected else None
        cache_age = (datetime.now(timezone.utc) - retrieved).total_seconds()
        weather.provider = weather_payload.get("_provider", "Open-Meteo")
        allowed_age = 5400 if weather.sampleKind == "FORECAST" else 1800
        weather.stale = selected is None or weather.ageSeconds is None or weather.ageSeconds > allowed_age or cache_age > 300
        if weather.stale:
            weather.source = weather_source = "CACHED"
            warnings.insert(0, "Weather is stale or has no valid provider timestamp; not current observations.")
    except ValueError as error:
        weather = demo_context(latitude, longitude).weather
        weather_source = "DEMO"
        warnings.append(f"Weather normalization failed; using DEMO weather: {error}.")

    air_quality_url = _provider_url("OPEN_METEO_AIR_QUALITY_URL", "https://air-quality-api.open-meteo.com/v1/air-quality")
    if not air_quality_url.rstrip("/").endswith("/air-quality"):
        air_quality_url = f"{air_quality_url.rstrip('/')}/air-quality"
    air_payload, air_source, air_warnings = _load_provider_sample(
        air_quality_url,
        cache_dir / f"air-quality-{key}.json",
        {"latitude": latitude, "longitude": longitude, "current": "pm2_5,pm10,us_aqi,european_aqi,ozone,nitrogen_dioxide", "forecast_days": 1},
        config,
        client,
        "Air-quality provider",
        max_age_seconds=_cache_ttl_seconds("Air-quality provider"),
    )
    warnings.extend(air_warnings)
    air_quality = None
    if air_payload is not None:
        try:
            air_quality = normalize_air_quality(air_payload, source=air_source)
        except ValueError as error:
            warnings.append(f"Air-quality normalization failed: {error}.")

    elevation_payload, elevation_source, elevation_warnings = _load_provider_sample(
        "https://api.open-meteo.com/v1/elevation",
        cache_dir / f"elevation-{key}.json",
        {"latitude": latitude, "longitude": longitude},
        config,
        client,
        "Elevation provider",
        max_age_seconds=_cache_ttl_seconds("Elevation provider"),
    )
    warnings.extend(elevation_warnings)
    elevation = None
    if elevation_payload is not None:
        try:
            elevation = normalize_elevation(elevation_payload, source=elevation_source)
        except ValueError as error:
            warnings.append(f"Elevation normalization failed: {error}.")

    alerts_payload, alerts_source, alerts_warnings = _load_provider_sample(
        f"{_provider_url('NWS_BASE_URL', 'https://api.weather.gov')}/alerts/active",
        cache_dir / f"alerts-{key}.json",
        {"point": f"{latitude},{longitude}"},
        config,
        client,
        "NOAA alerts provider",
        max_age_seconds=_cache_ttl_seconds("NOAA alerts provider"),
    )
    warnings.extend(alerts_warnings)
    alerts = normalize_noaa_alerts(alerts_payload or {"features": []}, source=alerts_source)

    overpass_endpoint = _provider_url("OVERPASS_ENDPOINT", "https://overpass-api.de/api/interpreter")
    features_payload, features_source, features_warnings = _load_provider_sample(
        overpass_endpoint,
        cache_dir / f"features-{key}.json",
        {"data": f"[out:json][timeout:8];(nwr(around:1500,{latitude},{longitude})[amenity~\"^(drinking_water|fountain|school|hospital)$\"];nwr(around:1500,{latitude},{longitude})[emergency=fire_hydrant];way(around:1500,{latitude},{longitude})[highway];);out center tags;"},
        config,
        client,
        "OpenStreetMap context provider",
        max_age_seconds=_cache_ttl_seconds("OpenStreetMap context provider"),
    )
    warnings.extend(features_warnings)
    features = normalize_overpass(features_payload or {"elements": []}, latitude, longitude, source=features_source)
    buildings_payload, buildings_source, buildings_warnings = _load_provider_sample(
        overpass_endpoint,
        cache_dir / f"buildings-{key}.json",
        {"data": f"[out:json][timeout:8];way(around:1500,{latitude},{longitude})[building];out center tags geom;"},
        config,
        client,
        "OpenStreetMap building footprint provider",
        max_age_seconds=_cache_ttl_seconds("OpenStreetMap building footprint provider"),
    )
    warnings.extend(buildings_warnings)
    buildings = normalize_buildings(buildings_payload or {"elements": []}, source=buildings_source)

    route = None
    configured_destination_latitude = os.getenv("DEMO_ROUTE_DESTINATION_LATITUDE")
    configured_destination_longitude = os.getenv("DEMO_ROUTE_DESTINATION_LONGITUDE")
    if destination_latitude is None and configured_destination_latitude:
        destination_latitude = float(configured_destination_latitude)
    if destination_longitude is None and configured_destination_longitude:
        destination_longitude = float(configured_destination_longitude)
    if destination_latitude is not None and destination_longitude is not None:
        try:
            destination_lat = float(destination_latitude)
            destination_lon = float(destination_longitude)
            if not -90.0 <= destination_lat <= 90.0 or not -180.0 <= destination_lon <= 180.0:
                raise ValueError("route destination is outside the valid geographic range")
            route_url = f"{_provider_url('OSRM_BASE_URL', 'https://router.project-osrm.org')}/route/v1/driving/{longitude},{latitude};{destination_lon},{destination_lat}"
            route_payload, route_source, route_warnings = _load_provider_sample(
                route_url,
                cache_dir / f"route-{key}-{_coordinate_key(destination_lat, destination_lon)}.json",
                {"overview": "full", "geometries": "geojson"},
                config,
                client,
                "OSRM routing provider",
                max_age_seconds=_cache_ttl_seconds("OSRM routing provider"),
            )
            warnings.extend(route_warnings)
            if route_payload is not None:
                try:
                    route = normalize_osrm_route(route_payload, latitude, longitude, destination_lat, destination_lon, source=route_source)
                except ValueError as error:
                    warnings.append(f"Routing normalization failed; using straight-line route: {error}.")
            if route is None:
                route = straight_line_route(latitude, longitude, destination_lat, destination_lon, source="DEMO")
        except ValueError:
            warnings.append("Configured route destination is invalid; route omitted.")

    return ContextSnapshot(
        latitude=latitude,
        longitude=longitude,
        weather=weather,
        weatherTimeline=(normalize_weather_timeline(weather_payload, source=weather_source, anchor_at=_now()) or [WeatherSample(minutesFromNow=minutes, windSpeedMetersPerSecond=weather.windSpeedMetersPerSecond, windDirectionFromDegrees=weather.windDirectionFromDegrees, temperatureCelsius=weather.temperatureCelsius, source=weather_source) for minutes in range(0, 121, 5)])[:25],
        airQuality=air_quality,
        elevation=elevation,
        alerts=alerts,
        features=features,
        buildings=buildings,
        route=route,
        provenance={"weather": weather_source, "airQuality": air_source, "elevation": elevation_source, "alerts": alerts_source, "context": features_source, "buildings": buildings_source, "routing": route.source if route is not None else "DEMO"},
        warnings=warnings,
    )


def load_json_cache(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as cache_file:
            value = json.load(cache_file)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_json_cache(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as cache_file:
        json.dump(value, cache_file, indent=2, sort_keys=True)
    os.replace(temporary_path, path)


def provider_headers(config: ProviderConfig = ProviderConfig()) -> dict[str, str]:
    """Return headers required for public providers, including NOAA's User-Agent policy."""
    return {
        "User-Agent": config.user_agent,
        "Accept": "application/geo+json, application/json",
    }


def fetch_json_with_cache(
    url: str,
    cache_path: Path,
    *,
    params: dict[str, Any] | None = None,
    config: ProviderConfig = ProviderConfig(),
    client: httpx.Client | None = None,
    max_age_seconds: float | None = None,
) -> tuple[dict[str, Any], Provenance, list[str]]:
    """Fetch a provider payload, reusing fresh cache and falling back to stale cache on errors."""
    warnings: list[str] = []
    if max_age_seconds is not None and cache_path.exists():
        age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - cache_path.stat().st_mtime)
        if age_seconds <= max_age_seconds:
            cached = load_json_cache(cache_path)
            if cached is not None:
                warnings.append(f"Using cached provider response ({age_seconds:.0f}s old).")
                return cached, "CACHED", warnings
    request_client = client or httpx.Client(timeout=config.timeout_seconds, headers=provider_headers(config))
    close_client = client is None
    try:
        response = request_client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("provider response must be a JSON object")
        with _CACHE_WRITE_LOCK:
            save_json_cache(cache_path, payload)
        return payload, "LIVE", warnings
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
        cached = load_json_cache(cache_path)
        if cached is not None:
            warnings.append(f"Provider unavailable; using cached response: {type(error).__name__}.")
            return cached, "CACHED", warnings
        raise RuntimeError("provider failed and no cached response is available") from error
    finally:
        if close_client:
            request_client.close()
