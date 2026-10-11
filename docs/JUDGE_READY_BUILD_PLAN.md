# Aero-Hazard / Plume — Judge-Ready Build Plan

**Updated:** 2026-10-10  
**Status:** Active implementation plan  
**Primary target:** Desktop Chrome at 1920×1080 and 1366×768, with a usable narrow layout fallback.

## 1. Product target

The supplied tactical reference image is the visual target: a dark command-center shell, a dominant spatial plume view, a left-side situation/action area, and compact right-side timeline, context, and system-status cards.

The product promise is deliberately narrow:

> Give us the incident; we will show where the plume goes, what it threatens, and what the commander should do next.

The judge must be able to understand the incident within five seconds, trigger a meaningful escalation within thirty seconds, and see a changed plume plus an action plan without waiting for a provider or model call.

This remains a **simulation and decision-support demo**, not an evacuation authority, certified atmospheric model, medical device, or emergency dispatch replacement. Every view must preserve the approximation disclaimer and data provenance.

## 2. Current baseline and known gaps

### Already verified

- FastAPI scenario, context, dispatch, plume, and action-plan contracts exist in `backend/app/main.py`.
- Gaussian plume approximation includes wind transport, Pasquill stability, source height, pressurization, explosion, dense/light gas adjustment, ground reflection, precipitation scavenging, and bounded terrain obstruction.
- Provider responses have disk caching and stale-cache fallback in `backend/app/services/context.py`.
- Provider freshness windows prevent repeated weather, air-quality, alert, elevation, OSM, and routing requests.
- Google Photorealistic mode has a persistent monthly/daily/hourly session guard in `backend/app/services/map_guard.py`.
- Backend suite passes with physics, API, provider, dispatch, voice, and performance coverage.
- The frontend has a lightweight local plume view, session-storage GET caching, debounced timeline updates, capped rendering, dispatch, provenance, and action-plan panels.

### Must be fixed or deliberately addressed next

1. Timeline requests after dispatch currently call `GET /api/plume`, which rebuilds the default scenario. Timeline updates must use the current scenario through `POST /api/plume` or a new versioned frame endpoint.
2. The frontend is a fast tactical shell, not yet a true map renderer. The local scene must be upgraded only after the interaction flow is stable.
3. The Google session response is requested safely, but Photorealistic rendering is not yet implemented. Do not add it until the open scene, fallback, attribution, and camera behavior are reliable.
4. The current frontend has no command history, unit state, seeded prompts, reset control, audio playback surface, or visible warning/action-plan detail equivalent to the reference image.
5. Frontend tests are absent. Add focused tests for request caching, timeline debouncing, primitive caps, dispatch state transitions, and renderer-guard behavior.

## 3. Architecture we will build

```text
React command center
  ├─ Incident header and metrics
  ├─ Spatial scene adapter
  │    ├─ Local safe scene (default; no paid request)
  │    └─ Optional Google Photorealistic adapter (guarded, fixed camera only)
  ├─ Timeline controller
  ├─ Dispatch console + optional voice/audio
  ├─ Action plan, context, provenance, and system log panels
  └─ Session cache / request scheduler
          |
          v
FastAPI API
  ├─ Bootstrap/scenario/context endpoints
  ├─ Versioned plume frame generation
  ├─ Deterministic dispatch + optional Gemini
  ├─ Cached external context providers
  ├─ Persistent Google map-session guard
  └─ Audio cache / text-only fallback
          |
          v
Local fixtures and bounded external providers
```

### State ownership

- **Backend owns truth:** scenario version, plume calculations, commands, action plan, provenance, and provider fallback decisions.
- **Frontend owns presentation:** selected timeline time, open panels, camera state, request cancellation, local cache, and render mode display.
- **Google owns only the streamed background mesh:** it must never become the source of plume physics, building impact, evacuation boundaries, or action-plan decisions.

### Renderer rule

The renderer starts in `OPEN_3D` or local vector safe mode. It may enter `PHOTOREALISTIC` only when all of these are true:

- `/api/map/session` returns `mode=PHOTOREALISTIC`.
- The response contains a non-null key and session ID.
- The app has not already initialized another Google root tileset in this session.
- The camera is inside the fixed demo venue bounds.
- Attribution is visible.

Timeline changes, plume updates, camera orbit, unit changes, and dispatch commands must update application overlays only. None may create a new Google root session.

## 4. Implementation sequence

### Phase A — Contract and request discipline

**Exit gate:** no stale scenario frames, no duplicate bootstrap calls, and every external request is observable.

- Add a compact `/api/bootstrap` response or equivalent frontend bootstrap coordinator returning scenario, initial frame, demo context, and guarded map config.
- Add `scenarioVersion` and `timeMinutes` to every frame cache key.
- Change timeline updates to send the current scenario to `POST /api/plume`.
- Add a small backend frame cache keyed by a canonical scenario hash and time, bounded by count and TTL.
- Add frontend request instrumentation: request name, cache hit/miss, duration, and failure/fallback status. Keep it in the developer panel, not the judge view.
- Add request coalescing so identical in-flight GETs share one promise.

