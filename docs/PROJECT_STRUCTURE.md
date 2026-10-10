# Project Structure

## Proposed stack

- Frontend: React with Vite, TypeScript, CesiumJS as the primary editable 3D scene, and MapLibre/OpenFreeMap as the lightweight fallback renderer.
- Backend: Python with FastAPI, Pydantic, an async HTTP client, and a small deterministic simulation module.
- Runtime: one browser workstation and one local Python process. No login, database, or multi-user synchronization is required for the first demo.
- Storage: checked-in venue fixtures and generated audio cache for reliable offline fallback.

## Repository layout

```text
aero-hazard/
|-- docs/
|   |-- README.md
|   |-- PROJECT_STRUCTURE.md
|   |-- DOMAIN_OBJECTS.md
|   `-- API_AND_MODEL_PLAN.md
|-- frontend/
|   |-- public/
|   |   |-- audio-cache/
|   |   `-- fixtures/
|   |       |-- venue-scenario.json
|   |       |-- venue-weather.json
|   |       `-- venue-context.geojson
|   |-- src/
|   |   |-- app/
|   |   |   |-- AppShell.tsx
|   |   |   |-- appState.ts
|   |   |   `-- apiClient.ts
|   |   |-- components/
|   |   |   |-- command-center/
|   |   |   |   |-- CommandCenter.tsx
|   |   |   |   |-- HeaderStatus.tsx
|   |   |   |   `-- ScenarioBanner.tsx
|   |   |   |-- map/
|   |   |   |   |-- MapViewport.tsx
|   |   |   |   |-- TerrainLayer.ts
|   |   |   |   |-- SceneMode.ts
|   |   |   |   |-- CesiumScene.ts
|   |   |   |   |-- EditableObjects.ts
|   |   |   |   |-- GooglePhotorealisticScene.ts
|   |   |   |   |-- MapSessionGuard.ts
|   |   |   |   |-- PlumeLayer.ts
|   |   |   |   |-- GasLayer.ts
|   |   |   |   |-- GasVolumeRenderer.ts
|   |   |   |   |-- PlumeWebGLRenderer.ts
|   |   |   |   |-- plumeCoordinates.ts
|   |   |   |   |-- UnitMarkers.tsx
|   |   |   |   `-- ContextFeatures.tsx
|   |   |   |-- dispatcher/
|   |   |   |   |-- DispatchConsole.tsx
|   |   |   |   |-- Transcript.tsx
|   |   |   |   `-- AudioControls.tsx
|   |   |   |-- controls/
|   |   |   |   |-- HazardPicker.tsx
|   |   |   |   |-- ReleaseControls.tsx
|   |   |   |   |-- WeatherControls.tsx
|   |   |   |   `-- Timeline.tsx
|   |   |   `-- panels/
|   |   |       |-- HazardMetrics.tsx
|   |   |       |-- ActionPlan.tsx
|   |   |       |-- UnitRoster.tsx
|   |   |       `-- AssumptionsPanel.tsx
|   |   |-- domain/
|   |   |   |-- scenario.ts
|   |   |   |-- dispatch.ts
|   |   |   `-- map.ts
|   |   |-- hooks/
|   |   |   |-- useScenario.ts
|   |   |   |-- useTimeline.ts
|   |   |   `-- useAudioQueue.ts
|   |   `-- styles/
|   |       `-- command-center.css
|   `-- package.json
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- api/
|   |   |   |-- routes_dispatch.py
|   |   |   |-- routes_scenario.py
|   |   |   |-- routes_context.py
|   |   |   `-- routes_audio.py
|   |   |-- domain/
|   |   |   |-- models.py
|   |   |   |-- enums.py
|   |   |   `-- validation.py
|   |   |-- services/
|   |   |   |-- gemini_dispatcher.py
|   |   |   |-- elevenlabs_voice.py
|   |   |   |-- google_3d_tiles.py
|   |   |   |-- weather_client.py
|   |   |   |-- historical_weather.py
|   |   |   |-- nws_alerts.py
|   |   |   |-- air_quality_client.py
|   |   |   |-- osm_context.py
|   |   |   |-- elevation_client.py
|   |   |   |-- routing_client.py
|   |   |   `-- cache.py
|   |   |-- simulation/
|   |   |   |-- plume_solver.py
|   |   |   |-- plume_geometry.py
|   |   |   |-- hazard_profiles.py
|   |   |   |-- wind_vectors.py
|   |   |   |-- terrain_mask.py
|   |   |   `-- metrics.py
|   |   `-- fixtures/
|   |       |-- hazard-library.json
|   |       |-- venue-scenario.json
|   |       `-- context-response.json
|   |-- tests/
|   |   |-- test_validation.py
|   |   |-- test_dispatch_tools.py
|   |   `-- test_plume_solver.py
|   |-- requirements.txt
|   `-- .env.example
|-- .gitignore
`-- README.md
```

## Frontend responsibilities

The frontend owns presentation and interaction state, not provider secrets or authoritative scenario mutation.

