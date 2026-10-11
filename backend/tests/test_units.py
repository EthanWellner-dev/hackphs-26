import asyncio
import json
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))

from app import main
from app.main import Scenario
from app.services.agent import _deterministic_decision
from app.services.units import Unit, apply_property_assignment, apply_unit_deployment
from app.services.context import BuildingFootprint, demo_context
from app.services import agent
from types import SimpleNamespace


def test_distinct_units_and_idempotent_updates():
    first, question = apply_unit_deployment("deploy Engine 4 at 40.3, -74.6", 40, -74, [])
    assert question is None
    second, question = apply_unit_deployment("deploy Ambulance 2 to source", 40, -74, first)
    assert question is None
    assert len(second) == 2
    assert second[1].latitude == 40
    updated, question = apply_unit_deployment("deploy ENGINE 4 at 41, -75", 40, -74, second)
    assert question is None
    assert len(updated) == 2
    assert updated[0].unitId == first[0].unitId
    assert updated[0].latitude == 41
    assert first[0].latitude == 40.3


@pytest.mark.parametrize("value", [
    "deploy Engine 4 at 91, 0", "deploy Engine 4 at 0, -181",
    "deploy Engine 4 to Main Street", "deploy Engine 4", None,
    '{"label":"Engine 4","latitude":NaN,"longitude":0}',
    '{"label":"Engine 4","latitude":0,"longitude":Infinity}',
    '{"label":"Engine 4","latitude":40}',
])
def test_invalid_or_unknown_location_does_not_fabricate_position(value):
    roster = [Unit(unitId="engine-1", label="Engine 1", latitude=40, longitude=-74)]
    result, question = apply_unit_deployment(value, 40, -74, roster)
    assert question
    assert result == roster


def test_json_string_compatibility():
    value = json.dumps({"unitId": "fd-4", "label": "Engine 4", "latitude": 40.3, "longitude": -74.6})
    units, question = apply_unit_deployment(value, 40, -74, [])
    assert question is None
    assert units[0].unitId == "fd-4"
    moved, question = apply_unit_deployment(value, 40, -74, units)
    assert question is None
    assert moved == units


@pytest.mark.parametrize("direction, axis, sign", [("north", "latitude", 1), ("south", "latitude", -1), ("east", "longitude", 1), ("west", "longitude", -1)])
def test_simulated_cardinal_offsets(direction, axis, sign):
    units, question = apply_unit_deployment(f"deploy Engine 4 to 200 m {direction} of source", 40, -74, [])
    assert question is None
    assert (getattr(units[0], axis) - (40 if axis == "latitude" else -74)) * sign > 0


def test_roster_limit_and_update_at_capacity():
    units = [Unit(unitId=f"engine-{i}", label=f"Engine {i}", latitude=40, longitude=-74) for i in range(50)]
    unchanged, question = apply_unit_deployment("deploy Engine 50 to source", 40, -74, units)
    assert question and unchanged == units
    updated, question = apply_unit_deployment("deploy Engine 4 at 41, -75", 40, -74, units)
    assert question is None and len(updated) == 50
    assert updated[4].latitude == 41
    with pytest.raises(ValidationError):
        Scenario(activeUnits=units + [units[0]])


def test_deployment_priority_and_complete_command():
    text = "deploy Engine 4 to north"
    decision = _deterministic_decision(text, Scenario())
    assert decision.commands[0].commandType == "DEPLOY_UNIT"
    assert decision.commands[0].value == text
    assert "simulated" in decision.assistantText.lower()


