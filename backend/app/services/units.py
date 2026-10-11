from __future__ import annotations

import json
import math
import re
from typing import Annotated, Literal

from app.services.context import BuildingFootprint

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Unit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)

    unitId: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    status: Literal["DEPLOYED"] = "DEPLOYED"
    teamType: str | None = Field(default=None, min_length=1, max_length=80)
    equipment: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=30)
    task: str | None = Field(default=None, min_length=1, max_length=300)
    assignedPropertyIds: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list, max_length=250)


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_COORDINATES = re.compile(rf"\(?\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\)?[.!]?$")
_OFFSET = re.compile(rf"(?:(?P<distance>{_NUMBER})\s*(?P<scale>m|meters?|metres?|km|kilometers?)\s+)?(?P<direction>north|south|east|west)(?:\s+of\s+(?:the\s+)?source)?[.!]?$", re.I)
_LOCATION_QUESTION = "Provide latitude, longitude or select a map place and use its coordinates; street names are not geocoded. You can also specify source or a simulated offset such as 200 m north of source."


def apply_unit_deployment(
    value: str | None,
    source_lat: float,
    source_lon: float,
    units: list[Unit],
) -> tuple[list[Unit], str | None]:
    """Validate a textual/JSON deployment, returning a new roster or a clarification.

    Text accepts 'deploy Engine 4 at 40.36, -74.65', 'Ambulance 2 to
    source', and cardinal offsets from source (default 100 meters). JSON
    strings accept label, latitude, longitude, and optional unitId. No place
    names are geocoded, and all positions represent simulated deployment.
    Optional text details use '; teamType: hazmat; equipment: radio, monitor;
    task: assist residents'. JSON accepts those fields directly. Moving a unit
    preserves omitted details and assignments; properties are assigned separately.
    """
    roster = [Unit.model_validate(unit).model_copy(deep=True) for unit in units]
    if len(roster) > 50:
        raise ValueError("Unit roster cannot contain more than 50 units")
    text = (value or "").strip()
    label = ""
    unit_id = None
    latitude = longitude = None
    details = {}
    try:
        if text.startswith("{"):
            payload = json.loads(text)
            label = payload.get("label", "")
            unit_id = payload.get("unitId")
            latitude = payload.get("latitude", payload.get("lat"))
            longitude = payload.get("longitude", payload.get("lon"))
            details = {key: payload[key] for key in ("teamType", "equipment", "task") if key in payload}
            if payload.get("assignedPropertyIds"):
                return roster, "Assign known properties separately using 'assign <building name or footprintId> to <unit>'."
        else:
            text, *detail_parts = text.split(";")
            for detail in detail_parts:
                detail_match = re.fullmatch(r"\s*(teamType|equipment|task)\s*:\s*(.+?)\s*", detail, re.I)
                if not detail_match:
                    return roster, "Use details as '; teamType: hazmat; equipment: radio, monitor; task: assist residents'."
                key, content = detail_match.groups()
                key = "teamType" if key.lower() == "teamtype" else key.lower()
                details[key] = [item.strip() for item in content.split(",")] if key == "equipment" else content
            text = text.strip()
            text = re.sub(r"^(?:please\s+)?deploy\s+", "", text, flags=re.I)
            text = re.sub(r"^(?:i|we)\s+have\s+(?:an?\s+)?", "", text, flags=re.I)
            text = re.sub(r"\s+(?:is\s+|are\s+)?responding\s+(?=at\b|on\b|to\b)", " ", text, flags=re.I)
            match = re.fullmatch(r"(?P<label>.+?)\s+(?:at|to|on)\s+(?P<destination>.+)", text, re.I)
            if not match:
                return roster, "Which unit and location? Try 'deploy Engine 4 at 40.36, -74.65' or 'deploy Ambulance 2 to source'."
            label = match.group("label").strip()
            specialization = re.fullmatch(r"(.+?)\s+with\s+(hazmat|fire|medical|ems|rescue)(?:\s+(?:capability|support))?", label, re.I)
            if specialization:
                label = specialization.group(1).strip()
                details.setdefault("teamType", specialization.group(2).lower())
            if label.lower() in {"fire team", "hazmat team", "medical team", "rescue team"}:
                label = label[0].upper() + label[1:]
            destination = match.group("destination").strip()
            coordinates = _COORDINATES.fullmatch(destination)
            offset = _OFFSET.fullmatch(destination)
            if coordinates:
                latitude, longitude = map(float, coordinates.groups())
            elif re.fullmatch(r"(?:the\s+)?source[.!]?", destination, re.I):
                latitude, longitude = source_lat, source_lon
            elif offset:
                distance = float(offset.group("distance") or "100")
                if (offset.group("scale") or "m").lower().startswith("k"):
                    distance *= 1000
                if not 0 < distance <= 100_000:
                    return roster, "Use a simulated offset greater than zero and no more than 100 km from source."
                latitude, longitude = source_lat, source_lon
                direction = offset.group("direction").lower()
                if direction in {"north", "south"}:
                    latitude += distance / 111_320 * (1 if direction == "north" else -1)
                else:
                    scale = math.cos(math.radians(source_lat))
                    if abs(scale) < 0.001:
                        return roster, "Near the poles, provide explicit latitude and longitude instead of an east/west offset."
                    longitude += distance / (111_320 * scale) * (1 if direction == "east" else -1)
            else:
                return roster, _LOCATION_QUESTION
        if not isinstance(label, str) or not label.strip():
            return roster, "Provide a unit label, such as Engine 4 or Ambulance 2."
        label = " ".join(label.split())
        unit_id = unit_id or re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
        existing = next((unit for unit in roster if unit.unitId == unit_id), None)
        data = existing.model_dump() if existing else {}
        data.update(unitId=unit_id, label=label, latitude=latitude, longitude=longitude)
        data.update(details)
        unit = Unit.model_validate(data)
    except (ValueError, TypeError, ValidationError):
        return roster, "Provide a valid unit label and finite coordinates: latitude -90 to 90, longitude -180 to 180. " + _LOCATION_QUESTION
    for index, existing in enumerate(roster):
        if existing.unitId == unit.unitId:
            roster[index] = unit
            return roster, None
    if len(roster) >= 50:
        return roster, "The simulated roster is limited to 50 units. Update an existing unit instead."
    roster.append(unit)
    return roster, None


