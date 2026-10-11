# Aero-Hazard / Plume — Build Progress

This checklist is the project progress bar. It is derived from [`project_outline.md`](./project_outline.md) and should be updated whenever a feature, test, or demo deliverable changes status.

## Overall progress

**Progress: 68%** `██████████████░░░░░░`

- **Completed:** 53 checklist items
- **In progress:** 0 checklist items
- **Remaining:** 22 checklist items
- **Last updated:** 2026-10-10

> Status: `[x]` complete · `[~]` in progress · `[ ]` not started · `[!]` blocked or needs a decision

## 1. Foundation and project setup — Hours 00–03

- [x] Establish the React/Vite frontend shell.
- [x] Establish the FastAPI backend shell.
- [x] Define the validated scenario, release, weather, plume, and dispatch contracts.
- [x] Add a local runnable demo path without provider credentials.
- [x] Add checked-in venue scenario, weather, context, and terrain fixtures.
- [ ] Add a shared environment configuration example and startup documentation.

## 2. AI dispatcher and voice — Hours 03–07

- [x] Implement deterministic dispatch shortcuts for explosion, wind, deployment, and no-op input.
- [x] Add structured Gemini response validation with a deterministic fallback.
- [x] Add bounded caching for repeated dispatcher requests.
- [x] Add ElevenLabs audio caching and text-only fallback.
- [x] Test ElevenLabs SDK invocation, MP3 caching, empty audio, provider failure, and dispatch voice response behavior.
- [ ] Add explicit provider retry/backoff policy for transient failures.
- [x] Add dispatch command coverage for release updates, weather updates, events, and unit deployment.
- [x] Ask focused intake follow-ups and accept unknown/not-known answers without guessing.
- [x] Return a complete incident action plan with assumptions and provenance.
- [x] Add browser audio playback and cached-audio controls.

## 3. Plume simulation and hazard library — Hours 07–11

- [x] Implement bounded Gaussian plume approximation.
- [x] Convert wind source direction into transport direction.
- [x] Model stability class, source height, pressurization, explosion, heavy-gas adjustment, and ground reflection.
- [x] Generate particle and volume-cell frames for `T+0` through `T+120` minutes.
- [x] Add hazard profiles for chlorine, ammonia, methane, iodine-131, cesium-137, and biological aerosols.
- [ ] Add chemical fate metadata (volatility, deposition/adsorption, persistence, resuspension, and decay) and distinguish airborne concentration from surface loading.
- [ ] For hazards with surface deposition/adsorption, display simulated candidate sanitation/decontamination zones and affected surfaces; label them non-operational until confirmed by sampling and qualified guidance.
- [x] Add terrain/building obstruction masks to the solver.
- [x] Add explicit unknown/out-of-domain band handling.
- [x] Enforce a documented particle and volume primitive budget.

## 4. Context and external data services — Hours 11–15

- [x] Add cached Open-Meteo/NOAA weather normalization based on incident time.
- [x] Add cached NOAA alert normalization with a required User-Agent.
- [x] Add cached Open-Meteo air-quality and elevation services.
- [x] Add a backend live-context endpoint with provider-level LIVE/CACHED/DEMO provenance and safe fallback.
- [x] Integrate Overpass nearby features and optional OSRM routes into the live-context orchestration.
- [x] Include precipitation rate, probability, and type in weather contracts and apply bounded wet scavenging to concentration predictions.
- [x] Add cached Overpass context lookup for hydrants, fountains, schools, roads, and HVAC features.
- [x] Add cached OSRM routing with straight-line fallback.
- [ ] Add browser geolocation with explicit permission-denied and unavailable states.
- [ ] Add an explosion animation at the incident source whenever the scenario enters an exploded state.
- [x] Query individual nearby building footprints and property shapes for evacuation prioritization.
- [x] Cache Overpass building geometry for 24 hours and reuse it before making another provider request.
- [~] Make 3D mode show reliable terrain/topography instead of only changing zoom.
- [~] Make AI dispatch voice-first by default with live browser transcript streaming and a bottom-right text bubble fallback.
- [ ] Default the map to satellite imagery and tune the command-center overlay toward the supplied dark tactical reference.
- [ ] Keep the map within the root viewport height rather than allowing an oversized canvas.
- [ ] In 2D, color simulated houses/buildings from green to red by impact severity with a visible legend.
- [x] Label every external result as `LIVE`, `CACHED`, or `DEMO`.
- [x] Add retry, timeout, and stale-cache behavior for non-rate-limited APIs.
- [x] Apply freshness windows to all live-context providers so repeated requests reuse cached responses.
- [x] Add a persistent Google Photorealistic session/quota guard with an `OPEN_3D` fallback.

