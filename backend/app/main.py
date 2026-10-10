from __future__ import annotations

import os
from pathlib import Path
from math import cos, exp, log, pi, radians, sin, sqrt
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.services.agent import process_dispatch
from app.services.voice import synthesize_dispatch


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


Band = Literal["TRACE", "PEL", "IDLH"]


class Location(BaseModel):
    latitude: float = 40.3487
    longitude: float = -74.6593
    label: str = "Demo incident location"


class Hazard(BaseModel):
    name: str = "Chlorine gas"
    category: str = "CHEMICAL"
    densityRelativeToAir: float = 2.47
    traceThreshold: float = 0.5
    pelThreshold: float = 1.0
    idlhThreshold: float = 10.0


class Release(BaseModel):
    rateKgPerSecond: float = Field(15.0, ge=0.0, le=1000.0)
    durationMinutes: int = Field(30, ge=1, le=240)
    sourceHeightMeters: float = Field(1.5, ge=0.0, le=100.0)
    isPressurized: bool = True
    hasExploded: bool = False


class Weather(BaseModel):
    windSpeedMetersPerSecond: float = Field(4.5, ge=0.0, le=80.0)
    windDirectionFromDegrees: float = Field(225.0, ge=0.0, le=360.0)
    temperatureCelsius: float = 18.0
    pasquillStabilityClass: Literal["A", "B", "C", "D", "E", "F"] = "D"
    source: str = "DEMO"


class Scenario(BaseModel):
    scenarioId: str = "INC-8892"
    version: int = 1
    location: Location = Location()
    hazard: Hazard = Hazard()
    release: Release = Release()
    weather: Weather = Weather()


class ScenarioPatch(BaseModel):
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


class PlumeFrame(BaseModel):
    scenarioId: str
    scenarioVersion: int
    timeMinutes: int
    particles: list[PlumeParticle]
    volumeCells: list[PlumeVolume]
    maxConcentration: float
    isApproximation: bool = True
    assumptions: list[str]


class DispatchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    scenario: Scenario


class DispatchResponse(BaseModel):
    assistantText: str
    scenario: Scenario
    frame: PlumeFrame
    commands: list[dict[str, str | None]] = Field(default_factory=list)
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


STABILITY_COEFFICIENTS = {
    "A": ((0.22, 0.0001, -0.5), (0.20, 0.0, 0.0)),
    "B": ((0.16, 0.0001, -0.5), (0.12, 0.0, 0.0)),
    "C": ((0.11, 0.0001, -0.5), (0.08, 0.0002, -0.5)),
    "D": ((0.08, 0.0001, -0.5), (0.06, 0.0015, -0.5)),
    "E": ((0.06, 0.0001, -0.5), (0.03, 0.0003, -1.0)),
    "F": ((0.04, 0.0001, -0.5), (0.016, 0.0003, -1.0)),
}


def dispersion_coefficients(scenario: Scenario, downwind_meters: float) -> tuple[float, float]:
    """Return Pasquill-Gifford sigma-y and sigma-z in meters.

    This is a bounded visualization approximation for rural/urban-scale demo
    distances, not a regulatory dispersion calculation.
    """
    lateral, vertical = STABILITY_COEFFICIENTS[scenario.weather.pasquillStabilityClass]
    sigma_y = max(2.0, lateral[0] * downwind_meters * (1 + lateral[1] * downwind_meters) ** lateral[2])
    sigma_z = max(2.0, vertical[0] * downwind_meters * (1 + vertical[1] * downwind_meters) ** vertical[2])
    return sigma_y, sigma_z


def plume_rise_meters(scenario: Scenario) -> float:
    """Approximate buoyant/pressurized rise without modeling a full jet."""
    pressure_factor = 1.35 if scenario.release.isPressurized else 1.0
    heat_factor = 1.25 if scenario.release.hasExploded else 1.0
    buoyancy_factor = max(0.55, 1.0 / sqrt(max(0.5, scenario.hazard.densityRelativeToAir)))
    return scenario.release.sourceHeightMeters + 3.0 * pressure_factor * heat_factor * buoyancy_factor


