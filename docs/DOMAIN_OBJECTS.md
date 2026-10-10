# Domain Objects

These are planning contracts. The eventual Python Pydantic models and frontend TypeScript types should implement the same field names and meanings.

## `ScenarioPayload`

The versioned state that drives the map, simulation, and panels.

```json
{
  "scenarioId": "INC-8892",
  "version": 7,
  "status": "ACTIVE",
  "location": {
    "latitude": 40.3487,
    "longitude": -74.6593,
    "label": "Hackathon venue main building",
    "source": "DEMO"
  },
  "hazard": {
    "hazardId": "chlorine",
    "category": "CHEMICAL",
    "displayName": "Chlorine gas",
    "molecularWeightGPerMol": 70.9,
    "densityRelativeToAir": 2.47,
    "buoyancyClass": "HEAVY",
    "decayHalfLifeSeconds": null,
    "thresholdsPpm": {
      "trace": 0.5,
      "pel": 1.0,
      "idlh": 10.0
    }
  },
  "release": {
    "rateKgPerSecond": 15.0,
    "durationMinutes": 30,
    "isPressurized": true,
    "hasExploded": false,
    "sourceHeightMeters": 1.5
  },
  "timing": {
    "incidentOccurredAt": "2026-10-09T18:00:00Z",
    "incidentReportedAt": "2026-10-09T18:30:00Z",
    "incidentTimeConfidence": "APPROXIMATE",
    "reportDelayMinutes": 30
  },
  "weather": {
    "windSpeedMetersPerSecond": 4.5,
    "windDirectionFromDegrees": 225,
    "temperatureCelsius": 18.0,
    "stabilityClass": "D",
    "source": "CACHED",
    "selectedAt": "2026-10-09T18:00:00Z",
    "historyId": "wind-INC-8892-20261009"
  },
  "windHistory": {
    "windowStart": "2026-10-08T18:00:00Z",
    "windowEnd": "2026-10-09T18:30:00Z",
    "intervalMinutes": 60,
    "provider": "OPEN_METEO",
    "providerModel": "AUTO",
    "samples": [
      { "timestamp": "2026-10-09T17:00:00Z", "speedMetersPerSecond": 4.2, "directionFromDegrees": 220 },
      { "timestamp": "2026-10-09T18:00:00Z", "speedMetersPerSecond": 4.5, "directionFromDegrees": 225 },
      { "timestamp": "2026-10-09T19:00:00Z", "speedMetersPerSecond": 4.8, "directionFromDegrees": 230 }
    ],
    "selectedSampleMethod": "EXACT_TIMESTAMP",
    "confidence": "HISTORICAL_FORECAST",
    "retrievedAt": "2026-10-09T18:31:00Z"
  },
  "activeUnits": [
    {
      "unitId": "ENGINE-4",
      "label": "Engine Company 4",
      "latitude": 40.3491,
      "longitude": -74.6580,
      "status": "DEPLOYED",
      "note": "Maintain upstream position"
    }
  ],
  "userContext": {
    "latitude": 40.3488,
    "longitude": -74.6591,
    "environmentState": "INDOORS",
    "accuracyMeters": 25,
    "nearbyFeatureIds": ["osm-123", "osm-456"]
  },
  "dataProvenance": {
    "scenario": "DEMO",
    "weather": "CACHED",
    "map": "LIVE",
    "context": "CACHED"
  },
  "mapSession": {
    "mode": "PHOTOREALISTIC",
    "provider": "GOOGLE_MAP_TILES",
    "rootSessionCount": 3,
    "rootSessionLimit": 900,
    "sessionStartedAt": "2026-10-10T14:00:00Z",
    "sessionExpiresAt": "2026-10-10T17:00:00Z",
    "fallbackMode": "OPEN_3D",
    "billingGuardState": "WITHIN_APP_LIMIT"
  }
}
```

## `MapSessionGuard`

The map session guard is a client-side safety contract for the optional Google Photorealistic 3D Tiles mode. It is not a billing system and cannot guarantee a maximum charge by itself.

Required fields:

