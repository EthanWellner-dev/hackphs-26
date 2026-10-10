# API And Model Plan

## Free-first policy

The baseline must remain runnable without paid map usage. We will support an optional USA-wide `PHOTOREALISTIC` mode using Google Photorealistic 3D Tiles with billing enabled, but the project must enforce a quota below the included free allowance and fall back before any paid map requests can occur. API keys may still be required. Keep a checked-in open-scene fallback and demo fixture for every external dependency.

Free does not mean unlimited or production-grade. Public endpoints have fair-use policies, provider quotas can change, and the quota snapshot below is the team's supplied AI Studio view on 2026-10-09. Verify the active project's limits before the event.

## Provider choices

| Capability | Provider | Cost path | Key required | Planned use | Fallback |
|---|---|---:|---:|---|---|
| Intent parsing, tool selection, action-plan drafting | Google Gemini API | Free AI Studio quota | Yes | Python backend only | Deterministic command shortcuts plus demo responses |
| Speech input transcription | Gemini 3.5 Transcribe | Free quota shown by team | Yes | Optional microphone intake | Browser text input |
| Dispatcher speech output | ElevenLabs Text to Speech | Free plan, 10,000 shared monthly credits shown on pricing page | Yes | Short confirmations and critical advisories | Cached audio clips, then text-only response |
| Editable 3D scene renderer | CesiumJS | Open-source, free | No for the engine | Globe/terrain camera, pickable entities/primitives, custom models, particle systems, voxel volumes, custom shaders | MapLibre 3D map mode |
| Lightweight 3D map renderer | MapLibre GL JS | Open-source, free | No | Camera pitch/bearing, terrain, extrusions, custom plume layer, markers | Local GeoJSON coordinate-grid renderer |
| Vector basemap and building footprints | OpenFreeMap | Public instance is free and keyless; attribution required | No | Streets, labels, OSM building source, 3D building extrusion properties | Local venue GeoJSON fixture |
| 3D terrain tiles | Mapterhorn Terrarium tiles | Public global tiles, no key in the documented MapLibre example; no SLA | No | Raster DEM terrain surface and hillshade | Open-Meteo elevation grid or local DEM fixture |
| Editable 3D gas rendering | CesiumJS `ParticleSystem`, `Primitive`, `CustomShader`, and optional `VoxelPrimitive` | Open-source, free | No for local/custom data | Semi-transparent particles, ellipsoids, volume cells, threshold coloring, picking, and time updates | Cesium ellipsoid entities or MapLibre custom WebGL layer |
| USA-wide photorealistic 3D tiles | Google Photorealistic 3D Tiles through CesiumJS | Billing account required; first 1,000 root tileset requests/month are listed at no cost | Yes | Textured aerial/photogrammetry scene across supported populated areas | Cesium open scene with OSM buildings/terrain |
| Free global 3D content | Cesium ion Community assets | Free individual/non-commercial account with quotas and token | Yes | Global imagery, terrain, and real-world 3D content; strongest low-effort fallback | Local scene assets |
| U.S. public aerial imagery | USGS/NAIP and The National Map services | Public/open or public-domain U.S. data; download/service availability varies | Usually no | High-resolution orthophoto ground texture for a fixed U.S. venue | OpenFreeMap or local neutral imagery |
| U.S. public 3D source data | USGS 3DEP LiDAR and DEM | Free of charge and without use restrictions | No | Terrain, vegetation, and structure point data for building/tree reconstruction | Mapterhorn/Open-Meteo terrain |
| Open aerial imagery commons | OpenAerialMap | Openly licensed imagery, coverage is uneven | No for browsing; service/API behavior varies | Venue-specific orthophoto if coverage exists | NAIP/local capture |
| Street-level context imagery | Mapillary or KartaView | Free/open access subject to provider terms; Mapillary requires an access token | Mapillary: Yes; KartaView: varies | Ground-level realism and visual context; not a complete 3D city mesh | Static local reference images |
| Current, historical, and forecast weather | Open-Meteo Forecast API | Free non-commercial usage, no key | No | Wind speed/direction, temperature, humidity, clouds, radiation, pressure; historical window for delayed reports | `venue-weather.json` |
| U.S. official forecasts and alerts | NOAA/National Weather Service API | Public, free, no key; User-Agent required | No | Active alerts, forecast office, hourly forecast, observations | Open-Meteo weather plus cached alerts |
| Air-quality context | Open-Meteo Air Quality API | Free non-commercial usage, no key | No | PM, ozone, NO2, CO, SO2, ammonia, U.S. AQI | Cached air-quality fixture; never substitute for plume concentration |
| Point elevation lookup | Open-Meteo Elevation API | Free for demo use, no key | No | Venue elevation and small grid samples | Cached elevation fixture |
| Nearby OSM features | Overpass API | Free public instances with fair-use limits | No | Hydrants, water, schools, hospitals, roads | `context-response.json` |
| Unit route and travel estimate | OSRM public router | Free public demo endpoint, no key; cache and keep requests low | No | Route an engine to a dispatch target and draw the route | Straight-line bearing/distance calculation |
| Browser location | Web Geolocation API | Built into browser | No | Optional user context | Fixed demo position and explicit permission denial state |

