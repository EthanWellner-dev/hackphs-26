# Aero-Hazard / Plume — Gantt Chart

This is the **recovery schedule from Saturday 3:15 PM to the 8:00 AM judge-ready freeze**. The base product is already real: FastAPI contracts, deterministic dispatch, plume generation, context fallbacks, Cesium rendering, timeline controls, and tests exist. The remaining work is not “build the whole architecture”; it is to turn the existing system into one unforgettable, reliable vertical slice.

**Assumptions:** local time is EDT; Google Maps 3D access arrives at 10:00 PM; the open Cesium scene remains the guaranteed fallback. Do not make Google, Gemini, ElevenLabs, live weather, or Overpass required for the demo.

## Winning vertical slice

> **“Give us the incident. We will show you where the plume goes, what it threatens, and what the commander should do next.”**

The judge flow should prove five things in under three minutes:

1. A cinematic 3D venue scene with the release source and colored concentration field.
2. A plain-English command such as **“Chlorine leak at the main entrance; deploy Engine 4 south and increase the wind.”**
3. A visible state change: plume, incident status, unit/command log, and updated metrics.
4. A concise action plan with shelter direction, HVAC/isolation advice, PPE, assumptions, and data provenance.
5. Timeline scrubbing plus a Google Photorealistic 3D “wow” moment, with an immediate open-scene fallback if the provider fails.

## Schedule at a glance

**Judge-ready progress:** 70% — stateful interaction, live-wind bootstrap, real map fallback, guarded Google path, and request/cache reductions are implemented and validated.

| Workstream | Window | Status | Priority | Deliverable / exit gate |
|---|---:|---|---:|---|
| Scope lock and demo seed | 3:15–4:00 PM | **Complete** | P0 | One named venue incident, exact judge prompt, and no-new-features rule |
| Dashboard command-center polish | 4:00–6:00 PM | Next | P0 | Action plan and dispatch result are visible; command history/unit state is visible |
| Backend cache, physics, and map-cost gate | 6:00–7:00 PM | **Complete** | P0 | Provider freshness windows, persistent Google session quota guard, backend tests green, and no uncontrolled paid 3D requests |
| Frontend rebuild against verified contracts | 7:00–9:00 PM | **Complete** | P0 | Fast command-center dashboard with cached API reads, debounced timeline, capped local plume rendering, dispatch/action plan, and guarded renderer status |
| Explosion event visualization | 8:00–8:20 PM | Planned | P1 | Escalated incidents show a restrained source pulse/ring animation without affecting map performance |
| Judge interaction shortcuts | 6:00–7:30 PM | **Complete** | P0 | One-click seeded prompts, reset, active-unit state, command history, full action plan, and text dispatch |
| Reliability and offline hardening | 7:30–9:00 PM | **Complete** | P0 | Clean build, browser smoke test, no-key demo, focused frontend tests, provider failure recovery, and reduced request fan-out |
| Demo props and rehearsal v1 | 9:00–10:00 PM | Planned | P0 | 2.5-minute script, hot-file, alarm cue, and fallback narration |
| Google 3D integration | 10:00–11:30 PM | Blocked on key | P0 | Photorealistic scene loaded, attribution shown, open-scene fallback verified |
| Visual polish and rehearsal v2 | 11:30 PM–1:00 AM | Planned | P1 | Strong hierarchy, readable labels, stable camera, no debug clutter |
| Freeze candidate and backup | 1:00–2:00 AM | Planned | P0 | Tagged/copyable known-good build and startup/recovery checklist |
| Buffer / sleep / recovery | 2:00–5:30 AM | Reserved | P0 | Protect the morning reliability window; no feature work |
| Final smoke test | 5:30–6:30 AM | Planned | P0 | Three consecutive successful runs on presentation laptop |
| Final rehearsal and recording | 6:30–7:30 AM | Planned | P0 | Each teammate knows their cue, judge prompt, and recovery line |
| Submission freeze | 7:30–8:00 AM | Planned | P0 | Freeze files, verify links/assets, stop changing core behavior |
| Stretch suite | After freeze only | **Defer** | P2 | Mobile, collaboration, custom shader, and extra providers are out of scope |

## Detailed time-boxed Gantt

```text
Local time             15 16 17 18 19 20 21 22 23 00 01 02 03 04 05 06 07 08
                       |----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
Scope + demo seed      [██]
Dashboard polish          [████████]
Judge shortcuts                         [██████]
Reliability/API smoke                              [██████]
Props + rehearsal v1                                             [███]
Google 3D integration                                                  [██████]
Polish + rehearsal v2                                                         [██████]
Freeze + backup                                                                        [████]
Buffer / recovery                                                                            [██████████]
Final smoke                                                                                              [████]
Final rehearsal                                                                                                  [████]
Submission freeze                                                                                                     [██]
```

