# Aero-Hazard / Plume — Build Progress

This checklist audits the goals in [project_outline.md](./project_outline.md) against the current implementation. **Audit date: 2026-10-11. No completion percentage is reported:** the previous 84% and item totals mixed obsolete implementations, partial features and unverified rehearsals.

Status: `[x]` implemented with focused evidence **at the stated scope** · `[~]` partial / integration or validation pending · `[ ]` not completed · `[!]` externally blocked. A backend API or helper test does not establish a working browser feature. Checked prototype behavior is not scientific or operational validation.

## Evidence and current architecture

- **Backend:** [API and model implementation](./backend/app/main.py), [API contracts](./backend/tests/test_api_contracts.py), [model/dispatch tests](./backend/tests/test_backend_slice.py), [transport tests](./backend/tests/test_live_transport.py), [weather orchestration](./backend/tests/test_weather_orchestration.py).
- **Providers:** [context implementation](./backend/app/services/context.py), [context tests](./backend/tests/test_context.py), [Gemini tests](./backend/tests/test_agent_provider.py), [voice tests](./backend/tests/test_voice_provider.py), [map guard tests](./backend/tests/test_map_guard.py).
- **Browser:** [active MapLibre entrypoint](./frontend/src/main.js), [HTML dashboard](./frontend/index.html), [plume layer](./frontend/src/plumeLayer.js), [timeline tests](./frontend/src/timeline.test.ts), [dispatch helper tests](./frontend/src/aiDispatch.test.ts), [playback tests](./frontend/src/playback.test.ts), [geometry tests](./frontend/src/plumeLayer.test.js). The current app is Vite plus JavaScript/TypeScript and MapLibre/Three.js, **not a mounted React/Cesium application**. Installed dependencies are not implemented features.
- **Recorded evidence, not final integration sign-off:** the coordinator reports a historical 85-backend/15-frontend baseline, then **15 mesh tests and 11 playback/cache/dispatch tests passing** during the current work. These are scoped run results, not a cumulative count or browser acceptance. Backend contract integration is still pending. The [runbook](./docs/PERFORMANCE_RUNBOOK.md#readiness-and-weather-evidence) records backend health/live-weather/mass-scaling smoke evidence. This audit inspected source/tests without rerunning the full suites while implementation agents were active.
- **Latest checkpoint:** the coordinator reports a production build and **28 frontend tests passing before the new WebM recording and chat/voice responder additions**. Those additions and backend responder parsing are still pending integration; the checkpoint does not establish their end-to-end behavior.
- **Research boundary:** [dilution and exposure research](./docs/PLUME_DILUTION_AND_EXPOSURE_RESEARCH.md) documents a provisional renderer-only floor at 1% of configured trace concentration. This is neither a health threshold nor physical mass removal; transport, overlap sums, exposure and mass accounting must retain hidden contributions. Summed-field and lower-floor comparisons remain validation requirements.
- **Planning only:** [build plan](./docs/JUDGE_READY_BUILD_PLAN.md), [request budget](./docs/API_CALL_BUDGET.md), [runbook](./docs/PERFORMANCE_RUNBOOK.md), [rehearsal script](./docs/DEMO_REHEARSAL_SCRIPT.md). Their proposed Cesium/local-safe paths and failure-drill instructions are not evidence that the active browser implements or has passed them.

## Urgent corrections and current integration gate

- [~] Fetch weather at startup and refresh every five minutes with source, age and failure labels. Backend NOAA fallback and preservation of non-weather context are tested; final browser refresh/failure evidence remains pending.
- [x] Preserve incident epoch through API serialization and integrate changing wind history in five-minute transport steps. Evidence: transport, hazard-rendering and weather-orchestration tests.
- [x] Record the prior backend health, live-bootstrap and release-mass scaling smoke check; 85-test baseline is historical evidence, not sign-off on subsequent changes.
- [~] Replace screen-space/additive particles with depth-tested map-space geometry; renderer agent owns final cloud/decluttering changes and validation.
- [~] Render map-anchored approximate terrain/building-aware wind paths and camera-relative wind badge; helper coverage exists, final browser acceptance pending.
- [~] Derive metrics/legends from the active frame and hazard; remove invented population/property numbers; verify current integration and release-mass edits.
- [~] Make timeline scrubbing revision-safe, bounded and cached; helper coverage exists, current dispatch/weather integration still requires browser verification.
- [~] Merge dense overlapping plume parcels into bounded smooth geometry while preserving sparse parcels; do not describe visual shells as scientifically derived exposure thresholds.
- [~] Play/pause/restart the five-minute forecast through T+120; cancellation/cache helper tests exist, browser acceptance pending.
- [~] Add two-hour outdoor exposure API and building/area overlays with peak, mean and concentration-time integral click details. Backend and UI work are active; this is **not personal absorbed dose**.
- [~] Validate geometry budgets, playback cancellation, mass/exposure scaling, API performance and final browser integration before promoting these features.

## 1. Foundation and project setup

- [x] Establish the Vite frontend project and build/test scripts. Evidence: [package.json](./frontend/package.json).
- [ ] Restore or implement a React component application if retaining that original architecture requirement; React dependencies alone do not meet it.
- [x] Establish the FastAPI backend and validated baseline scenario, release, weather, plume and dispatch contracts. Evidence: API implementation and contract tests.
- [x] Provide deterministic backend scenario/context defaults without Gemini, ElevenLabs or Google credentials. This does not promise an offline browser map.
- [~] Provide a complete no-key local browser demo; MapLibre style/tiles/DEM currently require network access and no full offline scene is verified.
- [~] Add checked-in venue/weather/context/terrain fixtures. Programmatic scenario/context defaults exist; a packaged offline terrain/building asset path is not established.
- [~] Add a shared environment example and verified startup documentation. A runbook/tasks exist; environment-example and current-architecture recovery verification remain outstanding.

## 2. AI dispatcher and voice

- [x] Implement deterministic single-command shortcuts for explosion, wind, release mass, deployment acknowledgement and no-op input. Evidence: agent, transport and backend-slice tests. This is not arbitrary multi-command planning or real unit deployment.
- [x] Validate structured Gemini responses and fall back on malformed responses/provider exceptions. Evidence: mocked Gemini tests; live Gemini success is not established by mocks.
- [x] Bound repeated dispatcher decisions in a 128-entry cache. Evidence: agent implementation and cache tests.
- [x] Cache ElevenLabs MP3 output and return text-only on missing configuration, empty audio or provider failure. Evidence: mocked voice tests, including SDK invocation and cache behavior.
- [ ] Add an explicit provider retry/backoff policy for transient AI/audio failures.
- [~] Cover every release/weather/event/deployment command path; representative commands are tested, not all combinations or free-form commands.
- [x] Ask deterministic focused follow-ups and accept unknown answers without inventing missing values. Evidence: backend-slice unknown-answer tests; full conversational intake state is not claimed.
- [x] Return a simulated action-plan object with assumptions, provenance and a simulation disclaimer. Evidence: backend/API plan tests. This does not certify its advice.
- [~] Render the full action plan, command history and unit acknowledgements in the active UI; coordinator owns current implementation/validation.
- [ ] Add/verify browser audio playback and cached-audio controls. Backend audio generation alone does not meet this gate.
- [~] Add browser SpeechRecognition for chat/voice responder commands; the coordinator is implementing transcript review followed by explicit Enter submission, not automatic dispatch. Verify microphone permissions, unsupported-browser/error states and text fallback before completion.
- [~] Integrate backend responder-command parsing helpers with chat/voice input and actual returned responder state. Backend agent work is active; parser tests alone will not establish browser integration or operational resource tracking.
- [ ] Validate chat/voice responder commands end to end, including reviewed transcripts, explicit submission, state updates and failure recovery. Speech recognition is distinct from ElevenLabs response playback.

## 3. Plume simulation and hazard library

- [x] Implement a bounded Gaussian approximation and meteorological FROM-to-transport conversion. Evidence: backend-slice and live-transport tests; not a validated CFD solver.
- [x] Include heuristic stability, source-height, pressurization, density, ground reflection, decay/settling and precipitation effects. Evidence: model implementation and focused behavior tests; parameters are not calibrated.
- [~] Verify explosion/release behavior and mass conservation after current backend corrections; do not promise invented extra mass or a fixed 1,000-particle explosion.
- [x] Generate bounded particle/volume-cell API frames for T+0–120. Evidence: API, hazard-rendering and [performance tests](./backend/tests/test_performance.py). Particle counts vary with transport/fission; old 500/1,000 claims are obsolete.
- [x] Provide library entries for chlorine, ammonia, methane, iodine-131, cesium-137 and biological aerosol. Evidence: library/threshold tests; radiological/biological mass concentration is not radiation dose or infection risk.
- [~] Complete chemical-fate metadata and distinguish airborne concentration from surface loading. Prototype retention/persistence/decay fields and candidate surface zones exist; adsorption, volatility, resuspension and physically validated loading do not.
- [~] Display simulated candidate contaminated surfaces/decontamination zones. Backend `surfaceZones` and candidate-review tests exist; active-map display and reviewed guidance are not complete.
- [x] Apply bounded supplied terrain/building obstruction heuristics. Evidence: obstruction and spatial-flow tests; this is not terrain-resolved CFD or proof of complete live DEM assimilation.
- [~] Handle unknown/out-of-domain conditions explicitly. `UNKNOWN` bands exist; do not equate unmodeled or below-reference areas with verified safety.
- [~] Enforce documented solver and renderer budgets. Existing solver performance tests cover the prior baseline; new cloud/exposure work and browser FPS require remeasurement.

## 4. Context and external data services

- [x] Normalize/cache Open-Meteo weather and NOAA fallback forecasts with timestamps and five-minute interpolation. Evidence: context, live-transport and weather-orchestration tests; interpolation is not five-minute observed wind.
- [x] Normalize NOAA alerts with User-Agent, Open-Meteo air quality and elevation. Evidence: context service/mocked tests.
- [x] Orchestrate live/cached/DEMO provider context with safe fallback and provenance fields. Evidence: context/API tests.
- [x] Query/normalize Overpass micro-features and building footprints; integrate optional OSRM routes with straight-line fallback. Evidence: context service/tests; no guaranteed building/HVAC coverage or safe route claim.
- [x] Apply precipitation contracts and bounded wet-scavenging heuristics. Evidence: rain/snow and contract tests.
- [x] Reuse provider freshness windows, including the 24-hour Overpass building cache, before requesting again. Evidence: cache service and mocked fresh/stale-cache tests.
- [~] Add browser retry/timeout/stale-cache behavior for all relevant services. Backend timeout/cache fallback exists; uniform frontend retry/backoff is not implemented.
- [~] Display provenance/age consistently for every external result; backend fields exist, complete UI coverage needs verification.
- [ ] Add browser geolocation with permission-denied/unavailable states and reviewed indoor/outdoor context; do not claim automatic indoor detection.
- [ ] Add a verified source explosion animation; changed release state or geometry is not itself an animation.
- [~] Show reliable terrain with useful zoom gating; online DEM configuration exists, disable/re-enable/failure behavior still needs verification.
- [!] Provide satellite imagery through a configured, attributed provider. Current no-key UI reports `SAT N/A`; street tiles are not satellite imagery.
- [~] Preserve viewport layout and responsive tactical overlays under actual browser resizing.
- [~] Color actual returned building footprints by modeled concentration; implementation exists, current geometry/exposure integration requires browser acceptance.
- [~] Show the seeded Princeton Middle School source pin and clear-snap interaction; code exists, verify against source edits/reset.
- [x] Extract active frontend application JavaScript into [main.js](./frontend/src/main.js).
- [x] Implement persistent Google session admission/quota guard with `OPEN_3D` response fallback. Evidence: map-guard tests. This is not proof of a browser renderer switch or a hard provider billing cap.

## 5. Map and rendering

- [~] Render the venue/plume using the active MapLibre/Three.js scene. Current cloud renderer is under revision and needs final visual validation.
- [ ] Integrate a working optional Cesium scene if still desired; installed Cesium assets are not an active renderer.
- [~] Render threshold-colored plume geometry without particle-count judge UI. Do not claim volume-cell rendering or AEGL shells from API payloads alone.
- [~] Verify map rotation/zoom and 2D/3D toggle; the inspected default is pitched 3D, not the outline's requested default 2D.
- [~] Implement editable incident source/manual scenario controls; coordinator is working on UI/API coupling. A generic map marker alone is not a source edit.
- [ ] Add real unit markers, isolation rings and route overlays backed by scenario state.
- [ ] Package local terrain/building assets and implement a tested map-provider failure fallback. A caught style-fetch error/toast is not an offline renderer.
- [ ] Integrate optional Google Photorealistic tiles through the session guard and verify credits and denied-session fallback. Backend guard alone is incomplete.
- [~] Verify attribution for every map, DEM and imagery provider. MapLibre attribution control exists; complete source-credit coverage is not established.

## 6. Command-center dashboard and exports

- [~] Display incident/hazard/release/weather metrics, provider errors and honest unavailable-data states in the active dashboard; final browser checks pending.
- [~] Verify text dispatch updates scenario/frame while preserving the scenario during scrubbing, weather refresh and playback.
- [~] Complete manual hazard/release/weather/location controls, including leak, burst and combined modes with rate, duration, burst mass and burst time. Coordinator implementation is active; backend contract integration and browser validation remain pending.
- [~] Complete seeded prompts, baseline reset, command history and action-plan/assumption/provenance panels; coordinator owns current work.
- [ ] Implement a real active-unit roster/resource model; a deployment acknowledgement or incident-label change is not unit tracking.
- [~] Export all returned modeled building records as escaped CSV; coordinator implementation is active. Verify complete row coverage, quoting/escaping, units/provenance and browser download after backend contract integration. Returned records are not a complete building inventory.
- [~] Export PNG/JPG map captures retaining attribution and a simulation disclaimer; coordinator implementation is active. Verify actual downloads, rendered content and credits/disclaimer in both formats before completion.
- [~] Add WebM video capture of the simulation; coordinator frontend implementation is active. Browser recording, stop/download behavior, attribution/disclaimer retention and unsupported-capture handling remain unverified.
- [ ] Verify WebM recordings contain the intended rendered frames, open successfully after download and release recording resources when stopped; no end-to-end recording claim yet.
- [ ] Add/verify a simulated hazard-perimeter GeoJSON export through the active UI; CSV/image/video exports do not satisfy this separate requirement. It must not be labeled an approved evacuation boundary.
- [ ] Validate phone-sized field layouts while preserving the 1080p dashboard.

## 7. Tests, hardening and delivery gates

- [x] Maintain focused backend tests for direction/stability, fallback/cache, voice failures, core API/manual updates, provider normalization and baseline performance. See evidence links above.
- [~] Cover every hazard/command path and every documented endpoint/failure response. Existing tests are representative; exhaustive coverage and new exposure endpoints need final evidence.
- [x] Keep Gemini/ElevenLabs provider tests mocked and verify cache/fallback behavior without paid calls.
- [x] Maintain dispatch/timeline/formatting helper tests; prior 15-test frontend baseline is recorded, not full browser coverage.
- [~] Rerun backend/frontend suites and production build/type-check after all active changes; validate the actual shipped JavaScript, not only typed helper modules.
- [~] Measure current frame/exposure generation, geometry caps, response size, browser FPS and request fan-out.
- [ ] Verify the complete browser flow without API keys and with each provider independently unavailable, including map style/tiles/DEM and audio.
- [ ] Verify no stale playback/dispatch/weather result overwrites a newer manual edit/reset.
- [x] Write implementation-plan, request-budget, failure-drill and rehearsal documents. These documents exist; their prescribed gates are not marked executed.
- [ ] Verify startup/recovery on the presentation laptop and capture reproducible smoke/rehearsal evidence.

## 8. Demo preparation and freeze

- [ ] Prepare historical disaster dossier cards, venue hot-file and alarm media.
- [~] Seed a deterministic incident for the judge flow: backend defaults exist; end-to-end reset/seed controls are being integrated.
- [x] Write a proposed 150-second walkthrough, prompts and fallback script: [rehearsal script](./docs/DEMO_REHEARSAL_SCRIPT.md). Verify prompts against current single-command behavior before use.
- [ ] Rehearse hook, walkthrough, ambush, dispatch, plume and action plan three times, including failure/recovery.
- [ ] Verify cached audio/local map assets on the presentation laptop; do not assume either exists from earlier status entries.
- [ ] Freeze/copy/tag a known-good build and record the startup/recovery steps actually exercised.

## Advanced extension backlog

### Priority 1 — visualization and exposure

- [ ] Add a working altitude-slice control for ground/roof/high views. No active altitude UI is evidenced.
- [~] Add map-space animated wind streamlines and building severity overlays; current rendering/browser verification pending.
- [ ] Add scientifically appropriate, labeled concentration iso-surfaces. Existing TRACE/PEL/IDLH bands and visual cloud shells are not AEGL-1/2/3 contours.
- [~] Add bounded two-hour **outdoor concentration-time exposure**, not cumulative personal toxic dose. Unit occupancy/PPE/breathing and hazard-specific toxicology are not modeled.
- [ ] Add/verify simulated perimeter GeoJSON export with honest metadata and a browser download check; current CSV/image work is separate.
- [ ] Add a working FLIR/thermal display toggle. No active toggle is evidenced; visual coloring is not a thermal measurement.

### Priority 2 — multimodal and field view

- [ ] Add a placard image scanner, reviewed hazard auto-population and explicit provider/confidence/validation display.
- [ ] Add approximate drone-image smoke analysis with a deterministic fallback.
- [ ] Add responder QR onboarding and a phone-sized field view with explicit location/provenance limitations.

### Priority 3 — presentation and chemical fate

- [ ] Add optional EOC audio effects/radio filtering with a complete silent fallback.
- [ ] Add a safe physical dispatch shortcut and verify it with actual hardware.
- [ ] Add illustrative secondary reaction/sensory-radius indicators without invented safety limits.
- [~] Research surface persistence beyond existing prototype retention fields; validated surface loading, resuspension and decontamination mapping remain incomplete.

### Priority 4 — collaboration/stretch

- [ ] Add mobile/PWA support, role-specific views, multi-user incident synchronization and richer responder routing only after the single-user core is reliable.
- [ ] Implement a custom advection-diffusion physics shader only if scientifically justified; current Three.js visualization is not that solver.

## Real-world validation blockers — prototype only

- [ ] Benchmark dispersion and uncertainty against reference datasets and field observations; calibrate source terms, meteorology, terrain/building interactions and deposition.
- [ ] Validate hazard-specific units, thresholds, mixtures, toxicology, radiation/infection models and exposure interpretation with qualified specialists.
- [ ] Integrate actual population/occupancy and field measurements; absence of a returned building or concentration is not evidence of safety.
- [ ] Validate indoor infiltration, personal dose/PPE, resource state and safe routes before making corresponding operational claims.
- [ ] Obtain qualified emergency-response review before independent evacuation, PPE, shelter or decontamination use. Current action plans and boundaries are simulation outputs, not authority.

## Update protocol and audit log

1. Promote an item only after implementation and focused validation at its stated scope; record a test/run/browser result, not just code existence.
2. Keep active cloud, exposure and coordinator UI/export work partial until final integration results arrive.
3. Keep [gantt.md](./gantt.md) synchronized. Do not reintroduce percentages without a defined denominator and evidence for every counted completion.
4. Keep paid-provider tests mocked; distinguish historical tests, new tests and live smoke evidence.

**2026-10-11 audit:** removed unsupported 84%/67-item totals and obsolete completion history; corrected active renderer/framework; downgraded offline reliability, React/Cesium/Google rendering, voice/audio, altitude/FLIR/AEGL/dose/export and broad validation claims. External services are implemented at backend scope; the old statement that they did not exist was also removed. Current implementation work remains pending rather than being credited prospectively.