def test_dispatch_roster_preserves_incident_and_clarifies_unknown(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(main, "synthesize_dispatch", lambda text: type("Voice", (), {"status": "TEXT_ONLY", "cache_key": "test", "audio_url": None, "provider": "TEST"})())

    async def exercise():
        scenario = Scenario(sourceLocation=main.Location(latitude=41, longitude=-75)).model_dump(mode="json")
        original_label = scenario["location"]["label"]
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            for text in ["deploy Engine 4 at 40.3, -74.6", "deploy Ambulance 2 to source", "deploy Engine 4 to Main Street"]:
                response = await client.post("/api/dispatch", json={"text": text, "scenario": scenario})
                assert response.status_code == 200, response.text
                body = response.json()
                scenario = body["scenario"]
            assert len(scenario["activeUnits"]) == 2
            assert scenario["activeUnits"][1]["latitude"] == 41
            assert scenario["location"]["label"] == original_label
            assert body["clarifyingQuestions"]
            assert "not geocoded" in body["assistantText"]

    asyncio.run(exercise())


def _building(footprint_id="way/100", name="Walnut House"):
    return BuildingFootprint(footprintId=footprint_id, displayName=name, latitude=40, longitude=-74,
                             polygon=[[-74, 40], [-74.001, 40], [-74, 40.001]], source="DEMO", retrievedAt="2026-10-11T00:00:00Z")


def test_details_preserved_on_move_and_assignment():
    roster, question = apply_unit_deployment("deploy Hazmat 1 to source; teamType: hazmat; equipment: radio, monitor; task: assist residents", 40, -74, [])
    assert question is None
    assert roster[0].teamType == "hazmat"
    assert roster[0].equipment == ["radio", "monitor"]
    assigned, question = apply_property_assignment("assign Walnut House to Hazmat 1", roster, [_building()])
    assert question is None
    assert assigned[0].assignedPropertyIds == ["way/100"]
    repeated, question = apply_property_assignment('assign way/100 to hazmat-1', assigned, [_building()])
    assert repeated == assigned and question is None
    moved, question = apply_unit_deployment("deploy Hazmat 1 at 41, -75", 40, -74, assigned)
    assert question is None
    assert moved[0].assignedPropertyIds == ["way/100"]
    assert moved[0].task == "assist residents"
    assert moved[0].equipment == ["radio", "monitor"]
    assert roster[0].assignedPropertyIds == []


@pytest.mark.parametrize("value, buildings", [
    ("assign Imaginary House to Engine 4", [_building()]),
    ("assign Walnut House to Missing Unit", [_building()]),
    ("assign Walnut House to Engine 4", [_building(), _building("way/101")]),
    ("assign Walnut House to Engine 4", []),
    ('{"propertyId":12,"unitId":"engine-4"}', [_building()]),
])
def test_unknown_ambiguous_assignment_is_unchanged(value, buildings):
    roster = [Unit(unitId="engine-4", label="Engine 4", latitude=40, longitude=-74)]
    result, question = apply_property_assignment(value, roster, buildings)
    assert question and result == roster


def test_deployment_rejects_assignment_bypass_and_invalid_details():
    for extra in ({"assignedPropertyIds": ["invented"]}, {"equipment": "radio"}, {"teamType": ""}):
        roster, question = apply_unit_deployment(json.dumps({"label": "Engine 4", "latitude": 40, "longitude": -74, **extra}), 40, -74, [])
        assert question and roster == []


@pytest.mark.parametrize("gemini", [False, True])
def test_dispatch_assigns_only_context_properties_and_details(monkeypatch, gemini):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    agent._AGENT_CACHE.clear()
    calls = []
    if gemini:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        def generate_content(**kwargs):
            calls.append(kwargs)
            text = json.loads(kwargs["contents"])["userMessage"]
            if text.startswith("deploy"):
                value = json.dumps({"label": "Engine 4", "latitude": 40, "longitude": -74, "teamType": "fire", "equipment": ["radio"], "task": "assist residents"})
                kind = "DEPLOY_UNIT"
            else:
                value = json.dumps({"propertyId": "way/100" if "Walnut House" in text else "invented", "unitId": "engine-4"})
                kind = "ASSIGN_PROPERTY"
            return SimpleNamespace(text=json.dumps({"assistantText": "Updating simulation.", "commands": [{"commandType": kind, "value": value}]}))
        monkeypatch.setattr(agent, "genai", SimpleNamespace(Client=lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))))
    monkeypatch.setattr(main, "synthesize_dispatch", lambda text: SimpleNamespace(status="TEXT_ONLY", cache_key="test", audio_url=None, provider="TEST"))

    async def exercise():
        scenario = Scenario().model_dump(mode="json")
        context = demo_context(40, -74)
        context.buildings = [_building()]
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            for text in ["deploy Engine 4 at 40, -74; teamType: fire; equipment: radio; task: assist residents", "assign Walnut House to Engine 4", "assign Imaginary House to Engine 4"]:
                response = await client.post("/api/dispatch", json={"text": text, "scenario": scenario, "context": context.model_dump(mode="json")})
                assert response.status_code == 200, response.text
                body = response.json()
                scenario = body["scenario"]
            unit = scenario["activeUnits"][0]
            assert unit["assignedPropertyIds"] == ["way/100"]
            assert unit["teamType"] == "fire"
            assert unit["equipment"] == ["radio"]
            assert unit["task"] == "assist residents"
            assert body["clarifyingQuestions"]
            if gemini:
                assert body["provider"].startswith("GEMINI:")
                assert len(calls) == 3
    asyncio.run(exercise())