### Explicit exclusions

- Mapbox is excluded from the free baseline because it requires an access token and its terms/quotas add a presentation dependency.
- OpenWeather is excluded because Open-Meteo and NOAA supply the required wind, forecast, and alert data without a key for this non-commercial hackathon demo.
- Google Maps Platform is isolated to the optional Photorealistic 3D Tiles renderer. It is not used for geocoding, weather, routing, Places, or 2D maps, so the billing-sensitive project has one map SKU to monitor.
- Firebase/WebSockets, a hosted database, and authentication are excluded from the first demo because they do not improve the 2.5-minute judge flow.
- Nominatim geocoding is optional only. For the fixed venue, store coordinates locally and avoid an unnecessary rate-limited request.

Google Photorealistic 3D Tiles are documented as requiring a Google Cloud project with billing and an API key. Google lists 1,000 free monthly root tileset events and $6 per 1,000 additional events at the first paid tier. One root request can support renderer tile requests for up to three hours, so a viewer session should reuse the same tileset rather than recreate it on every React update.

A $1 Cloud Billing budget is an alerting backstop, not a guaranteed hard spending cutoff. Make the cost boundary explicit with these controls:

1. Use a dedicated Google Cloud project only for Photorealistic 3D Tiles.
2. Restrict the browser API key to the Map Tiles API and the deployed origins/localhost development origins.
3. Set the Photorealistic 3D Tiles root-tileset quota below the free allowance, such as 100 root sessions/day and 900/month. The quota is the service stop; the budget is only a notification.
4. Configure budget notifications at 50%, 80%, and 100% of $1.
5. Reuse one root tileset/session for up to three hours. Camera movement, timeline scrubbing, gas edits, and unit updates must never request a new root tileset.
6. Add an application session guard. When the configured monthly or daily safety count is reached, switch to `OPEN_3D` before making another Google request.
7. Keep the Google project free of other Maps SKUs. Use Open-Meteo, NOAA, Overpass, and OSRM for the other services already selected.
8. Display the current root-session count and provide a one-click `Use open 3D mode` control.

Recommended safety settings:

```text
GOOGLE_PHOTOREALISTIC_ENABLED=true
GOOGLE_PHOTOREALISTIC_MONTHLY_SESSION_LIMIT=900
GOOGLE_PHOTOREALISTIC_DAILY_SESSION_LIMIT=100
GOOGLE_PHOTOREALISTIC_SESSION_HOURS=3
GOOGLE_PHOTOREALISTIC_FALLBACK_MODE=OPEN_3D
GOOGLE_MAPS_PROJECT_SCOPE=photorealistic-only
```

The 900 monthly limit leaves a 100-request buffer below the listed 1,000 free events. It does not guarantee a zero-dollar bill if Google changes pricing, counts a different event, or credentials are used outside the application. Check Google Cloud quota and billing reports before the demo.

## Free photorealism alternatives

### 1. Cesium ion Community: fastest free global fallback