def concentration_at(scenario: Scenario, time_minutes: int, downwind_meters: float, crosswind_meters: float, altitude_meters: float) -> float:
    """Estimate concentration with a steady Gaussian plume and ground reflection."""
    wind_speed = max(0.5, scenario.weather.windSpeedMetersPerSecond)
    elapsed_seconds = max(1.0, time_minutes * 60.0)
    release_seconds = scenario.release.durationMinutes * 60.0
    sigma_y, sigma_z = dispersion_coefficients(scenario, max(1.0, downwind_meters))
    effective_height = plume_rise_meters(scenario)

    if downwind_meters <= 0:
        return 0.0

    # A finite puff remains visible after shutoff, but decays as it moves away
    # from the last active source position.
    active_window = min(elapsed_seconds, release_seconds)
    trailing_seconds = max(0.0, elapsed_seconds - release_seconds)
    duration_factor = min(1.0, active_window / max(1.0, release_seconds))
    trailing_factor = exp(-trailing_seconds / max(60.0, release_seconds * 0.8))
    emission_rate = scenario.release.rateKgPerSecond * duration_factor * trailing_factor

    lateral_term = exp(-0.5 * (crosswind_meters / sigma_y) ** 2)
    vertical_term = exp(-0.5 * ((altitude_meters - effective_height) / sigma_z) ** 2)
    ground_reflection = exp(-0.5 * ((altitude_meters + effective_height) / sigma_z) ** 2)
    normalization = emission_rate / (2.0 * pi * wind_speed * sigma_y * sigma_z)
    heavy_gas_factor = 1.0 + max(0.0, scenario.hazard.densityRelativeToAir - 1.0) * 0.18
    return max(0.0, normalization * lateral_term * (vertical_term + ground_reflection) * heavy_gas_factor * 100.0)


def band_for(scenario: Scenario, concentration: float) -> Band:
    if concentration >= scenario.hazard.idlhThreshold:
        return "IDLH"
    if concentration >= scenario.hazard.pelThreshold:
        return "PEL"
    return "TRACE"


def make_frame(scenario: Scenario, time_minutes: int) -> PlumeFrame:
    direction_to = radians((scenario.weather.windDirectionFromDegrees + 180) % 360)
    wind_x = sin(direction_to)
    wind_y = cos(direction_to)
    particles: list[PlumeParticle] = []
    volumes: list[PlumeVolume] = []
    max_concentration = 0.0

    for index in range(18):
        distance = 18.0 + index * 24.0
        lateral = sin(index * 1.7) * (18.0 + index * 2.5)
        east_meters = wind_x * distance - wind_y * lateral
        north_meters = wind_y * distance + wind_x * lateral
        latitude = scenario.location.latitude + north_meters / 111_320.0
        longitude = scenario.location.longitude + east_meters / (111_320.0 * cos(radians(scenario.location.latitude)))
        altitude = scenario.release.sourceHeightMeters + 2.0 + (index % 4) * 2.5
        concentration = concentration_at(scenario, time_minutes, distance, lateral, altitude)
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
        east_meters = wind_x * distance
        north_meters = wind_y * distance
        latitude = scenario.location.latitude + north_meters / 111_320.0
        longitude = scenario.location.longitude + east_meters / (111_320.0 * cos(radians(scenario.location.latitude)))
        height = 8.0 + index * 1.5
        concentration = concentration_at(scenario, time_minutes, distance, lateral, height)
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
        maxConcentration=max_concentration,
        assumptions=[
            "Gaussian plume approximation with Pasquill-Gifford spread",
            "Meteorological wind direction converted from source direction to transport direction",
            "Ground reflection, source height, pressurization, and heavy-gas adjustment included",
            "Terrain and building obstruction require the next terrain-mask iteration",
        ],
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "aero-hazard-demo"}


@app.get("/api/scenario", response_model=Scenario)
def get_scenario() -> Scenario:
    return Scenario()


@app.get("/api/plume", response_model=PlumeFrame)
def get_plume(timeMinutes: int = 30) -> PlumeFrame:
    scenario = Scenario()
    return make_frame(scenario, max(0, min(120, timeMinutes)))


@app.post("/api/dispatch", response_model=DispatchResponse)
def dispatch(request: DispatchRequest) -> DispatchResponse:
    scenario = request.scenario.model_copy(deep=True)
    agent_result = process_dispatch(request.text, scenario)
    decision = agent_result.decision
    for command in decision.commands:
        if command.commandType == "TRIGGER_EVENT" and command.value == "EXPLOSION":
            scenario.release.hasExploded = True
            scenario.release.rateKgPerSecond = min(1000.0, scenario.release.rateKgPerSecond * 1.35)
        elif command.commandType == "UPDATE_RELEASE" and (command.value or "").upper() in {"EXPLODED", "EXPLOSION"}:
            scenario.release.hasExploded = True
            scenario.release.rateKgPerSecond = min(1000.0, scenario.release.rateKgPerSecond * 1.35)
        elif command.commandType == "UPDATE_WEATHER" and command.value == "INCREASE_WIND_1_MPS":
            scenario.weather.windSpeedMetersPerSecond = min(80.0, scenario.weather.windSpeedMetersPerSecond + 1.0)

    scenario.version += 1
    voice_result = synthesize_dispatch(decision.assistantText)
    return DispatchResponse(
        assistantText=decision.assistantText,
        scenario=scenario,
        frame=make_frame(scenario, 30),
        commands=[command.model_dump() for command in decision.commands],
        confidence=decision.confidence,
        provider=agent_result.provider,
        audio={
            "status": voice_result.status,
            "cacheKey": voice_result.cache_key,
            "audioUrl": voice_result.audio_url,
            "provider": voice_result.provider,
        },
    )
