from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone
from math import cos, exp, log, pi, radians, sin, sqrt
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

from app.services.agent import process_dispatch
from app.services.context import BuildingFootprint, ContextSnapshot, ContextFeature, WeatherSample, demo_context, get_live_context
from app.services.map_guard import acquire_map_session
from app.services.voice import synthesize_dispatch


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
    latitude: float = 40.3573
    longitude: float = -74.6672
    label: str = "Princeton High School · 151 Moore St, Princeton NJ"


class Hazard(BaseModel):
    name: str = "Chlorine gas"
    category: str = "CHEMICAL"
    molecularWeightGPerMol: float | None = Field(default=None, gt=0.0, le=1_000.0)
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
    rateKgPerSecond: float = Field(15.0, ge=0.0, le=1000.0)
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
    location: Location = Location()
    hazard: Hazard = Hazard()
    gases: list[GasComponent] = Field(default_factory=list, max_length=8)
    release: Release = Release()
    weather: Weather = Weather()
    weatherTimeline: list[WeatherSample] = Field(default_factory=list, max_length=25)
    terrainFeatures: list[TerrainFeature] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_gases(self) -> "Scenario":
        if self.gases and abs(sum(gas.massFraction for gas in self.gases) - 1.0) > 0.01:
            raise ValueError("gas component mass fractions must sum to 1.0")
        return self


class ScenarioPatch(BaseModel):
    scenario: Scenario
    context: ContextSnapshot | None = None


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


class PlumeFrame(BaseModel):
    scenarioId: str
    scenarioVersion: int
    timeMinutes: int
    particles: list[PlumeParticle]
    volumeCells: list[PlumeVolume]
    buildingContamination: list[BuildingContamination] = Field(default_factory=list, max_length=250)
    surfaceZones: list[SurfaceZone] = Field(default_factory=list, max_length=100)
    maxConcentration: float
    isApproximation: bool = True
    assumptions: list[str]


class DispatchRequest(BaseModel):
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
    wind_speed = max(0.5, scenario.weather.windSpeedMetersPerSecond)
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
    return max(0.0, normalization * lateral_term * (vertical_term + ground_reflection) * dense_gas_factor * light_gas_factor * obstruction_multiplier * wet_scavenging_factor * decay_factor * settling_factor * 100.0)


def band_for(scenario: Scenario, concentration: float) -> Band:
    if concentration <= 0.0:
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
    for index, particle in enumerate(particles):
        if particle.concentration <= scenario.hazard.traceThreshold:
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


def _building_contamination(scenario: Scenario, context: ContextSnapshot | None, time_minutes: int) -> list[BuildingContamination]:
    if context is None or not context.buildings:
        return []
    results: list[BuildingContamination] = []
    for building in context.buildings[:250]:
        east = (building.longitude - scenario.location.longitude) * 111_320.0 * cos(radians(scenario.location.latitude))
        north = (building.latitude - scenario.location.latitude) * 111_320.0
        wind = _weather_sample_at(scenario, time_minutes)
        downwind = east * sin(radians((wind.windDirectionFromDegrees + 180.0) % 360.0)) + north * cos(radians((wind.windDirectionFromDegrees + 180.0) % 360.0))
        crosswind = -east * cos(radians((wind.windDirectionFromDegrees + 180.0) % 360.0)) + north * sin(radians((wind.windDirectionFromDegrees + 180.0) % 360.0))
        concentration = concentration_at(scenario, time_minutes, downwind, crosswind, 2.0, east, north)
        results.append(BuildingContamination(
            footprintId=building.footprintId,
            displayName=building.displayName,
            polygon=building.polygon,
            levels=building.levels,
            buildingType=building.buildingType,
            concentration=concentration,
            band=band_for(scenario, concentration),
            opacity=min(0.85, 0.20 + concentration / max(1.0, scenario.hazard.idlhThreshold) * 0.65),
        ))
    return results