CesiumJS itself is Apache 2.0 and free. Cesium's current quickstart says a free ion account can provide global satellite imagery and real-world 3D content, and the free Community plan is intended for individual, personal, non-commercial, or exploratory use within quotas. This is the first alternative to test because it requires the least custom data work.

Expected quality: better geographic context than plain extrusions, but not guaranteed to match Google's dense photogrammetry, tree geometry, or façade detail at the venue. It requires a Cesium ion token and the team must confirm that the hackathon project fits the Community plan's usage terms.

### 2. USGS NAIP + 3DEP: strongest genuinely free U.S. data foundation

For a U.S. venue, use free public data to build a local scene:

- NAIP or other public orthoimagery supplies the aerial texture.
- 3DEP LiDAR supplies point data containing terrain, vegetation, and structures where coverage exists.
- 3DEP DEM supplies a reliable terrain surface and elevation fallback.
- OSM supplies semantic building footprints, road names, and context labels.

This can produce a convincing local venue view, especially from the same elevated oblique camera angle as the reference. It is not an instant tile API: a preprocessing step must clean the LiDAR, classify ground/vegetation/buildings, create meshes or 3D Tiles, and host the result locally or on a static file server. USGS states that 3DEP products are free of charge and without use restrictions, which makes this the safest data source for a competition demo.

Important limitation: standard DEMs show bare earth; they do not automatically provide photorealistic trees. Vegetation must come from LiDAR classification, a local procedural tree layer, or individually placed low-poly tree models. That is still enough to make the gas visibly interact with vegetation and structures.

### 3. OpenAerialMap: useful only if the venue is covered

OpenAerialMap is an open collection of openly licensed aerial imagery and may provide a high-resolution orthophoto for a particular venue or event. Coverage is uneven, so it is a discovery/fallback source rather than the primary plan. It provides imagery, not a ready-made photogrammetric 3D mesh. Combine it with 3DEP or another elevation source and local building/tree geometry.

### 4. Mapillary/KartaView: ground truth, not a 3D basemap

Mapillary and KartaView can add real street-level imagery or provide visual references for building façades, trees, hydrants, and entrances. Mapillary's API requires an access token, and its documented image/mesh/SfM fields should not be treated as a guaranteed venue-wide photogrammetry tileset. KartaView is an open street-level imagery platform, but it is also not a drop-in 3D city provider.

Use these services only for a side panel, incident evidence thumbnails, or to manually improve the fixed venue asset. Do not make the main 3D gas visualization depend on finding complete street imagery coverage.

### 5. Build a fixed venue photogrammetry asset: highest visual payoff

If the venue can be captured legally with a phone, 360 camera, or drone, a short local capture can be processed into a textured mesh using open tools such as OpenDroneMap/WebODM or Meshroom, then converted to glTF/3D Tiles for CesiumJS. This is not a remote API and requires permission, capture time, and preprocessing, but it is the only free path that can realistically approach the screenshot's tree and façade detail for the exact hackathon location.

Use only imagery the team owns or has permission to use. Do not scrape or reconstruct a venue from Google/Mapillary imagery without checking the applicable license and terms.

## Recommendation for the hackathon

Use a two-mode USA-wide scene plan:

| Mode | Data | Quality | Cost risk | Role |
|---|---|---:|---:|---|
| `PHOTOREALISTIC` | Google Photorealistic 3D Tiles across supported U.S. areas | High | Controlled by root-request quota and dedicated project | Primary visual mode when the safety guard allows it |
| `OPEN_3D` | Cesium ion/open terrain plus OSM buildings | Medium | No Google Maps usage | Automatic fallback when quota, billing, coverage, or network is unavailable |
| `EDITABLE_3D` | Cesium application-owned building/terrain approximations | Medium | No Google Maps usage | Deterministic offline fallback for rehearsal |

Do not prefetch, scrape, extract, analyze, or permanently cache Google Photorealistic 3D Tiles. Use the service only for visualization, respect response cache headers, keep Google attribution visible, and keep the gas simulation independent from the provider mesh.

## Gas interaction with trees and buildings

The gas should interact with scene geometry through explicit application data:

