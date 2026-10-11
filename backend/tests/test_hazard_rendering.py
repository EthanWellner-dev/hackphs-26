import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import Location, Scenario, WeatherSample, make_frame
from app.services.context import BuildingFootprint, demo_context


def test_default_source_is_princeton_middle_school() -> None:
    scenario = Scenario()
    assert scenario.location.latitude == pytest.approx(40.360556)
    assert scenario.location.longitude == pytest.approx(-74.6542123)
    assert "Princeton Middle School" in scenario.location.label


def test_particle_fission_grows_the_five_seed_parcels_and_remains_deterministic() -> None:
    initial = make_frame(Scenario(), 0)
    baseline = make_frame(Scenario(), 30)
    exploded = make_frame(Scenario(release={"hasExploded": True}), 30)
    assert len(initial.particles) == 5
    assert len(baseline.particles) > len(initial.particles)
    assert len(exploded.particles) >= len(baseline.particles)
    assert baseline.particles == make_frame(Scenario(), 30).particles
    assert baseline.trajectory[-1].longitude != pytest.approx(baseline.sourceLocation.longitude)


def test_source_pin_is_used_by_three_d_render_payload() -> None:
    source = Location(latitude=40.35, longitude=-74.66, label="Valve house")
    frame = make_frame(Scenario(sourceLocation=source), 0)

    assert frame.sourceLocation == source
    assert frame.trajectory[0].latitude == pytest.approx(source.latitude)
    assert frame.trajectory[0].longitude == pytest.approx(source.longitude)


def test_property_affected_colors_follow_building_concentration() -> None:
    context = demo_context(40.3573, -74.6672)
    context.buildings = [BuildingFootprint(
        footprintId="building-1",
        displayName="School",
        latitude=40.3573,
        longitude=-74.6655,
        polygon=[[-74.6656, 40.3572], [-74.6654, 40.3572], [-74.6654, 40.3574]],
        levels=2,
        source="DEMO",
        retrievedAt="2026-10-11T00:00:00Z",
    )]

    frame = make_frame(Scenario(), 30, context)
    assert len(frame.propertyAffectedColors) == 1
    color = frame.propertyAffectedColors[0]
    building = frame.buildingContamination[0]
    assert color.footprintId == building.footprintId
    assert color.color == building.affectedColor
    assert color.band == building.band
    assert color.affected == (building.concentration >= 0.5)


def test_trajectory_integrates_each_five_minute_wind_step() -> None:
    scenario = Scenario(weatherTimeline=[
        WeatherSample(minutesFromNow=0, windSpeedMetersPerSecond=4.0, windDirectionFromDegrees=0.0, temperatureCelsius=18.0, source="LIVE"),
        WeatherSample(minutesFromNow=5, windSpeedMetersPerSecond=4.0, windDirectionFromDegrees=90.0, temperatureCelsius=18.0, source="LIVE"),
        WeatherSample(minutesFromNow=10, windSpeedMetersPerSecond=4.0, windDirectionFromDegrees=180.0, temperatureCelsius=18.0, source="LIVE"),
    ])

    frame = make_frame(scenario, 10)
    assert [point.timeMinutes for point in frame.trajectory] == [0, 5, 10]
    # The integrated path includes the westward middle interval; a final-wind
    # tangent would incorrectly place the centerline directly northward.
    assert frame.trajectory[-1].longitude < scenario.location.longitude
    assert frame.trajectory[-1].latitude == pytest.approx(scenario.location.latitude)