- `MapViewport` selects `EDITABLE_3D`, `OPEN_3D`, or optional `PHOTOREALISTIC` mode and displays terrain, buildings, source marker, gas layers, units, routes, and context features.
- `CesiumScene` owns the Cesium viewer, camera, terrain, imagery, optional 3D Tiles, credits, and render loop.
- `GooglePhotorealisticScene` loads the Google root tileset only when the session guard permits it, reuses the active three-hour session, enables on-screen credits, and falls back to `OPEN_3D` on quota, coverage, billing, or network errors.
- `MapSessionGuard` counts root tileset sessions locally, enforces configured daily/monthly safety limits, and blocks new Google requests before the application reaches its safety threshold. It is an application guard, not a replacement for Google Cloud quotas.
- `EditableObjects` owns application-generated building footprints, incident objects, unit markers, barriers, isolation rings, and selection/picking state. Streamed provider meshes remain read-only.
- `GasLayer` owns one independently toggleable gas visual layer per hazard and connects timeline/scenario edits to the renderer.
- `GasVolumeRenderer` uses Cesium particles and batched translucent primitives first, with bounded voxel rendering as a later quality upgrade.
- `PlumeLayer` is the MapLibre fallback renderer. It registers a `custom` layer with `renderingMode: "3d"` and passes compact frame buffers to `PlumeWebGLRenderer`.
- `PlumeWebGLRenderer` is retained for the MapLibre fallback and uses Three.js instanced meshes for particles, soft sprites, and optional volume cells.
- `plumeCoordinates` converts longitude/latitude/altitude values and local-meter offsets into MapLibre Mercator coordinates. It is the only place that handles map projection math for the plume.
- `DispatchConsole` sends transcript text and current scenario version to the backend, then renders the assistant message and any returned scenario patch.
- `Timeline` selects a simulation time from 0 to 120 minutes and requests or interpolates the corresponding plume frame.
- `HazardMetrics`, `ActionPlan`, and `AssumptionsPanel` display explainable outputs and their source assumptions.
- `fixtures/` allows the full screen to work when every external API is unavailable.

The main editable 3D interaction is: select or drag the incident source, change release or gas controls, scrub the timeline, toggle a gas layer, and see the backend return a new validated `GasVisualFrame`. The scene updates application-owned primitives without attempting to edit a provider's streamed photogrammetry mesh.

## Backend responsibilities

The backend owns validation, orchestration, external API access, secrets, caching, and deterministic calculations.

- `routes_dispatch` accepts a dispatch message and returns a validated command result, assistant response, and optional scenario patch.
- `routes_scenario` loads the baseline scenario and applies manual-control patches after validation.
- `routes_context` retrieves cached weather, NWS alerts, air quality, elevation, OpenStreetMap features, and unit routes for a small radius around the incident.
- `routes_audio` turns approved short responses into ElevenLabs audio or serves an existing cached clip.
- `gemini_dispatcher` uses structured output and function declarations. Gemini may propose changes, but Pydantic validation decides what can be applied.
- `simulation` calculates the visible approximation from the validated scenario. The LLM never calculates concentration, wind transport, or safety thresholds.
- `plume_geometry` converts scalar simulation cells into bounded visual primitives with density bands, local altitude, opacity, and a `isApproximation` flag.
- `terrain_mask` supplies cached elevation and simplified building/terrain obstruction data to the solver and geometry builder.
- `cache` stores fixture data, recent API responses, and generated audio so a failed public endpoint does not break the presentation.
- `weather_client`, `nws_alerts`, and `air_quality_client` normalize external meteorological data into the internal weather/context contracts.
- `historical_weather` resolves incident time versus report time, retrieves the 24-hour wind window, selects/interpolates the incident-time sample, and records confidence/provenance.
- `routing_client` requests a small number of OSRM routes and returns a straight-line fallback when the public router is unavailable.
- `google_3d_tiles` owns configuration and status for the dedicated Google Maps project. It never proxies or stores Google tile content; the browser renderer requests tiles directly with the restricted public key.

## Request flow

```text
Browser input
    -> FastAPI dispatch endpoint
    -> Gemini intent extraction / tool proposal
    -> Pydantic command validation
    -> Scenario version increment
    -> deterministic plume and metric recalculation
    -> optional action-plan generation
    -> ElevenLabs audio for the short spoken response
    -> frontend map, timeline, metrics, transcript, and audio update
```

## Boundary rules

- Keep Gemini and ElevenLabs keys in the backend environment only.
- Keep simulation state versioned. A stale browser command must not overwrite a newer scenario.
- Treat external weather and map responses as advisory inputs, never as required startup dependencies.
- Keep the LLM output short and structured. Send only a concise response to ElevenLabs to protect the free credit pool.
- Always show whether values came from `LIVE`, `CACHED`, or `DEMO` data.
- In `PHOTOREALISTIC` mode, display Google Maps/data attribution and the current root-session counter. Do not hide billing-sensitive provider state.
- Never treat a billing budget as a hard cutoff. Use Google Cloud quota limits plus the application session guard, and fall back to `OPEN_3D` before the configured limit.
- Keep OpenFreeMap, OpenStreetMap, OpenMapTiles, and terrain-provider attribution visible in the map controls.
- Treat incident time and report time as separate fields. Recompute the plume against incident-time weather, then persist the selected wind history with the scenario version.