def apply_property_assignment(
    value: str | None,
    units: list[Unit],
    buildings: list[BuildingFootprint],
) -> tuple[list[Unit], str | None]:
    """Assign one known context footprint to an existing simulated unit.

    Accepts 'assign <exact building name or footprintId> to <unit label or ID>'
    or a JSON string with propertyId/propertyName and unitId/unitLabel. Ambiguous
    names require an ID. Repeating an assignment does not duplicate it or move
    the unit; this records work allocation, not routing or verified occupancy.
    """
    roster = [Unit.model_validate(unit).model_copy(deep=True) for unit in units]
    text = (value or "").strip()
    try:
        if text.startswith("{"):
            payload = json.loads(text)
            property_name = payload.get("propertyId") or payload.get("propertyName")
            unit_name = payload.get("unitId") or payload.get("unitLabel")
        else:
            match = re.fullmatch(r"(?:please\s+)?assign\s+(.+?)\s+to\s+(.+?)\s*", text, re.I)
            if not match:
                return roster, "Use 'assign <building name or footprintId> to <existing unit label or ID>'."
            property_name, unit_name = match.groups()
        if not isinstance(property_name, str) or not isinstance(unit_name, str):
            raise ValueError("Missing assignment target")
        property_name, unit_name = property_name.strip().casefold(), unit_name.strip().casefold()
    except (ValueError, TypeError):
        return roster, "Provide a known building name or footprintId and an existing unit label or ID."
    targets = [unit for unit in roster if unit.unitId.casefold() == unit_name]
    if not targets:
        targets = [unit for unit in roster if unit.label.casefold() == unit_name]
    if len(targets) != 1:
        return roster, "Choose one existing unit by its unique unitId; deploy it on the map first if missing."
    bulk = re.fullmatch(r"(\d+)\s+(?:(?:nearby|nearest)\s+)?(?:homes?|houses?|residential buildings?)[.!]?", property_name)
    if bulk:
        count = int(bulk.group(1))
        target = targets[0]
        if not 1 <= count <= 250:
            return roster, "Choose between 1 and 250 known residential buildings."
        assigned = {property_id for unit in roster for property_id in unit.assignedPropertyIds}
        residential_types = {"house", "residential", "apartments", "detached", "semidetached_house", "terrace", "bungalow", "dormitory"}
        candidates = {building.footprintId: building for building in buildings
                      if building.buildingType.casefold() in residential_types and building.footprintId not in assigned}
        if len(candidates) < count:
            return roster, f"Only {len(candidates)} unassigned known residential buildings are loaded; none assigned. Choose a smaller count or load more map buildings. Occupancy is unknown."
        if len(target.assignedPropertyIds) + count > 250:
            return roster, "This assignment would exceed the unit's limit of 250 properties."

        def distance(building: BuildingFootprint) -> float:
            lat1, lat2 = math.radians(target.latitude), math.radians(building.latitude)
            dlat = lat2 - lat1
            dlon = math.radians(building.longitude - target.longitude)
            return math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2

        nearest = sorted(candidates.values(), key=lambda building: (distance(building), building.footprintId))[:count]
        target.assignedPropertyIds.extend(building.footprintId for building in nearest)
        return roster, None
    matches = [building for building in buildings if building.footprintId.casefold() == property_name]
    if not matches:
        matches = [building for building in buildings if building.displayName.casefold() == property_name]
    if len(matches) != 1:
        return roster, "Choose a unique footprintId from the loaded map buildings. Unknown or ambiguous properties are not assigned; occupancy is unverified."
    target = targets[0]
    property_id = matches[0].footprintId
    if property_id not in target.assignedPropertyIds:
        if len(target.assignedPropertyIds) >= 250:
            return roster, "This unit already has the maximum 250 assigned properties."
        target.assignedPropertyIds.append(property_id)
    return roster, None