- `mode`: `PHOTOREALISTIC`, `OPEN_3D`, or `EDITABLE_3D`
- `provider`: `GOOGLE_MAP_TILES`, `CESIUM_ION`, `OPEN_DATA`, or `LOCAL`
- `rootSessionCount` and `rootSessionLimit`
- `sessionStartedAt`, `sessionExpiresAt`, and `fallbackMode`
- `billingGuardState`: `DISABLED`, `WITHIN_APP_LIMIT`, `FALLBACK_REQUIRED`, or `PROVIDER_ERROR`

The guard increments only when the application creates a new Google root tileset session. Camera movement, plume animation, timeline scrubbing, gas changes, and unit updates must not increment it. At the app limit, switch to `OPEN_3D` without requesting another Google root tileset.

## `HazardProfile`

Static, reviewed simulation metadata. This belongs in a checked-in library, not in an LLM prompt as the source of truth.

Required fields:

- `hazardId`, `displayName`, `category`
- `molecularWeightGPerMol`, `densityRelativeToAir`, `buoyancyClass`
- `diffusionCoefficient`, `settlingVelocity`, and optional `decayConstantPerSecond`
- `thresholdsPpm` or `thresholdsRelativeDose`
- `defaultPpeLevel`, `defaultIsolationRadiusMeters`
- `assumptions` and `sourceNotes`

Initial profiles: chlorine, ammonia, methane, iodine-131, cesium-137, and aerosol pathogen. Keep the values explicitly labeled as demonstration assumptions until reviewed by a qualified subject-matter expert.

## `WindHistory`

`WindHistory` preserves the meteorological conditions used for a delayed incident report.

Required fields:

- `windowStart`, `windowEnd`, and `intervalMinutes`
- `provider`, `providerModel`, `retrievedAt`
- `samples[]` with `timestamp`, `speedMetersPerSecond`, and `directionFromDegrees`
- `selectedSampleMethod`: `EXACT_TIMESTAMP`, `LINEAR_INTERPOLATION`, `NEAREST_SAMPLE`, or `CURRENT_FALLBACK`
- `confidence`: `LIVE_HISTORICAL`, `HISTORICAL_FORECAST`, `CACHED`, or `CURRENT_FALLBACK`

The selected sample must be the one used by the plume solver at simulation time zero. A report with no known incident time uses report time and sets `incidentTimeConfidence` to `UNKNOWN`; it must not imply that historical conditions are known.

## `DispatchMessage`

```json
{
  "messageId": "msg-018",
  "scenarioId": "INC-8892",
  "expectedScenarioVersion": 7,
  "channel": "TEXT",
  "text": "Deploy Engine 4 to 5th Ave and mark the tank as exploded.",
  "createdAt": "2026-10-09T18:30:00Z"
}
```

If a dispatch message supplies a delayed incident time, it may include:

```json
{
  "incidentOccurredAt": "2026-10-09T18:00:00Z",
  "incidentTimeConfidence": "APPROXIMATE"
}
```

## `DispatchResult`

```json
{
  "messageId": "msg-018",
  "accepted": true,
  "assistantText": "Engine 4 is deployed to 5th Avenue. Explosion state recorded. Recalculating the plume.",
  "commands": [
    {
      "commandType": "DEPLOY_UNIT",
      "unitId": "ENGINE-4",
      "target": { "latitude": 40.3491, "longitude": -74.6580 }
    },
    {
      "commandType": "TRIGGER_EVENT",
      "eventType": "EXPLOSION"
    }
  ],
  "scenarioPatch": {
    "release.hasExploded": true
  },
  "newScenarioVersion": 8,
  "audio": {
    "status": "READY",
    "cacheKey": "dispatch-engine-4-explosion-v1"
  }
}
```

Supported command types for the first demo:

- `UPDATE_HAZARD`
- `UPDATE_RELEASE`
- `UPDATE_WEATHER`
- `DEPLOY_UNIT`
- `MOVE_UNIT`
- `TRIGGER_EVENT`
- `SET_USER_CONTEXT`
- `REQUEST_ACTION_PLAN`

## `PlumeFrame`

The simulation output for one point on the timeline.

