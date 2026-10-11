from __future__ import annotations

import os
import random
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from math import ceil, cos, exp, log, pi, radians, sin, sqrt
from typing import Literal

import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

from app.services.agent import process_dispatch
from app.services.context import BuildingFootprint, ContextSnapshot, ContextFeature, WeatherSample, demo_context, get_live_context
from app.services.map_guard import acquire_map_session
from app.services.voice import synthesize_dispatch
from app.services.units import Unit, apply_property_assignment, apply_unit_deployment


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


Band = Literal["UNKNOWN", "TRACE", "PEL", "IDLH"]
TerrainFeatureKind = Literal["BUILDING", "TERRAIN_RIDGE", "VEGETATION"]
ReleaseMode = Literal["CONTINUOUS", "IMPULSIVE", "CONTINUOUS_THEN_IMPULSIVE"]


class GasComponent(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(default="CHEMICAL", min_length=1, max_length=40)
    massFraction: float = Field(gt=0.0, le=1.0)
    densityRelativeToAir: float = Field(gt=0.0, le=20.0)
    traceThreshold: float = Field(0.5, ge=0.0)
    pelThreshold: float = Field(1.0, ge=0.0)
    idlhThreshold: float = Field(10.0, ge=0.0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "GasComponent":
        if not self.traceThreshold <= self.pelThreshold <= self.idlhThreshold:
            raise ValueError("gas component thresholds must be ordered TRACE <= PEL <= IDLH")
        return self


class Location(BaseModel):
    # Princeton Middle School campus centroid, 217 Walnut Lane, Princeton, NJ.
    # Coordinates sourced from OpenStreetMap (relation 8787986, queried 2026-10-11).
    latitude: float = Field(40.360556, ge=-90.0, le=90.0)
    longitude: float = Field(-74.6542123, ge=-180.0, le=180.0)
    label: str = "Princeton Middle School · 217 Walnut Lane, Princeton NJ"


class PlumeTrajectoryPoint(BaseModel):
    """A five-minute, world-coordinate sample for 3D plume renderers."""

    timeMinutes: int = Field(ge=0, le=120)
    longitude: float
    latitude: float
    altitudeMeters: float = Field(ge=0.0)
    concentration: float = Field(ge=0.0)
    band: Band
    radiusMeters: float = Field(gt=0.0)


class Hazard(BaseModel):
    name: str = "Chlorine gas"
    category: str = "CHEMICAL"
    molecularWeightGPerMol: float | None = Field(default=70.90, gt=0.0, le=1_000.0)
    densityRelativeToAir: float = Field(2.47, gt=0.0, le=20.0)
    decayHalfLifeMinutes: float | None = Field(default=None, gt=0.0, le=10_000_000.0)
    settlingVelocityMetersPerSecond: float = Field(0.0, ge=0.0, le=10.0)
    depositionVelocityMetersPerSecond: float = Field(0.0, ge=0.0, le=1.0)
    traceThreshold: float = Field(0.5, ge=0.0)
    pelThreshold: float = Field(1.0, ge=0.0)
    idlhThreshold: float = Field(10.0, ge=0.0)
    surfaceDepositionPotential: bool = True
    surfaceRetentionFraction: float = Field(0.15, ge=0.0, le=1.0)
    surfacePersistenceMinutes: int = Field(90, ge=0, le=1_000_000)
    surfaceFateNote: str = "Reactive gas; moisture and surfaces can consume or retain material. Do not infer cleanup method from this flag."

    @model_validator(mode="after")
    def validate_thresholds(self) -> "Hazard":
        if not self.traceThreshold <= self.pelThreshold <= self.idlhThreshold:
            raise ValueError("hazard thresholds must be ordered TRACE <= PEL <= IDLH")
        return self


class Release(BaseModel):
    # Demo default is a ten-kilogram continuous release over 30 minutes.
    # Keeping rate * duration explicit preserves the continuous-release API.
    rateKgPerSecond: float = Field(10.0 / (30.0 * 60.0), ge=0.0, le=1000.0)
    durationMinutes: int = Field(30, ge=1, le=240)
    sourceHeightMeters: float = Field(1.5, ge=0.0, le=100.0)
    mode: ReleaseMode = "CONTINUOUS"
    impulseMassKg: float = Field(0.0, ge=0.0, le=100_000.0)
    impulseTimeMinutes: int = Field(0, ge=0, le=120)
    isPressurized: bool = True
    hasExploded: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "Release":
        if self.mode in {"IMPULSIVE", "CONTINUOUS_THEN_IMPULSIVE"} and self.impulseMassKg <= 0.0:
            raise ValueError("impulseMassKg must be positive for an impulsive release")
        return self


class Weather(BaseModel):
    windSpeedMetersPerSecond: float = Field(4.5, ge=0.0, le=80.0)
    windDirectionFromDegrees: float = Field(225.0, ge=0.0, le=360.0)
    temperatureCelsius: float = 18.0
    precipitationMillimetersPerHour: float = Field(0.0, ge=0.0, le=500.0)
    precipitationProbabilityPercent: float | None = Field(default=None, ge=0.0, le=100.0)
    precipitationType: Literal["NONE", "RAIN", "SNOW", "MIXED"] = "NONE"
    pasquillStabilityClass: Literal["A", "B", "C", "D", "E", "F", "G"] = "D"
    source: str = "DEMO"


class TerrainFeature(BaseModel):
    featureId: str
    kind: TerrainFeatureKind
    eastMeters: float = Field(ge=-2000.0, le=2000.0)
    northMeters: float = Field(ge=-2000.0, le=2000.0)
    radiusMeters: float = Field(gt=0.0, le=500.0)
    heightMeters: float = Field(ge=0.0, le=300.0)
    porosity: float = Field(0.0, ge=0.0, le=1.0)


class Scenario(BaseModel):
    scenarioId: str = "INC-8892"
    version: int = 1
    incidentStartedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: Location = Location()
    # Optional source pin; location remains the incident/map center for old clients.
    sourceLocation: Location | None = None
    hazard: Hazard = Hazard()
    gases: list[GasComponent] = Field(default_factory=list, max_length=8)
    release: Release = Release()
    weather: Weather = Weather()
    weatherTimeline: list[WeatherSample] = Field(default_factory=list, max_length=25)
    terrainFeatures: list[TerrainFeature] = Field(default_factory=list, max_length=100)
    activeUnits: list[Unit] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_gases(self) -> "Scenario":
        if self.gases and abs(sum(gas.massFraction for gas in self.gases) - 1.0) > 0.01:
            raise ValueError("gas component mass fractions must sum to 1.0")
        return self


class ScenarioPatch(BaseModel):
    scenario: Scenario
    context: ContextSnapshot | None = None


class ExposureMetrics(BaseModel):
    longitude: float
    latitude: float
    polygon: list[list[float]]
    peakConcentration: float = Field(ge=0.0)
    meanConcentration: float = Field(ge=0.0)
    timeIntegratedConcentration: float = Field(ge=0.0)
    cumulativeTimeIntegratedConcentration: list[float]
    band: Band
    color: str


class BuildingExposure(ExposureMetrics):
    footprintId: str
    displayName: str


class GridExposure(ExposureMetrics):
    cellId: str
    displayName: str


class ExposureDomain(BaseModel):
    bounds: dict[str, float]
    localBoundsMeters: dict[str, float]
    resolutionMeters: float
    minResolutionMeters: float = 50.0
    maxResolutionMeters: float = 2000.0
    maxDistanceFromSourcePerAxisMeters: float = 20_000.0
    maxCells: int = 400
    maxBuildings: int = 250
    truncated: bool
    truncationReasons: list[str]
    buildingsOutsideGrid: int


class ExposureResponse(BaseModel):
    scenarioId: str
    scenarioVersion: int
    location: Location
    sourceLocation: Location
    startMinutes: int = 0
    endMinutes: int = 120
    startAt: str
    endAt: str
    timeStepMinutes: int = 5
    sampleCount: int = 25
    breathingHeightMeters: float = 2.0
    concentrationUnit: str
    exposureUnit: str
    thresholds: dict[str, float]
    colorBasis: Literal["MEAN_CONCENTRATION"] = "MEAN_CONCENTRATION"
    buildings: list[BuildingExposure]
    areas: list[GridExposure]
    gridResolutionMeters: float
    domainTruncated: bool
    domain: ExposureDomain
    dataAvailability: dict[str, str]
    assumptions: list[str]
    disclaimer: str


class ManualScenarioUpdate(BaseModel):
    """Validated manual controls for updating a scenario without an LLM."""

    scenario: Scenario


class PlumeParticle(BaseModel):
    longitude: float
    latitude: float
    altitudeMeters: float
    radiusMeters: float
    concentration: float
    band: Band
    opacity: float
    massKg: float = Field(default=0.0, ge=0.0)
    density: float = Field(default=0.0, ge=0.0)
    parentId: int = Field(default=-1, ge=-1)
    clusterId: int = Field(default=-1, ge=-1)
    mergeRadiusMeters: float = Field(default=0.0, ge=0.0)


class PlumeVolume(BaseModel):
    longitude: float
    latitude: float
    groundElevationMeters: float
    heightMeters: float
    radiusMeters: float
    concentration: float
    band: Band
    opacity: float


class SurfaceZone(BaseModel):
    zoneId: str
    longitude: float
    latitude: float
    radiusMeters: float
    surfaceLoading: float = Field(ge=0.0)
    persistenceRemainingMinutes: int = Field(ge=0)
    affectedSurface: Literal["GROUND", "BUILDING_FACADE", "ROOF", "VEGETATION"]
    sanitationStatus: Literal["CANDIDATE_REVIEW"] = "CANDIDATE_REVIEW"
    warning: str = "Simulated candidate zone; confirm with sampling and qualified incident guidance."


class BuildingContamination(BaseModel):
    footprintId: str
    displayName: str
    polygon: list[list[float]]
    levels: int | None
    buildingType: str
    concentration: float = Field(ge=0.0)
    band: Band
    opacity: float = Field(ge=0.0, le=1.0)
    affected: bool = False
    affectedColor: str = "#64748b"


class PropertyAffectedColor(BaseModel):
    """Stable property coloring data for map layers."""

    footprintId: str
    color: str
    band: Band
    concentration: float = Field(ge=0.0)
    affected: bool


class PlumeFrame(BaseModel):
    scenarioId: str
    scenarioVersion: int
    timeMinutes: int
    sourceLocation: Location
    particles: list[PlumeParticle]
    volumeCells: list[PlumeVolume]
    trajectory: list[PlumeTrajectoryPoint] = Field(default_factory=list, max_length=25)
    buildingContamination: list[BuildingContamination] = Field(default_factory=list, max_length=250)
    propertyAffectedColors: list[PropertyAffectedColor] = Field(default_factory=list, max_length=250)
    surfaceZones: list[SurfaceZone] = Field(default_factory=list, max_length=100)
    maxConcentration: float
    affectedAreaSqKm: float = Field(default=0.0, ge=0.0)
    populationAtRisk: int | None = Field(default=None, ge=0)
    concentrationUnit: str = "ppm"
    metricsBasis: str = "Approximate puff field; area is thresholded 50 m grid coverage; population unavailable."
    thresholds: dict[str, float] = Field(default_factory=dict)
    windVectors: list[dict[str, float | bool]] = Field(default_factory=list, max_length=49)
    releasedMassKg: float = Field(default=0.0, ge=0.0)
    isApproximation: bool = True
    assumptions: list[str]


class DispatchRequest(BaseModel):
    timeMinutes: int = Field(default=30, ge=0, le=120)
    text: str = Field(min_length=1, max_length=1000)
    scenario: Scenario
    context: ContextSnapshot | None = None


class BootstrapResponse(BaseModel):
    """Single request contract for the initial, weather-aware projection."""

    scenario: Scenario
    context: ContextSnapshot
    frame: PlumeFrame
    map: dict[str, object]


class ActionPlan(BaseModel):
    planId: str
    scenarioId: str
    generatedAt: str
    modelId: str = "deterministic-action-plan-v1"
    hazardSeverity: Literal["UNKNOWN", "ADVISORY", "CRITICAL"]
    immediateActions: list[str] = Field(min_length=1, max_length=8)
    firstResponderPpe: list[str] = Field(min_length=1, max_length=6)
    isolationRadiusMeters: float = Field(ge=0.0, le=10_000.0)
    shelterGuidance: str
    decontaminationGuidance: str
    nearbyContextUsed: list[str] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(min_length=1, max_length=12)
    provenance: dict[str, Literal["LIVE", "CACHED", "DEMO", "UNKNOWN"]]
    disclaimer: str


class DispatchResponse(BaseModel):
    assistantText: str
    scenario: Scenario
    frame: PlumeFrame
    commands: list[dict[str, str | None]] = Field(default_factory=list)
    clarifyingQuestions: list[str] = Field(default_factory=list, max_length=3)
    actionPlan: ActionPlan
    confidence: str
    provider: str
    audio: dict[str, str | None]


app = FastAPI(title="Aero-Hazard Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
audio_cache_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "audio-cache"
audio_cache_dir.mkdir(parents=True, exist_ok=True)
app.mount("/audio-cache", StaticFiles(directory=audio_cache_dir), name="audio-cache")


HAZARD_LIBRARY: dict[str, Hazard] = {
    "chlorine": Hazard(name="Chlorine gas", category="CHEMICAL", molecularWeightGPerMol=70.90, densityRelativeToAir=2.47, traceThreshold=0.5, pelThreshold=1.0, idlhThreshold=10.0, surfaceDepositionPotential=True, surfaceRetentionFraction=0.15, surfacePersistenceMinutes=90, surfaceFateNote="Reactive gas; moisture and surfaces can consume or retain material. Do not infer cleanup method from this flag."),
    "ammonia": Hazard(name="Ammonia", category="CHEMICAL", molecularWeightGPerMol=17.03, densityRelativeToAir=0.60, traceThreshold=0.5, pelThreshold=25.0, idlhThreshold=300.0, surfaceDepositionPotential=True, surfaceRetentionFraction=0.10, surfacePersistenceMinutes=60, surfaceFateNote="Water films and acidic materials can retain or react with ammonia."),
    "methane": Hazard(name="Methane", category="CHEMICAL", molecularWeightGPerMol=16.04, densityRelativeToAir=0.55, traceThreshold=1.0, pelThreshold=5.0, idlhThreshold=10.0, surfaceFateNote="Volatile gas; no persistent surface loading modeled."),
    "iodine-131": Hazard(name="Iodine-131 aerosol", category="RADIOLOGICAL", molecularWeightGPerMol=131.90, densityRelativeToAir=4.94, settlingVelocityMetersPerSecond=0.01, depositionVelocityMetersPerSecond=0.005, traceThreshold=0.1, pelThreshold=0.5, idlhThreshold=5.0, surfaceDepositionPotential=True, surfaceRetentionFraction=0.70, surfacePersistenceMinutes=10080, surfaceFateNote="Particle/deposition behavior can leave persistent contamination; clearance requires radiological survey."),
    "cesium-137": Hazard(name="Cesium-137 aerosol", category="RADIOLOGICAL", molecularWeightGPerMol=132.91, settlingVelocityMetersPerSecond=0.01, depositionVelocityMetersPerSecond=0.005, densityRelativeToAir=4.65, traceThreshold=0.1, pelThreshold=0.5, idlhThreshold=5.0, surfaceDepositionPotential=True, surfaceRetentionFraction=0.80, surfacePersistenceMinutes=43200, surfaceFateNote="Aerosol deposition can persist on surfaces; clearance requires radiological survey."),
    "anthrax": Hazard(name="Anthrax aerosol", category="BIOLOGICAL", molecularWeightGPerMol=None, settlingVelocityMetersPerSecond=0.005, depositionVelocityMetersPerSecond=0.003, densityRelativeToAir=1.0, traceThreshold=0.1, pelThreshold=1.0, idlhThreshold=5.0, surfaceDepositionPotential=True, surfaceRetentionFraction=0.65, surfacePersistenceMinutes=1440, surfaceFateNote="Particle deposition may contaminate surfaces; follow qualified public-health protocols."),
}


STABILITY_COEFFICIENTS = {
    "A": ((0.22, 0.0001, -0.5), (0.20, 0.0, 0.0)),
    "B": ((0.16, 0.0001, -0.5), (0.12, 0.0, 0.0)),
    "C": ((0.11, 0.0001, -0.5), (0.08, 0.0002, -0.5)),
    "D": ((0.08, 0.0001, -0.5), (0.06, 0.0015, -0.5)),
    "E": ((0.06, 0.0001, -0.5), (0.03, 0.0003, -1.0)),
    "F": ((0.04, 0.0001, -0.5), (0.016, 0.0003, -1.0)),
    "G": ((0.03, 0.0001, -0.5), (0.012, 0.0003, -1.0)),
}


def dispersion_coefficients(scenario: Scenario, downwind_meters: float) -> tuple[float, float]:
    """Return bounded Pasquill-Gifford sigma-y and sigma-z values in meters."""
    lateral, vertical = STABILITY_COEFFICIENTS[scenario.weather.pasquillStabilityClass]
    distance = max(1.0, downwind_meters)
    sigma_y = max(2.0, lateral[0] * distance * (1 + lateral[1] * distance) ** lateral[2])
    sigma_z = max(2.0, vertical[0] * distance * (1 + vertical[1] * distance) ** vertical[2])
    return sigma_y, sigma_z


def _terrain_obstruction(scenario: Scenario, east_meters: float, north_meters: float, altitude_meters: float) -> tuple[float, float]:
    """Return concentration multiplier and wake-spread multiplier for a sample."""
    multiplier = 1.0
    wake_spread = 1.0
    for feature in scenario.terrainFeatures:
        distance = sqrt((east_meters - feature.eastMeters) ** 2 + (north_meters - feature.northMeters) ** 2)
        if distance > feature.radiusMeters:
            continue
        if altitude_meters > feature.heightMeters:
            continue
        # Buildings and ridges create a residual wake, not an impossible hard wall.
        coverage = max(0.0, 1.0 - distance / feature.radiusMeters)
        blocking = (1.0 - feature.porosity) * coverage
        multiplier *= 1.0 - (0.55 if feature.kind == "BUILDING" else 0.40) * blocking
        wake_spread *= 1.0 + 0.75 * blocking
    return max(0.15, multiplier), min(3.0, wake_spread)


def _gas_components(scenario: Scenario) -> list[GasComponent]:
    if scenario.gases:
        return scenario.gases
    hazard = scenario.hazard
    return [GasComponent(name=hazard.name, category=hazard.category, massFraction=1.0, densityRelativeToAir=hazard.densityRelativeToAir, traceThreshold=hazard.traceThreshold, pelThreshold=hazard.pelThreshold, idlhThreshold=hazard.idlhThreshold)]


def _mixture_property(scenario: Scenario, property_name: str) -> float:
    return sum(component.massFraction * getattr(component, property_name) for component in _gas_components(scenario))


def plume_rise_meters(scenario: Scenario) -> float:
    """Approximate buoyant/pressurized rise without modeling a full jet."""
    pressure_factor = 1.35 if scenario.release.isPressurized else 1.0
    heat_factor = 1.25 if scenario.release.hasExploded else 1.0
    buoyancy_factor = max(0.55, 1.0 / sqrt(max(0.5, _mixture_property(scenario, "densityRelativeToAir"))))
    return scenario.release.sourceHeightMeters + 3.0 * pressure_factor * heat_factor * buoyancy_factor


def _release_mass_rate(scenario: Scenario, time_minutes: float) -> float:
    release = scenario.release
    continuous = release.rateKgPerSecond if release.mode in {"CONTINUOUS", "CONTINUOUS_THEN_IMPULSIVE"} and time_minutes <= release.durationMinutes else 0.0
    impulse = 0.0
    if release.mode in {"IMPULSIVE", "CONTINUOUS_THEN_IMPULSIVE"}:
        # Represent the finite-duration impulse as a normalized Gaussian pulse.
        # Its integral over time is impulseMassKg, unlike an unbounded 1/t tail.
        pulse_sigma_seconds = 30.0
        seconds_from_impulse = (time_minutes - release.impulseTimeMinutes) * 60.0
        impulse = release.impulseMassKg / (pulse_sigma_seconds * sqrt(2.0 * pi)) * exp(
            -0.5 * (seconds_from_impulse / pulse_sigma_seconds) ** 2
        )
    return continuous + impulse


def concentration_at(
    scenario: Scenario,
    time_minutes: int,
    downwind_meters: float,
    crosswind_meters: float,
    altitude_meters: float,
    east_meters: float = 0.0,
    north_meters: float = 0.0,
) -> float:
    """Estimate concentration with Gaussian transport, reflection, and bounded wakes."""
    wind_sample = _weather_sample_at(scenario, time_minutes)
    wind_speed = max(0.5, wind_sample.windSpeedMetersPerSecond)
    elapsed_seconds = max(1.0, time_minutes * 60.0)
    release_seconds = scenario.release.durationMinutes * 60.0
    if downwind_meters <= 0:
        return 0.0
    sigma_y, sigma_z = dispersion_coefficients(scenario, downwind_meters)
    obstruction_multiplier, wake_spread = _terrain_obstruction(scenario, east_meters, north_meters, altitude_meters)
    sigma_y *= wake_spread
    sigma_z *= 1.0 + (wake_spread - 1.0) * 0.5
    effective_height = plume_rise_meters(scenario)

    # A finite puff remains visible after shutoff, but decays as it moves away
    # from the last active source position.
    active_window = min(elapsed_seconds, release_seconds)
    trailing_seconds = max(0.0, elapsed_seconds - release_seconds)
    duration_factor = min(1.0, active_window / max(1.0, release_seconds))
    trailing_factor = exp(-trailing_seconds / max(60.0, release_seconds * 0.8))
    emission_rate = _release_mass_rate(scenario, time_minutes) * trailing_factor
    if scenario.release.mode == "IMPULSIVE" and time_minutes < scenario.release.impulseTimeMinutes:
        emission_rate = 0.0

    lateral_term = exp(-0.5 * (crosswind_meters / sigma_y) ** 2)
    vertical_term = exp(-0.5 * ((altitude_meters - effective_height) / sigma_z) ** 2)
    ground_reflection = exp(-0.5 * ((altitude_meters + effective_height) / sigma_z) ** 2)
    normalization = emission_rate / (2.0 * pi * wind_speed * sigma_y * sigma_z)
    density_ratio = _mixture_property(scenario, "densityRelativeToAir")
    dense_gas_factor = 1.0 + max(0.0, density_ratio - 1.0) * 0.18
    light_gas_factor = 1.0 + max(0.0, 1.0 - density_ratio) * 0.10
    # Precipitation scavenges airborne material. This bounded wet-deposition
    # approximation is intentionally conservative and is not a cleanup model.
    precipitation_rate = scenario.weather.precipitationMillimetersPerHour
    if precipitation_rate > 0.0:
        rain_scavenging = min(0.85, 0.06 * sqrt(precipitation_rate))
        if scenario.weather.precipitationType == "SNOW":
            rain_scavenging *= 0.45
        elif scenario.weather.precipitationType == "MIXED":
            rain_scavenging *= 0.75
        wet_scavenging_factor = 1.0 - rain_scavenging
    else:
        wet_scavenging_factor = 1.0
    decay_factor = 1.0
    if scenario.hazard.decayHalfLifeMinutes is not None:
        decay_factor *= 0.5 ** (max(0.0, time_minutes) / scenario.hazard.decayHalfLifeMinutes)
    settling_factor = exp(-scenario.hazard.settlingVelocityMetersPerSecond * max(0.0, time_minutes * 60.0) / max(20.0, sigma_z * 8.0))
    mass_concentration_kg_per_m3 = max(0.0, normalization * lateral_term * (vertical_term + ground_reflection) * dense_gas_factor * light_gas_factor * obstruction_multiplier * wet_scavenging_factor * decay_factor * settling_factor)
    # Convert the transport solver's kg/m³ result to ppm by the ideal-gas law.
    # Thresholds in the hazard library are ppm, so this keeps a 10 kg release
    # numerically consistent instead of multiplying by an arbitrary display scale.
    molecular_weight_kg_per_mol = max(0.001, (scenario.hazard.molecularWeightGPerMol or 29.0) / 1000.0)
    molar_volume_m3_per_mol = 8.314462618 * (wind_sample.temperatureCelsius + 273.15) / 101_325.0
    return max(0.0, mass_concentration_kg_per_m3 / molecular_weight_kg_per_mol * molar_volume_m3_per_mol * 1_000_000.0)


def band_for(scenario: Scenario, concentration: float) -> Band:
    if concentration <= 0.0 or concentration < scenario.hazard.traceThreshold:
        return "UNKNOWN"
    if concentration >= scenario.hazard.idlhThreshold:
        return "IDLH"
    if concentration >= scenario.hazard.pelThreshold:
        return "PEL"
    return "TRACE"


def _surface_zones(scenario: Scenario, particles: list[PlumeParticle], time_minutes: int) -> list[SurfaceZone]:
    if not scenario.hazard.surfaceDepositionPotential or scenario.hazard.surfaceRetentionFraction <= 0.0:
        return []
    remaining = max(0, scenario.hazard.surfacePersistenceMinutes - max(0, time_minutes))
    zones: list[SurfaceZone] = []
    for index, particle in enumerate(particles[:24]):
        if particle.concentration <= 0.0:
            continue
        affected_surface: Literal["GROUND", "BUILDING_FACADE", "ROOF", "VEGETATION"] = "GROUND"
        if scenario.terrainFeatures:
            feature = min(
                scenario.terrainFeatures,
                key=lambda candidate: sqrt(
                    (candidate.eastMeters) ** 2 + (candidate.northMeters) ** 2
                ),
            )
            if feature.kind == "BUILDING":
                affected_surface = "BUILDING_FACADE"
            elif feature.kind == "VEGETATION":
                affected_surface = "VEGETATION"
        zones.append(
            SurfaceZone(
                zoneId=f"surface-{scenario.scenarioId}-{time_minutes}-{index}",
                longitude=particle.longitude,
                latitude=particle.latitude,
                radiusMeters=max(8.0, particle.radiusMeters),
                surfaceLoading=particle.concentration * scenario.hazard.surfaceRetentionFraction,
                persistenceRemainingMinutes=remaining,
                affectedSurface=affected_surface,
            )
        )
    return zones[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _action_plan_severity(scenario: Scenario, frame: PlumeFrame) -> Literal["UNKNOWN", "ADVISORY", "CRITICAL"]:
    if frame.maxConcentration >= scenario.hazard.idlhThreshold or scenario.release.hasExploded:
        return "CRITICAL"
    if frame.maxConcentration > scenario.hazard.traceThreshold:
        return "ADVISORY"
    return "UNKNOWN"


def build_action_plan(scenario: Scenario, frame: PlumeFrame, context: ContextSnapshot | None = None) -> ActionPlan:
    severity = _action_plan_severity(scenario, frame)
    radius = max((particle.radiusMeters for particle in frame.particles if particle.band in {"PEL", "IDLH"}), default=0.0)
    actions = [
        "Keep responders and bystanders upwind and outside the simulated plume boundary.",
        "Confirm the hazard identity, release status, wind, and source location before operational decisions.",
        "Treat this output as a planning aid and verify conditions with qualified incident personnel and field measurements.",
    ]
    if severity == "CRITICAL":
        actions.insert(0, "Escalate to incident command and restrict access to the simulated high-concentration area.")
    elif severity == "UNKNOWN":
        actions.insert(0, "Maintain a conservative posture because the selected frame is below the modeled trace threshold.")
    ppe = ["Use responder PPE selected by qualified HAZMAT leadership for the confirmed hazard."]
    if scenario.hazard.category == "RADIOLOGICAL":
        ppe.append("Use radiological dosimetry and contamination controls only under qualified radiological direction.")
    elif scenario.hazard.category == "BIOLOGICAL":
        ppe.append("Use public-health and biological-response protocols after hazard confirmation.")
    else:
        ppe.append("Do not infer a respirator or chemical-protection level from this simulation alone.")
    shelter = "Shelter or evacuate only according to qualified incident command guidance; use the modeled wind direction as an assumption, not a guarantee."
    if scenario.weather.precipitationMillimetersPerHour > 0:
        shelter += " Precipitation may reduce airborne concentration while increasing deposition; do not treat rainfall as decontamination."
    decontamination = "No cleanup method is generated. Surface impact indicators require field confirmation before reopening or remediation."
    if not scenario.hazard.surfaceDepositionPotential:
        decontamination = "No persistent surface impact is modeled for this hazard; verify conditions before reopening areas."
    nearby: list[str] = []
    provenance: dict[str, Literal["LIVE", "CACHED", "DEMO", "UNKNOWN"]] = {"scenario": "DEMO", "weather": "DEMO", "context": "UNKNOWN"}
    if context is not None:
        provenance["weather"] = context.provenance.get("weather", "UNKNOWN")
        provenance["context"] = context.provenance.get("context", "UNKNOWN")
        for feature in context.features[:12]:
            nearby.append(f"{feature.featureType}: {feature.displayName} ({feature.distanceMeters:.0f} m; {feature.source})")
    return ActionPlan(
        planId=f"plan-{scenario.scenarioId}-{scenario.version}-{frame.timeMinutes}",
        scenarioId=scenario.scenarioId,
        generatedAt=_utc_now(),
        hazardSeverity=severity,
        immediateActions=actions,
        firstResponderPpe=ppe,
        isolationRadiusMeters=min(10_000.0, radius),
        shelterGuidance=shelter,
        decontaminationGuidance=decontamination,
        nearbyContextUsed=nearby,
        assumptions=["Operational plume estimate generated from the active incident inputs."],
        provenance=provenance,
        disclaimer="SIMULATION ONLY: not an emergency authority, medical assessment, PPE selection, evacuation order, or decontamination procedure.",
    )


def _source_location(scenario: Scenario) -> Location:
    return scenario.sourceLocation or scenario.location


def _band_color(band: Band) -> str:
    return {
        "UNKNOWN": "#64748b",
        "TRACE": "#facc15",
        "PEL": "#f97316",
        "IDLH": "#dc2626",
    }[band]


def _advected_position(scenario: Scenario, time_minutes: float, distance_limit: float | None = None) -> tuple[float, float]:
    """Integrate wind vectors over five-minute intervals, not a final-wind tangent."""
    target_time = max(0.0, time_minutes)
    east_meters = 0.0
    north_meters = 0.0
    travelled = 0.0
    for start in range(0, int(target_time), 5):
        segment_minutes = min(5.0, target_time - start)
        sample = _weather_sample_at(scenario, start + segment_minutes / 2.0)
        distance = max(0.0, sample.windSpeedMetersPerSecond) * segment_minutes * 60.0
        if distance_limit is not None:
            distance = min(distance, max(0.0, distance_limit - travelled))
        direction = radians((sample.windDirectionFromDegrees + 180.0) % 360.0)
        east_meters += sin(direction) * distance
        north_meters += cos(direction) * distance
        travelled += distance
        if distance_limit is not None and travelled >= distance_limit:
            break
    return east_meters, north_meters


def _weather_sample_at(scenario: Scenario, time_minutes: float) -> WeatherSample:
    samples = sorted(scenario.weatherTimeline, key=lambda sample: sample.minutesFromNow)
    if not samples:
        return WeatherSample(minutesFromNow=round(time_minutes), windSpeedMetersPerSecond=scenario.weather.windSpeedMetersPerSecond, windDirectionFromDegrees=scenario.weather.windDirectionFromDegrees, temperatureCelsius=scenario.weather.temperatureCelsius, source="DEMO" if scenario.weather.source == "DEMO" else "CACHED")
    if time_minutes <= samples[0].minutesFromNow:
        return samples[0]
    if time_minutes >= samples[-1].minutesFromNow:
        return samples[-1]
    before = samples[0]
    after = samples[-1]
    for candidate in samples[1:]:
        if candidate.minutesFromNow >= time_minutes:
            after = candidate
            break
        before = candidate
    span = max(1, after.minutesFromNow - before.minutesFromNow)
    fraction = (time_minutes - before.minutesFromNow) / span
    direction_delta = (after.windDirectionFromDegrees - before.windDirectionFromDegrees + 540) % 360 - 180
    return WeatherSample(
        minutesFromNow=round(time_minutes),
        windSpeedMetersPerSecond=before.windSpeedMetersPerSecond + (after.windSpeedMetersPerSecond - before.windSpeedMetersPerSecond) * fraction,
        windDirectionFromDegrees=(before.windDirectionFromDegrees + direction_delta * fraction) % 360,
        temperatureCelsius=before.temperatureCelsius + (after.temperatureCelsius - before.temperatureCelsius) * fraction,
        source=before.source,
    )


def _local_wind(scenario: Scenario, minute: float, east: float, north: float, altitude: float, baseline: tuple[float, float] | None = None) -> tuple[float, float]:
    """Bounded obstacle deflection, not resolved CFD or measured local wind."""
    if baseline is None:
        sample = _weather_sample_at(scenario, minute)
        angle = radians((sample.windDirectionFromDegrees + 180) % 360)
        baseline = sin(angle) * sample.windSpeedMetersPerSecond, cos(angle) * sample.windSpeedMetersPerSecond
    vx, vy = baseline
    for feature in scenario.terrainFeatures:
        if altitude > feature.heightMeters:
            continue
        dx, dy = east - feature.eastMeters, north - feature.northMeters
        influence = feature.radiusMeters * 2.0
        if abs(dx) >= influence or abs(dy) >= influence:
            continue
        distance = sqrt(dx * dx + dy * dy)
        if distance >= influence or distance < 0.1:
            continue
        strength = (1 - distance / influence) * (1 - feature.porosity) * 0.65
        nx, ny = dx / distance, dy / distance
        inward = min(0.0, vx * nx + vy * ny)
        vx -= inward * nx * strength
        vy -= inward * ny * strength
        vx *= 1 - strength * 0.15
        vy *= 1 - strength * 0.15
    return vx, vy


def _transport_scenario(scenario: Scenario, context: ContextSnapshot | None) -> Scenario:
    if context is None or not context.buildings:
        return scenario
    result = scenario.model_copy(deep=True)
    source = _source_location(scenario)
    for building in context.buildings[:max(0, 100 - len(result.terrainFeatures))]:
        east = (building.longitude - source.longitude) * 111_320 * cos(radians(source.latitude))
        north = (building.latitude - source.latitude) * 111_320
        if abs(east) > 2000 or abs(north) > 2000:
            continue
        radius = max((sqrt(((point[0] - building.longitude) * 111_320 * cos(radians(source.latitude))) ** 2 + ((point[1] - building.latitude) * 111_320) ** 2) for point in building.polygon), default=12.0)
        result.terrainFeatures.append(TerrainFeature(featureId=building.footprintId, kind="BUILDING", eastMeters=east, northMeters=north, radiusMeters=min(500, max(5, radius)), heightMeters=(building.levels or 2) * 3.0))
    return result


@dataclass
class _PuffTransportHistory:
    # Request-local reuse for increasing sample times; never shared across scenarios.
    positions: dict[float, tuple[float, float, float, float]] = field(default_factory=dict)


def _puff_state(scenario: Scenario, time_minutes: int, history: _PuffTransportHistory | None = None) -> list[dict[str, float]]:
    """One-minute mass parcels retain their world positions as later winds change."""
    release = scenario.release
    emissions: list[tuple[float, float]] = []
    if release.mode != "IMPULSIVE":
        for minute in range(min(time_minutes, release.durationMinutes)):
            emissions.append((minute + 0.5, release.rateKgPerSecond * 60))
    if release.mode != "CONTINUOUS" and time_minutes >= release.impulseTimeMinutes:
        emissions.append((float(release.impulseTimeMinutes), release.impulseMassKg))
    puffs: list[dict[str, float]] = []
    height = plume_rise_meters(scenario)
    pre_explosion_height = height
    if release.hasExploded:
        before_explosion = scenario.model_copy(update={"release": release.model_copy(update={"hasExploded": False})})
        pre_explosion_height = plume_rise_meters(before_explosion)
    winds = {}
    for tick in range(time_minutes * 2):
        minute = tick * 0.5 + 0.25
        sample = _weather_sample_at(scenario, minute)
        angle = radians((sample.windDirectionFromDegrees + 180) % 360)
        winds[tick] = sin(angle) * sample.windSpeedMetersPerSecond, cos(angle) * sample.windSpeedMetersPerSecond
    for emitted, mass in emissions:
        if mass <= 0:
            continue
        puff_height = pre_explosion_height if emitted < release.impulseTimeMinutes else height
        east = north = travelled = 0.0
        minute = emitted
        if history is not None and emitted in history.positions:
            previous = history.positions[emitted]
            if previous[3] <= time_minutes:
                east, north, travelled, minute = previous
        while minute < time_minutes:
            step = min(0.5, time_minutes - minute)
            vx, vy = _local_wind(scenario, minute + step / 2, east, north, puff_height, winds[int(minute * 2)])
            east += vx * step * 60
            north += vy * step * 60
            travelled += sqrt(vx * vx + vy * vy) * step * 60
            minute += step
        if history is not None:
            history.positions[emitted] = east, north, travelled, minute
        age = time_minutes - emitted
        sigma_y, sigma_z = dispersion_coefficients(scenario, max(1, travelled))
        # Finite source size and calm-air diffusion avoid singular instant-release peaks.
        sy = sqrt(sigma_y ** 2 + 64 + age * 20)
        sz = sqrt(sigma_z ** 2 + 16 + age * 4)
        sx = max(sy, 15.0)
        retained = mass
        if scenario.hazard.decayHalfLifeMinutes:
            retained *= 0.5 ** (age / scenario.hazard.decayHalfLifeMinutes)
        retained *= exp(-(scenario.hazard.settlingVelocityMetersPerSecond + scenario.hazard.depositionVelocityMetersPerSecond) * age * 60 / max(20, sz * 8))
        rain_factor = 0.45 if scenario.weather.precipitationType == "SNOW" else 0.75 if scenario.weather.precipitationType == "MIXED" else 1.0
        retained *= exp(-min(0.05, 0.002 * sqrt(scenario.weather.precipitationMillimetersPerHour)) * age * rain_factor)
        puffs.append({"east": east, "north": north, "height": puff_height, "mass": retained, "sx": sx, "sy": sy, "sz": sz, "emitted": emitted})
    return puffs


def _field_concentration(scenario: Scenario, puffs: list[dict[str, float]], east: float, north: float, altitude: float) -> float:
    total = 0.0
    for puff in puffs:
        horizontal = ((east - puff["east"]) / puff["sx"]) ** 2 + ((north - puff["north"]) / puff["sy"]) ** 2
        if horizontal > 36:
            continue
        vertical = exp(-0.5 * ((altitude - puff["height"]) / puff["sz"]) ** 2) + exp(-0.5 * ((altitude + puff["height"]) / puff["sz"]) ** 2)
        total += puff["mass"] * exp(-0.5 * horizontal) * vertical / ((2 * pi) ** 1.5 * puff["sx"] * puff["sy"] * puff["sz"])
    if scenario.hazard.category != "CHEMICAL" or scenario.hazard.molecularWeightGPerMol is None:
        return total * 1_000_000  # kg/m? to mg/m?, not gas ppm or a dose estimate.
    molar_volume = 8.314462618 * (scenario.weather.temperatureCelsius + 273.15) / 101_325
    return total * molar_volume * 1_000_000 / (scenario.hazard.molecularWeightGPerMol / 1000)


def make_frame(scenario: Scenario, time_minutes: int, context: ContextSnapshot | None = None) -> PlumeFrame:
    time_minutes = max(0, min(120, time_minutes))
    scenario = _transport_scenario(scenario, context)
    source = _source_location(scenario)
    longitude_scale = 111_320 * max(0.0001, cos(radians(source.latitude)))
    puffs = _puff_state(scenario, time_minutes)
    particles: list[PlumeParticle] = []
    volumes: list[PlumeVolume] = []
    trajectory: list[PlumeTrajectoryPoint] = []
    count = max(5, min(20, 900 // max(1, len(puffs))))
    for index, puff in enumerate(puffs):
        for child in range(count):
            angle = child * 2.399963
            radius = sqrt(child / count) * 1.8
            east = puff["east"] + cos(angle) * radius * puff["sx"]
            north = puff["north"] + sin(angle) * radius * puff["sy"]
            altitude = max(0.5, puff["height"] + sin(child * 1.7) * puff["sz"])
            value = _field_concentration(scenario, puffs, east, north, altitude)
            density = min(1.0, value / max(0.01, scenario.hazard.idlhThreshold))
            particles.append(PlumeParticle(longitude=source.longitude + east / longitude_scale, latitude=source.latitude + north / 111_320, altitudeMeters=altitude, radiusMeters=max(8, min(180, puff["sy"] * 0.4)), concentration=value, band=band_for(scenario, value), opacity=min(0.85, 0.08 + density * 0.7), massKg=puff["mass"] / count, density=density, parentId=index, clusterId=index, mergeRadiusMeters=puff["sy"]))
    if not particles and time_minutes == 0:
        particles = [PlumeParticle(longitude=source.longitude, latitude=source.latitude, altitudeMeters=plume_rise_meters(scenario), radiusMeters=8, concentration=0, band="UNKNOWN", opacity=0) for _ in range(5)]
    for index in range(min(10, len(puffs))):
        puff = puffs[round(index * (len(puffs) - 1) / max(1, min(10, len(puffs)) - 1))]
        value = _field_concentration(scenario, puffs, puff["east"], puff["north"], puff["height"])
        volumes.append(PlumeVolume(longitude=source.longitude + puff["east"] / longitude_scale, latitude=source.latitude + puff["north"] / 111_320, groundElevationMeters=context.elevation.elevationMeters if context and context.elevation else 0, heightMeters=puff["height"] + puff["sz"], radiusMeters=puff["sy"], concentration=value, band=band_for(scenario, value), opacity=min(0.4, value / max(0.01, scenario.hazard.idlhThreshold) * 0.4)))
    trajectory_times = list(range(0, time_minutes + 1, 5))
    if trajectory_times[-1] != time_minutes:
        trajectory_times.append(time_minutes)
    for minute in trajectory_times[:25]:
        east, north = _advected_position(scenario, minute)
        value = _field_concentration(scenario, puffs, east, north, plume_rise_meters(scenario))
        trajectory.append(PlumeTrajectoryPoint(timeMinutes=minute, longitude=source.longitude + east / longitude_scale, latitude=source.latitude + north / 111_320, altitudeMeters=plume_rise_meters(scenario), concentration=value, band=band_for(scenario, value), radiusMeters=24))
    buildings: list[BuildingContamination] = []
    for building in (context.buildings[:250] if context else []):
        east = (building.longitude - source.longitude) * longitude_scale
        north = (building.latitude - source.latitude) * 111_320
        value = _field_concentration(scenario, puffs, east, north, 2.0)
        band = band_for(scenario, value)
        buildings.append(BuildingContamination(footprintId=building.footprintId, displayName=building.displayName, polygon=building.polygon, levels=building.levels, buildingType=building.buildingType, concentration=value, band=band, opacity=min(0.85, value / max(0.01, scenario.hazard.idlhThreshold)), affected=value >= scenario.hazard.traceThreshold and value > 0, affectedColor=_band_color(band)))
    # Bounded raster coverage avoids counting overlapping render-particle discs repeatedly.
    covered: set[tuple[int, int]] = set()
    for puff in puffs:
        value = _field_concentration(scenario, [puff], puff["east"], puff["north"], 2.0)
        threshold = max(1e-9, scenario.hazard.traceThreshold)
        if value < threshold:
            continue
        radius = min(500.0, max(25.0, puff["sy"] * sqrt(2 * log(value / threshold))))
        for x in range(int((puff["east"] - radius) // 50), int((puff["east"] + radius) // 50) + 1):
            for y in range(int((puff["north"] - radius) // 50), int((puff["north"] + radius) // 50) + 1):
                if ((x + 0.5) * 50 - puff["east"]) ** 2 + ((y + 0.5) * 50 - puff["north"]) ** 2 <= radius ** 2:
                    covered.add((x, y))
    vectors = []
    for east in range(-600, 601, 200):
        for north in range(-600, 601, 200):
            vx, vy = _local_wind(scenario, time_minutes, east, north, 10)
            vectors.append({"longitude": source.longitude + east / longitude_scale, "latitude": source.latitude + north / 111_320, "altitudeMeters": 10.0, "eastMetersPerSecond": vx, "northMetersPerSecond": vy, "approximate": True})
    release = scenario.release
    released_mass = (release.rateKgPerSecond * min(time_minutes, release.durationMinutes) * 60 if release.mode != "IMPULSIVE" else 0) + (release.impulseMassKg if release.mode != "CONTINUOUS" and time_minutes >= release.impulseTimeMinutes else 0)
    return PlumeFrame(scenarioId=scenario.scenarioId, scenarioVersion=scenario.version, timeMinutes=time_minutes, sourceLocation=source, particles=particles, volumeCells=volumes, trajectory=trajectory, buildingContamination=buildings, propertyAffectedColors=[PropertyAffectedColor(footprintId=b.footprintId, color=b.affectedColor, band=b.band, concentration=b.concentration, affected=b.affected) for b in buildings], surfaceZones=_surface_zones(scenario, particles, time_minutes), maxConcentration=max([0.0] + [p.concentration for p in particles] + [v.concentration for v in volumes] + [b.concentration for b in buildings]), affectedAreaSqKm=len(covered) * 0.0025, populationAtRisk=None, concentrationUnit="ppm" if scenario.hazard.category == "CHEMICAL" and scenario.hazard.molecularWeightGPerMol else "mg/m³", thresholds={"trace": scenario.hazard.traceThreshold, "pel": scenario.hazard.pelThreshold, "idlh": scenario.hazard.idlhThreshold}, windVectors=vectors, releasedMassKg=released_mass, assumptions=["Illustrative Gaussian puff transport, not validated emergency guidance or CFD.", "Hourly forecasts are interpolated at five-minute simulation steps; not five-minute observations.", "Building footprints and explicit terrain obstacles heuristically deflect flow; elevation alone does not resolve terrain wind.", "Area is a bounded 50 m raster union of individual puff trace footprints (500 m radius cap), not surveyed exposure; population is unavailable.", "Particle altitude is above ground; aerosol mass concentration is not a radiological dose or biological risk."])


def make_exposure(scenario: Scenario, context: ContextSnapshot | None = None) -> ExposureResponse:
    """Bounded outdoor centroid samples over incident T+0–120, never personal dose."""
    scenario = _transport_scenario(scenario, context)
    source = _source_location(scenario)
    longitude_scale = 111_320 * max(0.0001, cos(radians(source.latitude)))
    history = _PuffTransportHistory()
    times = list(range(0, 121, 5))
    batches = [_puff_state(scenario, minute, history) for minute in times]
    # Vertical reflection and unit conversion are identical at every 2 m receptor.
    fields = [[(puff["east"], puff["north"], 1 / puff["sx"], 1 / puff["sy"],
                _field_concentration(scenario, [puff], puff["east"], puff["north"], 2.0))
               for puff in batch] for batch in batches]
    # Cover the source and the actual advected parcels, rather than a final-wind ray.
    west = south = -250.0
    east = north = 250.0
    for batch in batches:
        for puff in batch:
            west = min(west, puff["east"] - 3 * puff["sx"])
            east = max(east, puff["east"] + 3 * puff["sx"])
            south = min(south, puff["north"] - 3 * puff["sy"])
            north = max(north, puff["north"] + 3 * puff["sy"])
    reasons = ["Finite grid covers parcel centers plus three dispersion sigmas; Gaussian tails outside are omitted."]
    if max(abs(west), abs(east), abs(south), abs(north)) > 20_000:
        reasons.append("Advected path or dispersion extends beyond the 20 km per-axis source domain cap.")
    west, east = max(-20_000.0, west), min(20_000.0, east)
    south, north = max(-20_000.0, south), min(20_000.0, north)
    # Clip at valid geographic bounds; local planar transport is unreliable near poles.
    west = max(west, (-180 - source.longitude) * longitude_scale)
    east = min(east, (180 - source.longitude) * longitude_scale)
    south = max(south, (-90 - source.latitude) * 111_320)
    north = min(north, (90 - source.latitude) * 111_320)
    if abs(source.latitude) > 80 or abs(source.longitude) > 179:
        reasons.append("Polar/date-line coverage is clipped; local planar coordinates are an approximation.")
    resolution = max(50.0, ceil(max(east - west, north - south) / 20 / 50) * 50.0)
    columns = max(1, ceil((east - west) / resolution))
    rows = max(1, ceil((north - south) / resolution))

    def coordinates(x: float, y: float) -> list[float]:
        return [source.longitude + x / longitude_scale, source.latitude + y / 111_320]

    building_inputs = context.buildings[:250] if context else []
    receptors = [((building.longitude - source.longitude) * longitude_scale,
                  (building.latitude - source.latitude) * 111_320) for building in building_inputs]
    receptors.extend(((west + column * resolution + min(east, west + (column + 1) * resolution)) / 2,
                      (south + row * resolution + min(north, south + (row + 1) * resolution)) / 2)
                     for column in range(columns) for row in range(rows))
    points = np.asarray(receptors, dtype=np.float64)
    concentrations = np.zeros((len(receptors), len(times)), dtype=np.float64)
    for index, batch in enumerate(fields):
        if not batch:
            continue
        puff_fields = np.asarray(batch, dtype=np.float64)
        dx = (points[:, 0, None] - puff_fields[None, :, 0]) * puff_fields[None, :, 2]
        dy = (points[:, 1, None] - puff_fields[None, :, 1]) * puff_fields[None, :, 3]
        horizontal = dx * dx + dy * dy
        contributions = np.exp(-0.5 * horizontal) * puff_fields[None, :, 4]
        contributions[horizontal > 36] = 0
        concentrations[:, index] = contributions.sum(axis=1)
    receptor_values = iter(concentrations.tolist())

    def metrics(x: float, y: float, polygon: list[list[float]]) -> ExposureMetrics:
        values = next(receptor_values)
        cumulative = [0.0]
        for previous, current in zip(values, values[1:]):
            cumulative.append(cumulative[-1] + (previous + current) * 2.5)
        mean = cumulative[-1] / 120
        band = band_for(scenario, mean)
        lon, lat = coordinates(x, y)
        return ExposureMetrics(longitude=lon, latitude=lat, polygon=polygon,
            peakConcentration=max(values), meanConcentration=mean,
            timeIntegratedConcentration=cumulative[-1], cumulativeTimeIntegratedConcentration=cumulative,
            band=band, color=_band_color(band))

    buildings = []
    outside = 0
    for building in (context.buildings[:250] if context else []):
        x = (building.longitude - source.longitude) * longitude_scale
        y = (building.latitude - source.latitude) * 111_320
        outside += int(not (west <= x <= east and south <= y <= north))
        value = metrics(x, y, building.polygon)
        buildings.append(BuildingExposure(**value.model_dump(), footprintId=building.footprintId, displayName=building.displayName))
    areas = []
    for column in range(columns):
        left, right = west + column * resolution, min(east, west + (column + 1) * resolution)
        for row in range(rows):
            bottom, top = south + row * resolution, min(north, south + (row + 1) * resolution)
            polygon = [coordinates(left, bottom), coordinates(right, bottom), coordinates(right, top), coordinates(left, top), coordinates(left, bottom)]
            value = metrics((left + right) / 2, (bottom + top) / 2, polygon)
            areas.append(GridExposure(**value.model_dump(), cellId=f"exposure-{column}-{row}", displayName=f"Outdoor area {column + 1}-{row + 1}"))
    unit = "ppm" if scenario.hazard.category == "CHEMICAL" and scenario.hazard.molecularWeightGPerMol else "mg/m³"
    origin = scenario.incidentStartedAt
    if origin.tzinfo is None:
        origin = origin.replace(tzinfo=timezone.utc)
    lower, upper = coordinates(west, south), coordinates(east, north)
    return ExposureResponse(
        scenarioId=scenario.scenarioId, scenarioVersion=scenario.version, location=scenario.location, sourceLocation=source,
        startAt=origin.isoformat(), endAt=(origin + timedelta(minutes=120)).isoformat(),
        concentrationUnit=unit, exposureUnit="ppm·min" if unit == "ppm" else "mg·min/m³",
        thresholds={"trace": scenario.hazard.traceThreshold, "pel": scenario.hazard.pelThreshold, "idlh": scenario.hazard.idlhThreshold},
        buildings=buildings, areas=areas, gridResolutionMeters=resolution, domainTruncated=True,
        domain=ExposureDomain(bounds={"west": lower[0], "south": lower[1], "east": upper[0], "north": upper[1]},
            localBoundsMeters={"west": west, "south": south, "east": east, "north": north},
            resolutionMeters=resolution, truncated=True, truncationReasons=reasons, buildingsOutsideGrid=outside),
        dataAvailability={
            "buildings": f"{len(buildings)} supplied footprints" if buildings else "UNAVAILABLE: no building footprints supplied; no house-level inference",
            "weather": f"{scenario.weather.source}; scenario timeline" if scenario.weatherTimeline else f"{scenario.weather.source}; constant scenario weather (forecast timeline unavailable)",
            "context": "SUPPLIED" if context else "UNAVAILABLE: no context supplied; scenario-only obstacles",
            "personalDose": "UNAVAILABLE: breathing rate, occupancy, indoor infiltration and PPE are not modeled",
            "population": "UNAVAILABLE", "exceedanceDuration": "NOT_COMPUTED: five-minute samples may miss short peaks",
        },
        assumptions=[
            "Fixed incident T+0–120 minute forecast, not a rolling window from the current playback time.",
            "Outdoor concentration at 2 m above ground; building and grid centroid samples, not indoor or polygon averages.",
            "Trapezoidal integration of 25 samples at five-minute intervals; peaks between samples may be missed.",
            "Colors compare the 120-minute MEAN concentration with scenario TRACE/PEL/IDLH reference thresholds; not cumulative-dose limits or validated two-hour safety criteria.",
            "Illustrative Gaussian puff transport with heuristic obstacle deflection; not validated emergency guidance or CFD.",
            "Pressurization, explosion and gas density modify approximate source rise only; no blast, combustion or dense-gas CFD is modeled. Mixed-mode continuous and impulse masses are additive.",
            "At most 400 grid cells and 250 supplied buildings; adaptive 50–2000 m grid, 20 km per-axis domain cap; building centroids outside the grid are still sampled.",
            "Uses submitted scenario weather, timeline, source pin, release and hazard; no network lookup. Context supplies building obstacles only.",
            "Cumulative values align with startMinutes + index * timeStepMinutes; no radiological or biological dose conversion.",
        ],
        disclaimer="Outdoor modeled exposure, not inhaled/absorbed dose; does not account for indoors, occupancy or PPE; no safe/risk thresholds inferred.",
    )


@lru_cache(maxsize=4)
def _cached_exposure(payload: str) -> ExposureResponse:
    update = ScenarioPatch.model_validate_json(payload)
    return make_exposure(update.scenario, update.context)


@app.post("/api/exposure", response_model=ExposureResponse)
def post_exposure(update: ScenarioPatch) -> ExposureResponse:
    # Full validated input includes scenario/context revisions; no stale ID-only hits.
    return _cached_exposure(update.model_dump_json()).model_copy(deep=True)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aero-hazard-demo"}


@app.get("/api/map/session")
def map_session(mode: Literal["OPEN_3D", "PHOTOREALISTIC"] = "PHOTOREALISTIC") -> dict[str, object]:
    """Return a quota-guarded renderer config; never expose a key without a slot."""
    return acquire_map_session(mode)


@app.get("/api/scenario", response_model=Scenario)
def get_scenario() -> Scenario:
    return scenario_with_context(get_live_context(Location().latitude, Location().longitude))


def scenario_with_context(context: ContextSnapshot) -> Scenario:
    """Apply the cached provider snapshot before any physics frame is generated."""
    return Scenario(
        incidentStartedAt=_utc_now(),
        location=Location(latitude=context.latitude, longitude=context.longitude),
        weather=Weather(
            windSpeedMetersPerSecond=context.weather.windSpeedMetersPerSecond,
            windDirectionFromDegrees=context.weather.windDirectionFromDegrees,
            temperatureCelsius=context.weather.temperatureCelsius,
            precipitationMillimetersPerHour=context.weather.precipitationMillimetersPerHour,
            precipitationProbabilityPercent=context.weather.precipitationProbabilityPercent,
            precipitationType=context.weather.precipitationType,
            source=context.weather.source,
        ),
        weatherTimeline=context.weatherTimeline,
    )


@app.get("/api/bootstrap", response_model=BootstrapResponse)
def get_bootstrap(
    latitude: float = 40.360556,
    longitude: float = -74.6542123,
    mapMode: Literal["OPEN_3D", "PHOTOREALISTIC"] = "PHOTOREALISTIC",
) -> BootstrapResponse:
    """Build the initial scenario and plume from one cached context lookup."""
    try:
        context = get_live_context(latitude, longitude)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    scenario = scenario_with_context(context)
    return BootstrapResponse(
        scenario=scenario,
        context=context,
        frame=make_frame(scenario, 30, context),
        map=acquire_map_session(mapMode),
    )


@app.get("/api/hazards", response_model=dict[str, Hazard])
def get_hazards() -> dict[str, Hazard]:
    return {name: hazard.model_copy(deep=True) for name, hazard in HAZARD_LIBRARY.items()}


@app.get("/api/context", response_model=ContextSnapshot)
def get_context(latitude: float = 40.360556, longitude: float = -74.6542123) -> ContextSnapshot:
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise HTTPException(status_code=422, detail="coordinates are outside the valid geographic range")
    return demo_context(latitude, longitude)


@app.get("/api/context/live", response_model=ContextSnapshot)
def get_live_context_endpoint(
    latitude: float = 40.360556,
    longitude: float = -74.6542123,
    destinationLatitude: float | None = None,
    destinationLongitude: float | None = None,
) -> ContextSnapshot:
    try:
        return get_live_context(latitude, longitude, destination_latitude=destinationLatitude, destination_longitude=destinationLongitude)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/plume", response_model=PlumeFrame)
def get_plume(timeMinutes: int = 30) -> PlumeFrame:
    context = get_live_context(Location().latitude, Location().longitude)
    return make_frame(scenario_with_context(context), max(0, min(120, timeMinutes)), context)


@app.post("/api/plume", response_model=PlumeFrame)
def post_plume(update: ScenarioPatch, timeMinutes: int = 30) -> PlumeFrame:
    """Generate a frame from the caller's current scenario, preserving dispatch state."""
    return make_frame(update.scenario, max(0, min(120, timeMinutes)), update.context)


@app.post("/api/scenario", response_model=Scenario)
def update_scenario(update: ManualScenarioUpdate) -> Scenario:
    scenario = update.scenario.model_copy(deep=True)
    scenario.version += 1
    return scenario


@app.post("/api/dispatch", response_model=DispatchResponse)
def dispatch(request: DispatchRequest) -> DispatchResponse:
    scenario = request.scenario.model_copy(deep=True)
    agent_result = process_dispatch(request.text, scenario)
    decision = agent_result.decision
    for command in decision.commands:
        value = (command.value or "").strip()
        normalized_value = value.upper()
        if (command.commandType == "TRIGGER_EVENT" and normalized_value == "EXPLOSION") or (command.commandType == "UPDATE_RELEASE" and normalized_value in {"EXPLODED", "EXPLOSION"}):
            release = scenario.release
            if not release.hasExploded:
                release.hasExploded = True
                release.impulseTimeMinutes = request.timeMinutes
                if release.impulseMassKg > 0:
                    if release.mode == "CONTINUOUS":
                        release.mode = "CONTINUOUS_THEN_IMPULSIVE"
                    decision.assistantText = "Explosion recorded at the selected simulation time using the configured impulse mass. Continuous leak rate is unchanged."
                else:
                    decision.assistantText = "Explosion recorded, but additional released mass is unknown. The continuous leak rate is unchanged; no explosion mass has been invented. Set impulse mass and release mode to model the added release."
                    decision.clarifyingQuestions = ["How many kilograms were released by the explosion?"]
        elif command.commandType == "UPDATE_WEATHER":
            start = request.timeMinutes
            previous = [_weather_sample_at(scenario, minute).model_copy(update={"minutesFromNow": minute}) for minute in range(0, 121, 5)]
            # Preserve past knots; manual changes affect future transport, not old coordinates.
            for sample in previous:
                if sample.minutesFromNow <= start:
                    continue
                if normalized_value == "INCREASE_WIND_1_MPS":
                    sample.windSpeedMetersPerSecond = min(80, sample.windSpeedMetersPerSecond + 1)
                elif normalized_value == "DECREASE_WIND_1_MPS":
                    sample.windSpeedMetersPerSecond = max(0, sample.windSpeedMetersPerSecond - 1)
                elif normalized_value.startswith("DIRECTION_"):
                    try:
                        sample.windDirectionFromDegrees = float(normalized_value.removeprefix("DIRECTION_")) % 360
                    except ValueError:
                        continue
                sample.source = "DEMO"
                sample.sampleKind = "MANUAL_OVERRIDE"
            scenario.weatherTimeline = previous
            if normalized_value == "INCREASE_WIND_1_MPS":
                scenario.weather.windSpeedMetersPerSecond = min(80, scenario.weather.windSpeedMetersPerSecond + 1)
            elif normalized_value == "DECREASE_WIND_1_MPS":
                scenario.weather.windSpeedMetersPerSecond = max(0, scenario.weather.windSpeedMetersPerSecond - 1)
            elif normalized_value.startswith("DIRECTION_"):
                try:
                    scenario.weather.windDirectionFromDegrees = float(normalized_value.removeprefix("DIRECTION_")) % 360
                except ValueError:
                    pass
            scenario.weather.source = "MANUAL_OVERRIDE"
        elif command.commandType == "UPDATE_RELEASE" and normalized_value.startswith("MASS_KG_"):
            try:
                mass = max(0.0, min(100_000.0, float(normalized_value.removeprefix("MASS_KG_"))))
                if scenario.release.mode == "IMPULSIVE":
                    scenario.release.impulseMassKg = max(0.001, mass)
                else:
                    scenario.release.rateKgPerSecond = mass / (scenario.release.durationMinutes * 60)
            except ValueError:
                pass
        elif command.commandType == "ASSIGN_PROPERTY":
            scenario.activeUnits, clarification = apply_property_assignment(
                command.value, scenario.activeUnits,
                request.context.buildings if request.context else [],
            )
            if clarification:
                decision.assistantText = clarification
                decision.clarifyingQuestions = [clarification]
            elif not decision.clarifyingQuestions:
                decision.assistantText = "Known map property assigned to the simulated unit. This records assistance planning only; occupancy, access, safe routing, and live dispatch are not verified."
        elif command.commandType == "DEPLOY_UNIT":
            source = scenario.sourceLocation or scenario.location
            scenario.activeUnits, clarification = apply_unit_deployment(
                command.value, source.latitude, source.longitude, scenario.activeUnits,
            )
            if clarification:
                decision.assistantText = clarification
                decision.clarifyingQuestions = [clarification]
            elif not decision.clarifyingQuestions:
                decision.assistantText = "Simulated unit position updated on the map; no live dispatch or safe route is implied. Cardinal offsets are approximate distances from source (100 m when unspecified)."

    scenario.version += 1
    frame = make_frame(scenario, request.timeMinutes, request.context)
    voice_result = synthesize_dispatch(decision.assistantText)
    return DispatchResponse(
        assistantText=decision.assistantText,
        scenario=scenario,
        frame=frame,
        commands=[command.model_dump() for command in decision.commands],
        clarifyingQuestions=decision.clarifyingQuestions,
        actionPlan=build_action_plan(scenario, frame, request.context),
        confidence=decision.confidence,
        provider=agent_result.provider,
        audio={
            "status": voice_result.status,
            "cacheKey": voice_result.cache_key,
            "audioUrl": voice_result.audio_url,
            "provider": voice_result.provider,
        },
    )