- Building footprints/meshes become an obstruction mask for the plume approximation.
- Tree instances become porous obstruction/drag volumes, not opaque walls.
- Gas volume cells are rendered with depth testing and alpha blending, so they pass in front of and behind buildings as the camera moves.
- A selected building/tree can show a contextual concentration readout without changing the provider mesh.
- The UI should include toggles for `BUILDINGS`, `TREES`, `GAS VOLUME`, `PARTICLES`, and `OBSTRUCTION MASK` so the interaction is obvious during the judge demo.

The gas solver remains a visualization approximation. It can make the cloud bend around buildings and slow/settle in low areas, but it must not claim that a public imagery source makes the atmospheric physics scientifically validated.

## Gemini model selection

The model names below follow the team's supplied AI Studio quota table. RPM, TPM, and RPD are included to make the design operational; they are not promises of capacity.

| Priority | Model | Supplied free quota | Assignment | Why it belongs |
|---:|---|---|---|---|
| 1 | `gemini-3.8-flash` | 5 RPM / 250K TPM / 20 RPD | Primary dispatcher reasoning, structured command extraction, concise action-plan drafting | Best primary impression from the listed current Flash models; enough quality for tool selection and a small context window |
| 2 | `gemini-3.5-flash-lite` | 15 RPM / 250K TPM / 500 RPD | Fast intent classification, parameter extraction, and overflow requests | Highest practical request budget in the list; protects the primary model from repetitive UI traffic |
| 3 | `gemini-3.1-flash-lite` | 15 RPM / 250K TPM / 500 RPD | Second lightweight fallback and transcript cleanup | Same generous quota profile; gives the backend a model-level fallback if one model is unavailable |
| 4 | `gemini-3.5-transcribe` | 3 RPM / 10K TPM / 25 RPD | Optional microphone speech-to-text for judge intake | A dedicated transcription model is easier to constrain than sending arbitrary audio to the command parser |
| 5 | `gemini-2.5-flash-native-audio-preview-12-2025` | Unlimited RPM / 1M TPM / unlimited RPD in supplied table | Optional live audio experiment only | Strong wow-factor for a direct voice agent, but it is deliberately not the baseline because ElevenLabs is the sponsor integration and should own spoken output |

### Model routing rules

1. Use `gemini-3.8-flash` for a new dispatch turn when the request could mutate the scenario or produce a judge-facing action plan.
2. Use `gemini-3.5-flash-lite` for simple classification, missing-field detection, transcript cleanup, and repeated status confirmations.
3. Use `gemini-3.1-flash-lite` when the primary lightweight route errors or is temporarily unavailable.
4. Use `gemini-3.5-transcribe` only for an explicit audio upload or microphone transcription request. Do not transcribe every UI event.
5. Treat the native-audio model as an experiment behind a feature flag. It must not silently replace ElevenLabs.
6. Enforce a per-turn token/output cap and keep the action-plan prompt small. The free RPD limits, especially 20 requests for the primary model, are the main demo risk.

### Models intentionally not selected

- `Gemini 2.5 Flash` and `Gemini 2.5 Flash Lite` are viable compatibility fallbacks, but the supplied 20 RPD limits are less useful than the 3.x Lite quotas.
- Pro models, image models, video models, Deep Research, robotics, and computer-use models are either zero-quota in the supplied table, unnecessary, or a poor fit for a 2.5-minute emergency demo.
- Embeddings are not needed for a small checked-in hazard library. Add an embedding model only if the library grows enough to justify retrieval.
- Gemini TTS models are intentionally not used because the required sponsor integration is ElevenLabs.

## Gemini backend contract

The backend should ask Gemini for a structured response with these logical fields:

```text
assistant_text: short dispatcher response
commands: zero or more typed command objects
clarifying_questions: zero or more questions
action_plan_requested: boolean
confidence: HIGH | MEDIUM | LOW
```

The backend then validates every command against the current `ScenarioPayload` and a whitelist of command types. Gemini can propose a `DEPLOY_UNIT` command, but it cannot directly write state, invent a unit, or change a hazard profile.

## ElevenLabs plan