## Milestones and acceptance gates

| Milestone | Target | Acceptance gate | Status |
|---|---:|---|---|
| G1 — Scope lock | 4:00 PM | One seeded chlorine incident, one escalation command, one fallback story; all other ideas parked | **In progress** |
| G2 — Judge-visible command center | 6:00 PM | Dispatch response renders action plan, assumptions, provenance, and command/unit history in the UI | **In progress** |
| G3 — Interactive vertical slice | 7:30 PM | Judge can type or click a prompt and see a changed scenario, plume, metrics, and visible command result | Planned |
| G4 — Offline reliability | 9:00 PM | Frontend build and backend tests pass; demo works with Gemini/ElevenLabs/Google keys absent | Planned |
| G5 — Google wow pass | 11:30 PM | Google Photorealistic 3D loads with attribution; disabling it returns cleanly to Cesium open 3D | Blocked until 10 PM |
| G6 — Freeze candidate | 2:00 AM | Known-good build copied/tagged; no unresolved P0/P1 startup or interaction failures | Planned |
| G7 — Presentation-ready | 7:30 AM | Three consecutive 2.5-minute rehearsals, including the failure/recovery script | Planned |
| G8 — Submission freeze | 8:00 AM | No feature edits after this point; only presentation/submission checks | Planned |

## Workstream detail and remaining scope

### Foundation, backend, simulation, context — **mostly complete**

- `[x]` React/Vite frontend shell and FastAPI backend shell.
- `[x]` Validated scenario, weather, release, plume, dispatch, action-plan, and context contracts.
- `[x]` Deterministic no-key dispatch path with Gemini and ElevenLabs fallbacks.
- `[x]` Bounded plume generation with wind transport, stability, pressurization, explosion, density, precipitation, terrain/building attenuation, and surface-zone metadata.
- `[x]` Cached/live/DEMO context orchestration and provenance labels.
- `[x]` Provider freshness windows for weather, air quality, alerts, elevation, OSM, and routing to prevent repeated external requests.
- `[x]` Persistent Google Photorealistic session guard with monthly/daily/hourly limits and safe `OPEN_3D` fallback.
- `[x]` Reduced API usage with one cached/coalesced bootstrap, no duplicate map-session request, lazy MapLibre fallback, and backend live-context request coalescing.
- `[x]` Backend-first verification gate: focused physics, context, API, performance, and map-guard tests pass.
- `[x]` Frontend rebuilt against verified contracts with session cache, debounced timeline requests, capped local rendering, and guarded map-session display.
- `[~]` Local safe plume scene is complete; Cesium/Google 3D remains optional and is gated behind the stateful interaction slice and fixed-camera fallback test.
- `[ ]` Timeline, altitude slicing, FLIR, concentration footprints, dose estimate, and GeoJSON export are deferred until they can be added without exceeding the request/render budgets.
- `[x]` Documented judge-ready implementation sequence, performance budgets, request budgets, failure drills, and rehearsal runbook.
- `[x]` Finished the enforceable API call budget, cache-tier policy, Google cost stops, and 150-second judge rehearsal script.book.
### P0 — next implementation gate: fast judge-visible vertical slice

The execution plan and hard performance budgets are documented in [docs/JUDGE_READY_BUILD_PLAN.md](./docs/JUDGE_READY_BUILD_PLAN.md) and [docs/PERFORMANCE_RUNBOOK.md](./docs/PERFORMANCE_RUNBOOK.md). The order is intentional: preserve scenario state, add judge-visible state, test the safe path, then attempt optional Google 3D.

### P0 — judge-visible vertical slice before 10 PM

- `[ ]` Render the backend `actionPlan` in the dashboard instead of hard-coding generic actions.
- `[ ]` Fix timeline requests so a post-dispatch scenario is preserved instead of `/api/plume` silently rebuilding the default scenario.
- `[ ]` Add visible command history and deployed-unit state; every dispatch must leave evidence on screen.
- `[ ]` Add one-click demo prompts for the exact escalation flow while keeping free-text input.
- `[ ]` Add a visible simulation/provenance state and a concise approximation disclaimer.
- `[ ]` Add a manual reset to the seeded baseline incident.

### P0 — reliability from 7:30–9:00 PM

- `[ ]` Run backend tests and frontend production build; fix only regressions blocking the vertical slice.
- `[ ]` Verify no-key operation and independent Gemini, ElevenLabs, live-context, and Google failure paths.
- `[ ]` Verify text dispatch remains complete when audio is text-only.
- `[ ]` Verify Google failure returns to Cesium open 3D without a blank map or broken camera.
- `[ ]` Verify startup/recovery steps on the presentation laptop.