## 5. 3D map and rendering — parallel core work

- [~] Render the venue and plume in a Cesium-based 3D scene; the current rebuild uses a local safe scene first.
- [x] Render plume field and volume cells with restrained threshold colors; avoid particle-count UI in the judge view.
- [ ] Support map rotation/zoom controls and a 2D/3D toggle with 2D as the default.
- [ ] Add editable incident source, unit markers, isolation rings, and route lines.
- [ ] Add local/open terrain and building fixtures as the no-key renderer path.
- [ ] Add MapLibre fallback mode with terrain and a custom 3D plume layer.
- [x] Add optional photorealistic tiles behind an application quota/session guard.
- [ ] Preserve visible attribution for every selected map, terrain, and imagery source.
- [ ] Handle map/provider failure by switching to the local open scene before making paid requests.

## 6. Command-center dashboard — Hours 15–18

- [x] Display incident hazard, concentration, wind, and release metrics.
- [x] Add the `T+0` to `T+120` timeline scrubber.
- [x] Add text dispatch input and scenario/frame updates.
- [ ] Add manual hazard, release, weather, and source-location controls.
- [ ] Add unit roster, active commands, and command history.
- [ ] Add action-plan, model-assumptions, provenance, and fallback-state panels.
- [x] Add loading, provider-error, stale-cache, and backend-offline UI states.
- [ ] Add responsive layout for field updates while preserving the 1080p command-center view.

## Backend-first delivery gate

- [x] Complete backend cache, map-guard, physics, and API validation before rebuilding the frontend.
- [x] Rebuild the frontend only against verified backend contracts; no renderer may issue uncontrolled 3D requests.
- [x] Write the judge-ready implementation plan, performance budgets, request budget, failure drills, and rehearsal runbook.
- [x] Finish the API call budget, cache-tier policy, cost stops, and 150-second judge rehearsal script.
- [x] Close the next P0 gaps: preserve post-dispatch scenario during timeline scrubbing, add seeded prompts/reset/history, and render the complete action plan.
- [x] Add focused frontend tests and complete offline/provider-failure rehearsal.
- [x] Reduce duplicate bootstrap/map requests and expand browser/backend cache reuse.

## 7. Tests, hardening, and demo reliability — Hours 18–21

- [x] Test plume direction and stability behavior.
- [x] Test deterministic agent fallback and cache behavior without Gemini calls.
- [x] Test voice fallback without ElevenLabs calls.
- [x] Test health, scenario, plume, validation, and manual-update endpoints.
- [x] Add unit tests for every hazard profile and command application path.
- [x] Add API contract tests for every documented endpoint and failure response.
- [x] Add external-service tests using mocks, fixtures, expected results, and cache hits only.
- [x] Add plume performance and primitive-budget tests.
- [x] Add frontend build/type-check validation and smoke-test the demo flow.
- [ ] Add performance checks for frame generation and render primitive limits.
- [ ] Verify the app runs with no API keys and with each provider independently unavailable.

## 8. Demo preparation and rehearsal — Hours 21–24

- [ ] Prepare historical disaster dossier cards.
- [ ] Prepare the venue incident hot-file and alarm ambush media.
- [ ] Seed a deterministic baseline incident for the 2.5-minute judge flow.
- [ ] Write the spoken walkthrough, interactive judge prompts, and fallback script.
- [ ] Rehearse the complete flow: hook, walkthrough, ambush, dispatch, plume, and action plan.
- [ ] Verify cached audio and local map assets on the presentation laptop.
- [ ] Freeze a known-good demo build and record startup/recovery steps.

## Stretch goals (only after the core demo is reliable)

- [ ] Add mobile field view/PWA layout.
- [ ] Add role-based live synchronization for commander, AI agent, field units, and evacuation lead.
- [ ] Add multi-user incident sessions.
- [ ] Add richer unit routing and localized responder advice.

## Advanced extensions — prioritized by judge impact

These are intentionally ordered by the strongest combination of visible demo impact, technical depth, and implementation value. Complete the highest priority tier before starting lower tiers.

### Priority 1 — visible command-center differentiators