def make_frame(scenario: Scenario, time_minutes: int, context: ContextSnapshot | None = None) -> PlumeFrame:
    timeline = [_weather_sample_at(scenario, minute) for minute in range(0, max(0, time_minutes) + 1, 5)]
    if not timeline or timeline[-1].minutesFromNow != time_minutes:
        timeline.append(_weather_sample_at(scenario, time_minutes))
    particles: list[PlumeParticle] = []
    volumes: list[PlumeVolume] = []
    max_concentration = 0.0

    for index in range(18):
        distance = 18.0 + index * 24.0
        lateral = sin(index * 1.7) * (18.0 + index * 2.5)
        east_meters = 0.0
        north_meters = 0.0
        remaining_distance = distance
        elapsed_minutes = 0.0
        for segment_start, segment_end in zip(timeline, timeline[1:]):
            segment_minutes = max(0.0, min(time_minutes, segment_end.minutesFromNow) - segment_start.minutesFromNow)
            if segment_minutes <= 0:
                continue
            segment_weather = _weather_sample_at(scenario, segment_start.minutesFromNow + segment_minutes / 2)
            segment_direction = radians((segment_weather.windDirectionFromDegrees + 180) % 360)
            segment_seconds = segment_minutes * 60.0
            segment_distance = min(remaining_distance, max(0.0, segment_weather.windSpeedMetersPerSecond) * segment_seconds)
            east_meters += sin(segment_direction) * segment_distance
            north_meters += cos(segment_direction) * segment_distance
            remaining_distance -= segment_distance
            elapsed_minutes += segment_minutes
            if remaining_distance <= 0:
                break
        if remaining_distance > 0:
            segment_weather = _weather_sample_at(scenario, max(0.0, time_minutes - elapsed_minutes))
            segment_direction = radians((segment_weather.windDirectionFromDegrees + 180) % 360)
            east_meters += sin(segment_direction) * remaining_distance
            north_meters += cos(segment_direction) * remaining_distance
        segment_weather = _weather_sample_at(scenario, time_minutes)
        wind_east = sin(radians((segment_weather.windDirectionFromDegrees + 180) % 360))
        wind_north = cos(radians((segment_weather.windDirectionFromDegrees + 180) % 360))
        crosswind_east = -wind_north
        crosswind_north = wind_east
        east_meters += crosswind_east * lateral
        north_meters += crosswind_north * lateral
        latitude = scenario.location.latitude + north_meters / 111_320.0
        longitude = scenario.location.longitude + east_meters / (111_320.0 * cos(radians(scenario.location.latitude)))
        segment_weather = _weather_sample_at(scenario, time_minutes)
        altitude = max(0.5, plume_rise_meters(scenario) + (index % 5 - 2) * (3.0 + distance * 0.012) - max(0.0, scenario.hazard.densityRelativeToAir - 1.0) * min(5.0, distance * 0.018))
        concentration = concentration_at(scenario, time_minutes, distance, lateral, altitude, east_meters, north_meters)
        max_concentration = max(max_concentration, concentration)
        band = band_for(scenario, concentration)
        particles.append(
            PlumeParticle(
                longitude=longitude,
                latitude=latitude,
                altitudeMeters=altitude,
                radiusMeters=14.0 + concentration * 1.6,
                concentration=concentration,
                band=band,
                opacity=min(0.8, 0.16 + concentration / 20.0),
            )
        )

    for index in range(10):
        distance = 35.0 + index * 42.0
        lateral = 0.0
        segment_weather = _weather_sample_at(scenario, time_minutes)
        wind_east = sin(radians((segment_weather.windDirectionFromDegrees + 180) % 360))
        wind_north = cos(radians((segment_weather.windDirectionFromDegrees + 180) % 360))
        east_meters = wind_east * distance
        north_meters = wind_north * distance
        latitude = scenario.location.latitude + north_meters / 111_320.0
        longitude = scenario.location.longitude + east_meters / (111_320.0 * cos(radians(scenario.location.latitude)))
        height = max(4.0, plume_rise_meters(scenario) + 5.0 + index * (1.1 + segment_weather.windSpeedMetersPerSecond * 0.08) - max(0.0, scenario.hazard.densityRelativeToAir - 1.0) * index * 0.12)
        concentration = concentration_at(scenario, time_minutes, distance, lateral, height, east_meters, north_meters)
        max_concentration = max(max_concentration, concentration)
        band = band_for(scenario, concentration)
        volumes.append(
            PlumeVolume(
                longitude=longitude,
                latitude=latitude,
                groundElevationMeters=0.0,
                heightMeters=height + concentration * 1.2,
                radiusMeters=28.0 + index * 2.0,
                concentration=concentration,
                band=band,
                opacity=min(0.4, 0.08 + concentration / 50.0),
            )
        )

    return PlumeFrame(
        scenarioId=scenario.scenarioId,
        scenarioVersion=scenario.version,
        timeMinutes=time_minutes,
        particles=particles,
        volumeCells=volumes,
        buildingContamination=_building_contamination(scenario, context, time_minutes),
        surfaceZones=_surface_zones(scenario, particles, time_minutes),
        maxConcentration=max_concentration,
        assumptions=["Real-time plume projection from wind, release, terrain, and hazard inputs."],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aero-hazard-demo"}


@app.get("/api/map/session")
def map_session(mode: Literal["OPEN_3D", "PHOTOREALISTIC"] = "PHOTOREALISTIC") -> dict[str, object]:
    """Return a quota-guarded renderer config; never expose a key without a slot."""
    return acquire_map_session(mode)


@app.get("/api/scenario", response_model=Scenario)
def get_scenario() -> Scenario:
    return Scenario()


def scenario_with_context(context: ContextSnapshot) -> Scenario:
    """Apply the cached provider snapshot before any physics frame is generated."""
    return Scenario(
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
    latitude: float = 40.3573,
    longitude: float = -74.6672,
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
def get_context(latitude: float = 40.3573, longitude: float = -74.6672) -> ContextSnapshot:
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise HTTPException(status_code=422, detail="coordinates are outside the valid geographic range")
    return demo_context(latitude, longitude)


@app.get("/api/context/live", response_model=ContextSnapshot)
def get_live_context_endpoint(
    latitude: float = 40.3573,
    longitude: float = -74.6672,
    destinationLatitude: float | None = None,
    destinationLongitude: float | None = None,
) -> ContextSnapshot:
    try:
        return get_live_context(latitude, longitude, destination_latitude=destinationLatitude, destination_longitude=destinationLongitude)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/plume", response_model=PlumeFrame)
def get_plume(timeMinutes: int = 30) -> PlumeFrame:
    scenario = Scenario()
    return make_frame(scenario, max(0, min(120, timeMinutes)))


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
        if command.commandType == "TRIGGER_EVENT" and normalized_value == "EXPLOSION":
            scenario.release.hasExploded = True
            scenario.release.rateKgPerSecond = min(1000.0, scenario.release.rateKgPerSecond * 1.35)
        elif command.commandType == "UPDATE_RELEASE":
            if normalized_value in {"EXPLODED", "EXPLOSION"} and not scenario.release.hasExploded:
                scenario.release.hasExploded = True
                scenario.release.rateKgPerSecond = min(1000.0, scenario.release.rateKgPerSecond * 1.35)
        elif command.commandType == "UPDATE_WEATHER":
            if normalized_value == "INCREASE_WIND_1_MPS":
                scenario.weather.windSpeedMetersPerSecond = min(80.0, scenario.weather.windSpeedMetersPerSecond + 1.0)
            elif normalized_value == "DECREASE_WIND_1_MPS":
                scenario.weather.windSpeedMetersPerSecond = max(0.0, scenario.weather.windSpeedMetersPerSecond - 1.0)
        elif command.commandType == "DEPLOY_UNIT" and value:
            scenario.location.label = f"{scenario.location.label} | Unit: {value[:80]}"

    scenario.version += 1
    frame = make_frame(scenario, 30, request.context)
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