### Phase B — Fast judge-visible command center

**Exit gate:** a judge can perform the complete seeded interaction with no network dependency after startup.

- Add a baseline reset button that restores the seeded scenario and clears only transient UI state.
- Add three seeded prompts: baseline status, deploy Engine 4, and explosion/wind escalation.
- Add command history with timestamp, command type, value, confidence, and provider.
- Add active-unit state and a simple route/marker overlay only when the backend supplies it.
- Render the full action plan: immediate actions, PPE, isolation radius, shelter guidance, decontamination guidance, assumptions, disclaimer, and provenance.
- Add a compact system log showing `LIVE`, `CACHED`, `DEMO`, provider fallback, and audio state.
- Add cached audio playback when available, with an always-visible text response fallback.

### Phase C — Tactical spatial scene

**Exit gate:** the scene communicates source, wind, plume direction, thresholds, time, and affected context at a glance while holding the frame budget.

- Keep the local safe scene as the default presentation path.
- Add a fixed venue camera and bounded world coordinates; no arbitrary globe exploration during the demo.
- Use one canvas/WebGL layer or a small SVG layer for plume overlays rather than one heavy DOM subtree per future particle.
- Show three threshold bands: TRACE, PEL, and IDLH. Use opacity and color, not dozens of labels.
- Add animated wind streamlines with a fixed pool of reusable instances.
- Add incident source pulse only on explosion state transitions, not every render.
- Add building/context impact coloring only for bounded nearby footprints returned by the backend.
- Display a visible legend and approximation/provenance badges.

### Phase D — Optional Google Photorealistic pass

**Exit gate:** one fixed venue camera loads once, shows attribution, and falls back cleanly without affecting the judge flow.

- Request the backend map session before importing or constructing the Google scene adapter.
- Load one root tileset for the fixed venue only.
- Reuse the returned session for its lifetime; never recreate it on React state updates.
- Set a conservative camera bounds box and disable exploratory movement outside it.
- Treat provider failure, unsupported coverage, quota exhaustion, or missing key as a normal fallback to the local/open scene.
- Run this as a presentation enhancement, never as a startup requirement.

### Phase E — Rehearsal and freeze

**Exit gate:** three consecutive rehearsals complete with the network disconnected, then three with the guarded Google path enabled if available.

- Record startup, reset, fallback, and recovery steps.
- Freeze a known-good build and cache contents.
- Stop feature work after the freeze; only fix P0 startup or interaction failures.

## 5. Performance plan

### Hard budgets

| Budget | Target | Enforcement |
|---|---:|---|
| Initial local first content | ≤ 1.0 s after Vite/static server response | Browser performance mark |
| Local interactive ready | ≤ 2.0 s | Bootstrap timing mark |
| Bootstrap requests | ≤ 4 requests, ideally 1 aggregate | Network instrumentation |
| Provider requests during normal demo | 0 after cached bootstrap | Backend cache tests and system log |
| Google root sessions | 1 per active app session; 0 in safe mode | `map_guard.py` counters |
| Plume frame generation | < 100 ms target, < 1 s hard limit | Backend performance test |
| Visible plume primitives | ≤ 24 particles + ≤ 16 volume cells | Backend and frontend caps |
| Local render frame time | ≥ 55 FPS target on presentation laptop | Browser performance overlay during rehearsal |
| Timeline request rate | ≤ 1 request per settled scrub position | Debounce/coalescing test |
| Main JS payload | Keep the safe path lightweight; do not ship a map SDK on the initial route | Build output review and lazy loading |
| DOM growth | Constant-size shell plus bounded overlays | Frontend test/inspection |

### How we stay fast

1. **Fast path first:** serve the cached fixture and local scene immediately; external data is enrichment, never a render prerequisite.
2. **One-time bootstrap:** load scenario, initial frame, context, and renderer guard once. Do not refetch all panels on every timeline change.
3. **Canonical cache keys:** cache by endpoint, normalized coordinates, scenario version, and time. Never cache a post-dispatch frame under the default scenario key.
4. **Debounce and cancel:** wait roughly 200–250 ms after timeline movement, cancel or ignore stale requests, and render the last valid frame while waiting.
5. **Bound geometry:** backend primitive counts are hard limits. Frontend never expands them into unbounded markers or labels.
6. **Lazy expensive code:** keep Google/Cesium/optional WebGL adapters out of the initial safe route; load only after the map guard authorizes the selected mode.
7. **No repeated 3D initialization:** keep one renderer instance in a ref and update data buffers/entities in place.
8. **No arbitrary map navigation:** fixed venue bounds prevent a judge from accidentally triggering a city-scale tile traversal such as a 3D New York request.
9. **Cache audio:** synthesize once per exact response text/voice pair; replay cached MP3 or show text-only output.
10. **Measure, then polish:** every optimization must have a timing or request-count measurement; do not trade reliability for visual effects.