Use ElevenLabs only after the backend has produced a short approved `assistant_text`. Recommended constraints:

- Keep spoken responses under roughly 250 characters whenever possible.
- Cache by normalized text plus voice/model identifier.
- Generate audio for confirmations and the first critical advisory; do not speak every metric update.
- Store generated files in `frontend/public/audio-cache/` for the rehearsal path.
- Keep the ElevenLabs API key in the Python backend, never in browser code.
- Display a text transcript even when audio generation fails.

The free plan shown by ElevenLabs lists 10,000 shared monthly credits. At one credit per character for common TTS usage, a concise demo script has enough room, but repeated judge experimentation can exhaust it. The cache and text-only fallback are required, not optional polish.

## Frontend map plan

### Recommended stack: CesiumJS for the editable 3D scene

Use CesiumJS as the primary scene when the requirement is an editable 3D map with gas volumes. Use MapLibre/OpenFreeMap as the lightweight fallback or 2D/3D extrusion mode.

| Scene mode | Visual source | Editable application layers | Free baseline |
|---|---|---|---|
| `EDITABLE_3D` | Application-owned buildings/terrain, open imagery or a simple basemap | Fully editable incident, buildings, units, barriers, rings, particles, and gas volumes | Yes |
| `OPEN_3D` | OpenFreeMap/OSM or local vector data plus terrain | Editable application overlays and generated building geometry | Yes, subject to public endpoint fair use |
| `PHOTOREALISTIC` | Google Photorealistic 3D Tiles across supported U.S. coverage | Editable overlays and gas volumes; provider mesh itself is streamed/read-only | Billing enabled, quota-guarded |

The reference image is a target for `PHOTOREALISTIC`, not a promise of the free mode. In `EDITABLE_3D`, buildings should be generated from normalized footprint polygons and height attributes so they can be selected, highlighted, hidden, or replaced. External streamed 3D tiles can be picked and styled, but their underlying mesh should be treated as read-only; editable incident objects and gas volumes must remain separate application-owned primitives.

### Cesium gas rendering path

Cesium is a better fit for the gas layer because the scene can combine:

- `ParticleSystem` for animated wind-following tracer particles;
- `Primitive` plus batched `GeometryInstance` objects for translucent ellipsoid/cell volumes;
- `CustomShader` for concentration-to-color/opacity mapping and animated noise;
- `VoxelPrimitive` as an optional higher-quality volume renderer for a bounded concentration grid;
- `CustomDataSource`/entities for editable source points, unit markers, isolation rings, and annotations.

The first free implementation should use a bounded set of instanced ellipsoids and particles. It should not depend on a remote voxel service. Each gas cell is an application-owned object with `gasId`, `timeMinutes`, `longitude`, `latitude`, `groundElevationMeters`, `altitudeMeters`, `radiusMeters`, `concentration`, `thresholdBand`, `opacity`, and `isApproximation`. Updating a slider or dispatch command regenerates these objects from the validated scenario and replaces the active frame.

The visual stack should render gases in this order:

1. Terrain and building scene.
2. Read-only streamed or local building geometry.
3. Low-opacity gas volume cells with depth testing enabled.
4. Additive/alpha-blended tracer particles and wind streaks.
5. Source, unit, isolation, and warning overlays.

Use separate `GasLayer` instances per hazard so chlorine, ammonia, radiological dust, or biological aerosol can be toggled independently. The UI can edit release rate, source height, wind override, opacity, threshold visibility, and selected timeline frame; the backend remains responsible for recomputing the concentration field.

### Free-mode 3D assets

For the fixed venue, the free mode should ship with a small local asset pack:

- building footprint GeoJSON with `heightMeters` and `minHeightMeters`;
- a local height grid or terrain mesh for the venue;
- optional low-poly GLB landmarks for visually important buildings;
- a local aerial or neutral imagery fallback with attribution;
- generated gas sprites/volume geometry owned by the application.

This gives the team reliable, editable 3D objects even when public tiles fail. It also avoids claiming that a streamed photogrammetry mesh is editable.

### MapLibre fallback

