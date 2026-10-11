import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.main import Scenario, make_frame


def test_plume_frame_primitive_budget_and_generation_time() -> None:
    scenario = Scenario()
    started = time.perf_counter()
    frame = make_frame(scenario, 120)
    elapsed = time.perf_counter() - started
    assert len(frame.particles) <= 24
    assert len(frame.volumeCells) <= 16
    assert len(frame.surfaceZones) <= 24
    assert elapsed < 1.0


def test_large_terrain_input_remains_within_budget() -> None:
    scenario = Scenario(terrainFeatures=[
        {
            "featureId": f"ridge-{index}",
            "kind": "TERRAIN_RIDGE",
            "eastMeters": index * 10 - 500,
            "northMeters": (index % 20) * 10 - 100,
            "radiusMeters": 20,
            "heightMeters": 25,
            "porosity": 0.2,
        }
        for index in range(100)
    ])
    frame = make_frame(scenario, 60)
    assert len(frame.particles) == 18
    assert len(frame.volumeCells) == 10
