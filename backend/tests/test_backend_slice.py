import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import Scenario, dispersion_coefficients, make_frame
from app.services.agent import process_dispatch


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