- [x] **Implement volumetric altitude slicing.** Add a `Z`-axis control with ground-level (`z=2m`), roof-height (`z=25m`), and high-atmosphere views so judges can inspect concentration by altitude.
- [x] **Add animated 3D wind streamlines.** Render bounded vector flowlines that show wind transport and building/terrain deflection around the plume.
- [x] **Highlight affected buildings by severity.** Render deterministic venue building fixtures from green through yellow to red based on nearby plume concentration.
- [x] **Add dynamic plume iso-surface boundaries.** Render concentration shells for AEGL-1, AEGL-2, and AEGL-3 with clear threshold labels and simulation disclaimers.
- [x] **Add cumulative toxic-dose metrics.** Calculate `Dose = integral(C(t)^n dt)` for active units and expose the result in the unit/action-plan view.
- [x] **Add evacuation-boundary GeoJSON export.** Provide a one-click export of the current simulated hazard perimeter for EOC/GIS workflows.
- [x] **Add a FLIR/thermal tactical view.** Provide a one-click LUT toggle for Cesium/MapLibre plume visualization.

### Priority 2 — high-impact interactive judge features

- [ ] **Add a HAZMAT placard photo scanner.** Accept a drag-and-drop or camera image and use Gemini Vision to identify a UN placard such as `UN 1017`.
- [ ] **Auto-populate identified hazard properties.** Fill chemical identity, density, toxicity thresholds, reactivity, and a conservative default leak rate from a reviewed local library; never treat model output as the source of truth.
- [ ] **Display vision confidence and reasoning trace.** Show provider, confidence, extracted placard fields, and validation warnings before applying a hazard change.
- [ ] **Add drone recon smoke analysis.** Accept an overhead image and return an explicitly approximate plume vector and buoyancy classification with a deterministic fallback.
- [ ] **Generate a dynamic responder QR code.** Open a no-registration mobile field view with the simulated location and indoor/outdoor safety guidance.
- [ ] **Add a compact field responder view.** Show local plume band, nearest context features, unit advice, and stale/demo provenance on a phone-sized layout.

### Priority 3 — immersion and presentation polish

- [ ] **Add EOC audio effects.** Mix dispatcher chimes, radio chatter, and tactical static around cached ElevenLabs output without making audio generation required.
- [ ] **Add radio playback filtering.** Apply optional band-pass/static effects in the browser and preserve a clean text-only fallback.
- [ ] **Add a physical Execute Dispatch switch.** Map a safe keyboard shortcut or optional macro-pad/arcade button to trigger the seeded emergency scenario.
- [ ] **Add secondary chemical reaction indicators.** Model clearly labeled illustrative effects such as chlorine humidity mist or secondary-fire updrafts.
- [ ] **Research and model chemical surface persistence.** Track candidate contaminated surfaces separately from airborne plume concentration and show sanitation/decontamination areas for hazards with deposition or adsorption traits.
- [ ] **Add a sensory-impact radius.** Display conservative eye/respiratory irritation perimeter warnings separately from regulatory plume bands.

### Priority 4 — collaboration stretch features

- [ ] **Add role-based field collaboration.** Support commander, AI operations agent, field unit, and evacuation lead views.
- [ ] **Add multi-user incident synchronization.** Add real-time shared state only after the offline single-user demo is reliable.

### Advanced phase mapping

- **Phase 9 — AI vision and multimodal intake:** placard upload, reviewed hazard auto-population, confidence/reasoning display, and drone recon analysis.
- **Phase 10 — Interactive EOC tools and graphics:** altitude slice, FLIR mode, wind flowlines, iso-surfaces, cumulative dose, sensory radius, and GeoJSON export.
- **Phase 11 — Field collaboration and QR onboarding:** responder QR code, mobile field view, audio effects/filtering, and optional multi-user collaboration.

## Update protocol

1. Check an item only after its implementation and focused validation are complete.
2. Mark an item `[~]` while it is actively being built; include the blocking detail below if needed.
3. Update the percentage and counts at the top after changing statuses.
4. Update [`gantt.md`](./gantt.md) in the same change so the checklist and schedule stay aligned.
5. Keep provider calls out of tests; use mocks, fixtures, expected results, or cache files for Gemini and ElevenLabs.

### Current blockers and decisions

- The outline names Mapbox in the original architecture, while the current implementation uses Cesium with an open-scene fallback. Keep the renderer provider-neutral before adding another renderer.
- External weather, context, routing, and elevation services are not implemented yet; local fixtures should land before live integrations.