## 6. Judge flow

### 0–20 seconds — establish stakes

Show the seeded chlorine incident, source marker, wind direction, current concentration, and the disclaimer. Avoid loading spinners or provider dashboards.

### 20–50 seconds — explain the system

Point out the source, plume bands, timeline, nearby context, and action-plan panel. Use the local/open scene first so the core story is clear.

### 50–80 seconds — judge triggers the incident

Use the seeded prompt or type: **“The leak just exploded; increase the wind and deploy Engine 4 south.”** The UI must show a new scenario version, command history entry, visible source pulse, changed plume, and updated action plan.

### 80–115 seconds — scrub the forecast

Move from T+0 to T+60 or T+120. The plume moves, but no provider or Google root request is created. The current scenario and command state remain intact.

### 115–145 seconds — show operational value

Open the action plan and show isolation radius, shelter guidance, PPE, nearby context, assumptions, and provenance. Play cached voice if available; keep the text response visible.

### 145–150 seconds — prove resilience

Toggle or simulate provider failure. The scene remains usable and visibly labels cached/demo data. If the Google path is enabled, show that the same view falls back to the safe scene.

## 7. Test and acceptance matrix

### Backend

- Physics direction, stability, source height, heavy-gas, precipitation, terrain obstruction, and explosion tests remain green.
- Frame cache returns identical canonical requests without recomputation.
- Post-dispatch `POST /api/plume` preserves scenario ID/version and command state.
- Context provider cache prevents calls inside freshness windows.
- Map guard allocates once, reuses active sessions, and falls back at each limit.
- No-key and provider-offline paths return complete contracts.

### Frontend

- Bootstrap renders with fixtures when the API is unavailable after a cached session.
- Timeline scrubbing is debounced and stale responses cannot overwrite newer state.
- Dispatch updates scenario, frame, command history, action plan, and timeline requests together.
- Reset returns to the exact seeded baseline.
- Primitive caps are enforced before render.
- Safe mode never imports or initializes the Google adapter.
- Authorized Google mode displays attribution and falls back on load failure.
- Keyboard and mouse interaction remain usable at 1366×768.

### Rehearsal

- Three offline runs: startup → prompt → escalation → timeline → reset.
- Three online runs: same flow with providers available.
- One forced Google quota/failure run.
- One forced audio failure run.
- One slow-network run with no blank scene.

## 8. Scope control

### Must ship

- Fast local safe scene.
- Correct versioned plume updates.
- Seeded judge interaction.
- Action plan, command history, context, provenance, and fallback state.
- Backend physics and cache tests.
- Optional guarded Google wow pass only if it does not threaten the offline flow.

### Explicitly defer

- City-scale arbitrary exploration.
- Full fluid-dynamics or a custom ray-marched atmospheric solver.
- Multi-user synchronization, authentication, mobile/PWA, and new providers.
- Per-building CFD or unbounded OSM geometry.
- Any feature that adds a network request inside the judge interaction loop.

## 9. Final API/request policy

The detailed request contract is in [API_CALL_BUDGET.md](./API_CALL_BUDGET.md). The implementation must use these rules, not merely document them:

- Prefer one aggregate bootstrap request; until it exists, use at most four parallel cached GETs.
- Never poll. Refresh providers only on explicit operator action or after their TTL expires.
- Treat timeline movement as a local UI event until the scrub settles; issue one request for the final time only.
- Send the active scenario with timeline frame requests. A frame cache key must include solver revision, canonical scenario, scenario version, and time.
- Keep the last valid frame visible while waiting. Never replace it with a blank loading state.
- Coalesce identical in-flight requests and do not automatically retry non-idempotent dispatch actions.
- Do not call Gemini or ElevenLabs for deterministic cached demo paths.
- Do not initialize Google, Cesium, or an unbounded map before the backend guard and fixed venue bounds authorize it.

## 10. Final presentation plan

The visual and spoken run is specified in [DEMO_REHEARSAL_SCRIPT.md](./DEMO_REHEARSAL_SCRIPT.md). The winning tradeoff is a fast, legible local scene with one optional photorealistic reveal—not a fragile city-scale map exploration.

## 11. Definition of done

The build is judge-ready when a clean machine can start the app with no provider keys, render the seeded incident, accept the escalation prompt, update the plume and action plan, scrub the timeline without losing scenario state, reset the demo, and explain every `LIVE`, `CACHED`, and `DEMO` result. Google Photorealistic mode is an optional one-session enhancement, not a dependency.