MapLibre remains useful for a lighter deployment: OpenFreeMap building extrusions, Mapterhorn terrain, and the existing custom WebGL `PlumeLayer`. The domain contracts should stay renderer-neutral so the same `GasVisualFrame` can be rendered by Cesium or MapLibre. Do not build two complete renderers before the free Cesium path is proven.

Use this as the primary map implementation:

```text
CesiumJS
	scene mode: EDITABLE_3D | OPEN_3D | PHOTOREALISTIC
	buildings: local GeoJSON/GLB or optional streamed 3D Tiles
	terrain: local height grid or optional provider terrain
	gas: application-owned particles, primitives, and optional voxels

MapLibre fallback
	style: https://tiles.openfreemap.org/styles/liberty
	vector source: https://tiles.openfreemap.org/planet
	terrain source: https://tiles.mapterhorn.com/{z}/{x}/{y}.webp
	terrain encoding: terrarium
	plume: custom GeoJSON/canvas/WebGL layer owned by the application
```

MapLibre provides the 3D camera and rendering engine. OpenFreeMap provides the vector style and an OSM/OpenMapTiles building source. The `building` source layer exposes `render_height` and `render_min_height`, which can drive a `fill-extrusion` layer. Mapterhorn's Terrarium tiles provide a global elevation raster source suitable for `setTerrain` and hillshade.

The Cesium scene should start in a tilted local view of the venue with a 55-70 degree downward camera angle, moderate heading, and visual terrain exaggeration where supported. Keep the exaggeration labeled as visual, not scientific. Put the application gas layers above the terrain and use depth testing so gas appears to occupy space around the buildings.

Required map layers:

1. Cesium terrain or the local venue height grid.
2. Local/OpenStreetMap-derived building geometry or optional 3D Tiles.
3. Open imagery, vector labels, and attribution.
4. Incident source marker and isolation rings.
5. OSM context features from the backend.
6. Unit markers and OSRM route lines.
7. Plume contours/particles from the deterministic simulation.

Required attribution in the visible map UI must match the selected source: OpenFreeMap/OpenMapTiles/OSM for the open scene, Mapterhorn for its terrain, Cesium ion for ion-hosted assets, and Google for Photorealistic 3D Tiles. Keep Cesium's credit display enabled.

Public map and terrain instances are appropriate for a hackathon demo, but they are not SLA-backed emergency mapping services. Cache the venue view and keep a local GeoJSON/height-grid fallback. Do not describe the result as operational-grade terrain data.

### Map API responsibilities

The browser should not call Overpass, OSRM, Gemini, or ElevenLabs directly. The frontend map client should only receive:

- a selected scene mode and renderer configuration;
- public style/tile URLs when the open renderer is selected;
- optional Cesium token/provider configuration only when explicitly enabled;
- validated GeoJSON for incident, plume, units, routes, and context features;
- a provenance label for each layer: `LIVE`, `CACHED`, or `DEMO`.

The Python backend should proxy/cache context, routing, weather, elevation, and AI providers. This keeps provider headers, rate limiting, normalization, and fallback behavior in one place.

### 3D gas visual implementation

The gas visual will be a real 3D application layer, not a flat colored polygon:

1. `MapViewport` initializes MapLibre with terrain enabled and a pitched camera.
2. `PlumeLayer` registers a MapLibre `custom` layer with `renderingMode: "3d"`.
3. The custom layer shares MapLibre's WebGL context and camera matrix. Three.js is used inside the layer for instanced rendering and transparent blending; it does not replace MapLibre's basemap or terrain.
4. Each `PlumeFrame` is converted into a bounded set of visual primitives: density-colored particles for motion, soft camera-facing sprites for the visible cloud edge, and optional low-resolution volume cells for the strongest bands.
5. Primitive positions are converted from longitude/latitude/meters into MapLibre's Mercator coordinate space. Ground contact uses the frame's terrain sample or `queryTerrainElevation`; altitude is measured in meters above local ground.
6. Buildings remain visible through the gas using depth testing and alpha blending. The plume solver supplies a simplified building/terrain mask so the cloud can bend around obstacles without pretending to perform a certified CFD calculation.
7. Timeline changes replace or interpolate the active frame. A short animation loop advances particle phase only; it does not call Gemini or an external API per animation frame.