### P0 — Google 3D pass at 10 PM

- `[ ]` Set the Google key through local environment configuration only; never commit it.
- `[ ]` Load Photorealistic 3D Tiles, preserve attribution/credits, and capture one reliable venue camera.
- `[ ]` Keep the open Cesium scene as the guaranteed fallback; do not depend on arbitrary map exploration.

### P1 — polish and presentation after the vertical slice

- `[~]` Tighten visual hierarchy and readability around source, plume bands, wind, current time, satellite imagery, and the supplied tactical reference.
- `[~]` Make voice-first AI dispatch the primary interaction with a blue orb and live transcript; retain text via the bottom-right bubble affordance.
- `[~]` Constrain map height to the root viewport and add a green-to-red 2D building impact heatmap.
- `[ ]` Add a deterministic unit marker/route only if it does not destabilize the map.
- `[ ]` Prepare historical dossier, venue hot-file, alarm cue, and spoken walkthrough.
- `[ ]` Freeze a known-good build and perform three complete rehearsals.

### Explicitly deferred until after the 8:00 AM freeze

- `[ ]` Custom WebGL advection-diffusion shader, MapLibre second renderer, mobile/PWA, collaboration sync, and new provider integrations.

## Advanced extension backlog

The backlog is ordered by likely judge impact. These items should be scheduled after the core offline-safe demo gates, with Priority 1 work taking precedence over Priority 2 and below.

| Priority | Workstream | Planned order | Feature set | Acceptance gate |
|---|---|---:|---|---|
| 1 | EOC visual intelligence | Next | Altitude slicing, animated wind streamlines, AEGL iso-surfaces, cumulative dose, evacuation GeoJSON, FLIR view | A judge can inspect altitude, wind, thresholds, dose, and exportable boundaries in one seeded incident |
| 2 | Multimodal judge interaction | After P1 | Placard photo scanner, reviewed hazard auto-population, confidence/reasoning trace, drone recon analysis, responder QR/mobile field view | A judge can provide an image or scan a QR code and see validated, clearly approximate results |
| 3 | Immersive presentation polish | After P2 | EOC chimes, radio chatter/static, browser audio filtering, safe hardware dispatch switch, sensory radius, reaction indicators | Audio and hardware enhance the demo without becoming required for startup or recovery |
| 4 | Collaboration stretch | Last | Role-based field views and multi-user synchronization | Core demo remains offline-safe and single-user when collaboration services are unavailable |

### Advanced phase mapping

- **Phase 9:** AI vision and multimodal intake.
- **Phase 10:** Interactive EOC tools and graphics polish.
- **Phase 11:** Field collaboration, QR onboarding, and audio polish.

## Update log

| Date | Change | Overall progress |
|---|---|---:|
| 2026-10-10 | Added 24-hour cache reuse for Overpass building geometry, preserving LIVE/CACHED provenance and stale-cache fallback behavior. | 64% |
| 2026-10-10 | Added real/cached OSM building footprint contracts and queries, terrain-provider fallback, constrained 3D camera framing, circular voice orb refinement, and explosion source pulse groundwork; validation pending. | 62% |
| 2026-10-10 | Added voice-first dispatch UI, live browser transcript submission, satellite imagery default, viewport-constrained map sizing, and 2D green-to-red building impact overlays; frontend build passes. | 58% |
| 2026-10-10 | Added wind streamlines, AEGL-1/2/3 iso-surface boundaries, simulated cumulative dose metrics, and one-click evacuation GeoJSON export with deterministic tests. | 48% |
| 2026-10-10 | Fixed Vite development serving for Cesium image/texture assets, verified correct MIME types and clean live rendering, and switched development feedback to `npm run dev`. | 51% |
| 2026-10-10 | Added frontend API retry/cache behavior, extracted/tested building exposure calculations, and added Vitest coverage; frontend tests and production build pass. | 44% |
| 2026-10-10 | Added deterministic building exposure heatmap: venue fixtures are colored green through yellow to red from nearby plume severity; frontend production build passes. | 41% |
| 2026-10-10 | Added frontend API client, altitude slicing, FLIR tactical view, context provenance, cached audio playback, and resilient UI states; frontend production build passes. | 40% |
| 2026-10-10 | Added the prioritized advanced extension backlog, mapped to Phases 9–11 and gated behind the offline-safe core demo. | 37% |
| 2026-10-10 | Added fixture-first context normalization, provenance labels, straight-line routing fallback, cache helpers, and provider-failure tests. | 37% |
| 2026-10-10 | Added the backend hazard catalog, threshold validation, deployment command application, and command-path tests. | 34% |
| 2026-10-10 | Created schedule from the project outline; recorded completed backend/frontend foundation work and current blockers. | 31% |