```json
{
  "scenarioId": "INC-8892",
  "scenarioVersion": 8,
  "timeMinutes": 30,
  "grid": {
    "origin": { "latitude": 40.343, "longitude": -74.666 },
    "cellSizeMeters": 25,
    "columns": 80,
    "rows": 80,
    "baseAltitudeMeters": 0,
    "verticalLayers": 8,
    "verticalCellSizeMeters": 8
  },
  "cells": [
    { "column": 40, "row": 40, "layer": 0, "concentration": 12.4, "band": "IDLH", "terrainElevationMeters": 18.2 },
    { "column": 41, "row": 40, "layer": 1, "concentration": 4.2, "band": "PEL", "terrainElevationMeters": 18.5 }
  ],
  "visualPrimitives": {
    "particles": [
      { "longitude": -74.6593, "latitude": 40.3487, "altitudeMeters": 3, "radiusMeters": 18, "concentration": 12.4, "band": "IDLH", "opacity": 0.72 }
    ],
    "volumeCells": [
      { "longitude": -74.6591, "latitude": 40.3488, "groundElevationMeters": 18.2, "heightMeters": 8, "radiusMeters": 22, "concentration": 4.2, "band": "PEL", "opacity": 0.42 }
    ]
  ],
  "maxConcentration": 12.4,
  "isApproximation": true,
  "terrainSource": "CACHED",
  "obstructionSource": "DEMO"
}
```

The backend grid is the simulation source of truth. `visualPrimitives` is a bounded render payload derived from that grid so the browser does not need to solve physics. The browser may receive contours or compact raster data later, but it should keep the semantic fields `timeMinutes`, `band`, `maxConcentration`, `isApproximation`, `terrainSource`, and `obstructionSource`.

For every visual primitive, altitude is measured in meters above local ground and concentration is in the hazard profile's declared unit. The frontend must never infer height from color or concentration. A frame without `visualPrimitives` can fall back to a flat 2D layer, but the demo scenario should always include them.

## `HazardMetrics`

```json
{
  "hazardSeverity": "CRITICAL",
  "timeMinutes": 30,
  "peakConcentration": 12.4,
  "peakBand": "IDLH",
  "affectedAreaSquareMeters": 184000,
  "downwindDistanceMeters": 680,
  "isolationRadiusMeters": 300,
  "confidence": "DEMO_ESTIMATE",
  "assumptions": [
    "Steady wind during the selected frame",
    "Simplified terrain interaction",
    "No indoor infiltration model"
  ]
}
```

## `EmergencyActionPlan`

The action plan is advisory text assembled from validated simulation results, hazard-library rules, and context features.

Required fields:

- `planId`, `scenarioId`, `generatedAt`, `modelId`
- `hazardSeverity`
- `immediateActions` as short ordered strings
- `firstResponderPpe`
- `isolationRadiusMeters`
- `shelterGuidance`
- `decontaminationGuidance`
- `nearbyContextUsed`
- `disclaimer` stating that the result is a simulation

The model must not invent live emergency resources. If a feature is absent or stale, it must say that it is unknown.

## `ContextFeature`

Normalized OpenStreetMap data used for visual context and advisory ranking.

```json
{
  "featureId": "osm-123",
  "featureType": "WATER_SOURCE",
  "displayName": "Drinking water",
  "latitude": 40.3484,
  "longitude": -74.6588,
  "distanceMeters": 45,
  "tags": { "amenity": "drinking_water" },
  "source": "OPENSTREETMAP",
  "retrievedAt": "2026-10-09T18:25:00Z"
}
```

Use conservative feature types: `WATER_SOURCE`, `FIRE_HYDRANT`, `SCHOOL`, `HOSPITAL`, `ROAD`, `BUILDING`, and `HVAC_RELATED`. Do not claim that an HVAC intake exists unless OSM data or a demo fixture explicitly identifies it.

## `ApiEnvelope`

All backend responses should include:

```json
{
  "ok": true,
  "data": {},
  "source": "LIVE",
  "requestId": "req-123",
  "warnings": []
}
```

This gives the frontend a consistent way to show stale data, fallback mode, validation warnings, and request identifiers.