Required visual states:

- `TRACE`: cool blue, low opacity, wide dispersion.
- `PEL`: amber/yellow, medium opacity, visibly follows wind direction.
- `IDLH`: red/magenta, high opacity, concentrated around the source and low terrain.
- `UNKNOWN`: gray outline or hidden, used when a cell is outside the valid simulation domain.

The renderer must have a hard primitive budget for the laptop demo, for example 10,000 particles and 2,000 volume cells. Use instanced buffers and update only the changed frame data. Do not create one React component per particle.

The visual layer must continue to work when terrain tiles fail. In that mode, it uses the local venue height grid and displays `TERRAIN: CACHED` while retaining the same world-coordinate conversion.

## Weather plan

Use Open-Meteo with a narrowly scoped request for the venue. The weather request must be based on the **incident time**, not automatically on the report time. The UI should collect both values:

- `incidentReportedAt`: when the user submits the report;
- `incidentOccurredAt`: when the release is believed to have started, defaulting to report time;
- `incidentTimeConfidence`: `EXACT`, `APPROXIMATE`, or `UNKNOWN`.

For incidents reported up to 24 hours late, request the past 24 hours plus a short forward buffer. Open-Meteo's forecast endpoint supports a `past_hours` parameter for recent historical forecast data. Use an explicit `start_hour` and `end_hour` when available so the response is aligned to the selected incident timestamp:

```text
https://api.open-meteo.com/v1/forecast
	?latitude={lat}&longitude={lon}
	&hourly=temperature_2m,relative_humidity_2m,cloud_cover,shortwave_radiation,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m
	&wind_speed_unit=ms&past_hours=24&forecast_hours=3&timezone=UTC
```

For a report older than the provider's recent-history window, or when higher historical fidelity is needed, use the Open-Meteo Historical Forecast endpoint with a date-bounded request. The backend should choose the endpoint based on the requested incident date and cache the normalized result:

```text
https://historical-forecast-api.open-meteo.com/v1/forecast
	?latitude={lat}&longitude={lon}
	&start_date={incident_date}&end_date={incident_date}
	&hourly=temperature_2m,relative_humidity_2m,cloud_cover,shortwave_radiation,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m
	&wind_speed_unit=ms&timezone=UTC
```

The historical endpoint is a forecast-reanalysis product, not an anemometer reading. Display its source and model timestamp. For the hackathon simulator, hourly wind samples are sufficient; interpolate between adjacent samples for the plume timeline and preserve the original samples for auditability.

Relevant fields:

- `current=temperature_2m,wind_speed_10m,wind_direction_10m,relative_humidity_2m`
- `hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m`
- `wind_speed_unit=ms`
- `past_hours=24&forecast_hours=3`

Suggested Open-Meteo forecast URL shape:

```text
https://api.open-meteo.com/v1/forecast
	?latitude={lat}&longitude={lon}
	&current=temperature_2m,relative_humidity_2m,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m
	&hourly=temperature_2m,relative_humidity_2m,cloud_cover,shortwave_radiation,wind_speed_10m,wind_direction_10m,wind_gusts_10m
	&wind_speed_unit=ms&past_hours=24&forecast_hours=3&timezone=UTC
```

For the U.S. venue, also query NOAA/NWS:

```text
GET https://api.weather.gov/points/{lat},{lon}
GET {forecastHourly from properties.forecastHourly}
GET https://api.weather.gov/alerts/active?point={lat},{lon}
```

Send a descriptive `User-Agent` header to weather.gov. Use NWS for official alerts and forecast language; use Open-Meteo for compact numeric wind inputs and a consistent cross-provider fallback. If the two providers disagree, display both provenance labels and let the deterministic simulator use the selected scenario weather rather than silently blending them.

For optional atmospheric context, use Open-Meteo Air Quality:

```text
https://air-quality-api.open-meteo.com/v1/air-quality
	?latitude={lat}&longitude={lon}
	&current=us_aqi,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,ozone
	&hourly=us_aqi,pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,ozone
	&forecast_hours=3&timezone=auto
```

Air-quality forecast data is regional background context, not a measurement of the simulated chemical plume. Keep it in a separate panel and never use it as the plume concentration value.

The simulator should convert meteorological `wind_direction_from_degrees` into a transport vector explicitly. Do not pass the compass direction directly into the renderer as if it were a vector.

The backend should normalize the result into a `WindHistory` object containing samples at their original timestamps, the selected incident-time sample, interpolation metadata, provider/model timestamps, and a confidence label. The scenario must store the selected weather snapshot and the full history used to generate the plume. This prevents a later refresh from silently changing a past incident's visualization.

Pasquill stability class is not directly supplied by the minimal weather request. For the demo, derive a labeled heuristic from cloud cover, wind, time of day, and solar radiation, or keep the class in the scenario fixture and show it as an assumption.

## Elevation, context, and routing plan

Use Mapterhorn raster DEM tiles for the visible 3D terrain and Open-Meteo Elevation for backend point/grid values used by the simulator. This separates the renderer's tile format from the simulation's simple numeric input.

## OpenStreetMap context plan

Use one small Overpass query around the incident point and cache the response. Query only the feature types needed for the demo, such as:

- drinking water and fire hydrants
- schools, hospitals, and emergency services
- roads and named buildings

Public Overpass instances are shared infrastructure. Add a descriptive User-Agent, avoid polling, use a timeout, and use the cached fixture after the first successful response. Treat HVAC intakes as unknown unless a source explicitly provides them; ordinary OSM data will not reliably contain them.

Use OSRM only for a small number of route requests, such as the incident point to one or two active units:

```text
https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}
	?overview=full&geometries=geojson&steps=true
```

Cache route results, identify the application in the backend request headers where supported, and retain the straight-line fallback. Public OSRM instances are shared services and should not be treated as guaranteed production dispatch routing.

## Environment variables to reserve

```text
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
GEMINI_PRIMARY_MODEL=gemini-3.8-flash
GEMINI_FAST_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-3.1-flash-lite
GEMINI_TRANSCRIBE_MODEL=gemini-3.5-transcribe
OVERPASS_ENDPOINT=https://overpass-api.de/api/interpreter
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
OPEN_METEO_HISTORICAL_BASE_URL=https://historical-forecast-api.open-meteo.com/v1
OPEN_METEO_AIR_QUALITY_URL=https://air-quality-api.open-meteo.com/v1/air-quality
NWS_BASE_URL=https://api.weather.gov
MAP_RENDERER=cesium
MAP_SCENE_MODE=EDITABLE_3D
CESIUM_ION_ACCESS_TOKEN=
MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
MAP_TERRAIN_TILE_URL=https://tiles.mapterhorn.com/{z}/{x}/{y}.webp
OSRM_BASE_URL=https://router.project-osrm.org
DEMO_LATITUDE=40.3487
DEMO_LONGITUDE=-74.6593
```

Do not commit actual values. The frontend should receive only backend URLs and public map configuration, never provider secrets.

## Reliability plan for the live demo

| Failure | Required behavior |
|---|---|
| Gemini quota or network error | Apply only explicit manual controls, show `AI OFFLINE`, and offer a canned demo response |
| ElevenLabs quota or network error | Play a cached clip, then show text without audio |
| Open-Meteo unavailable | Use cached weather and mark it `CACHED` |
| Historical wind unavailable | Use the nearest cached wind window, show `WIND HISTORY: CACHED`, and lower confidence; never silently substitute current wind without labeling it |
| NOAA/NWS unavailable | Use Open-Meteo forecast and cached alert state |
| Air-quality API unavailable | Hide the background AQ panel and keep plume simulation available |
| Overpass unavailable | Use cached venue context and mark it `CACHED` |
| OSRM unavailable | Draw a straight-line unit route and mark routing as approximate |
| Geolocation denied | Use the scenario's demo user position and show that GPS is unavailable |
| Terrain tiles unavailable | Use a local height grid and keep building extrusions/plume layers visible |
| Map tiles unavailable | Render the local GeoJSON venue layer over a simple coordinate grid |
