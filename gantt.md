# Aero-Hazard / Plume — Gantt and Acceptance Gates

**Audited 2026-10-11.** This is a recovery plan, not evidence that scheduled work finished. The previous **84% judge-ready** claim and completion counts were unsupported and have been removed. [todo.md](./todo.md) is the evidence-scoped checklist; [project_outline.md](./project_outline.md) is the original target, not the implemented architecture.

The current application uses **Vite JavaScript/TypeScript, MapLibre and Three.js**, with a FastAPI simulation/API backend. It does not currently establish a mounted React/Cesium application, a Google Photorealistic scene or a guaranteed offline map. No API keys is not the same as no network: the active map loads an external style, tiles and DEM.

**Safety boundary:** this is an uncalibrated simulation prototype, not an emergency-response authority. Real-world dispersion/toxicology validation, field/population observations, indoor/personal-dose modeling and qualified emergency-response review remain mandatory blockers.

## Status and evidence rules

- **Implemented (scoped):** source plus focused evidence support the stated backend/helper/document behavior.
- **Partial / in progress:** code exists or work is active, but the whole feature or final integration validation is incomplete.
- **Planned / blocked:** acceptance has not been established; a planned time or test file alone is not proof.
- Evidence supplied by the coordinator: historical **85-backend/15-frontend baseline**, followed by **15 mesh tests and 11 playback/cache/dispatch tests passing** during current work. These are separate scoped run results, not a cumulative total or browser acceptance. Backend contract integration remains pending. [Recorded backend smoke evidence](./docs/PERFORMANCE_RUNBOOK.md#readiness-and-weather-evidence) covers health, live bootstrap and mass scaling. This audit did not rerun full suites while implementation agents were active.

**Latest checkpoint:** the coordinator reports a production build and **28 frontend tests passing before the new WebM capture and chat/voice responder additions**. Those additions, SpeechRecognition transcript review/Enter submission and backend responder parsing remain pending integration and browser validation. This checkpoint does not certify them.

## Judge flow to validate

1. Load the Princeton Middle School simulation with a visible source, correctly labeled wind/provenance and no invented population estimates.
2. Submit a supported plain-text incident update; show changed scenario/frame and an honest acknowledgement. Do not promise an arbitrary compound command or real deployed units from a single-command fallback.
3. Inspect the current simulated plan, assumptions and disclaimer; manual edits/reset/history must visibly preserve correct scenario state.
4. Scrub or play five-minute frames through T+120 and inspect modeled outdoor two-hour exposure. Exposure is concentration-time integral, **not personal absorbed dose**.
5. Download escaped CSV for all returned modeled buildings and PNG/JPG map captures with attribution and a simulation disclaimer only after browser verification. A perimeter GeoJSON export is a separate outstanding feature; none of these artifacts is an approved evacuation boundary.

Optional Google imagery, speech/audio and provider integrations must not be represented as complete without their own acceptance results. The original Google “wow” moment is not a prerequisite for this recovery flow.

## Workstream schedule and current status

Original windows below are **planning targets from the Saturday-to-Sunday recovery plan**, not completion timestamps. EDT is assumed. Passed windows remain partial until evidence closes their gate; the 8:00 AM freeze is a target, not an accomplished milestone.

| Workstream | Original target window | Audited status | Priority | Exit gate / remaining work |
|---|---:|---|---:|---|
| Scope and demo seed | Sat 3:15–4:00 PM | Partial | P0 | Backend venue defaults exist; final supported prompt/reset flow and team scope sign-off pending |
| Dashboard polish | Sat 4:00–6:00 PM | Partial | P0 | Map/dashboard code exists; current UI layout, metrics and source behavior require browser acceptance |
| Backend cache/physics/map guard | Sat 6:00–7:00 PM | Implemented baseline; changes in progress | P0 | Prior focused baseline passed; revalidate current release/exposure changes and their budgets |
| Frontend contract integration | Sat 7:00–9:00 PM | In progress | P0 | Verify active MapLibre UI against changed API; do not credit obsolete React/Cesium implementation |
| Explosion visualization | Sat 8:00–8:20 PM | Partial | P1 | Event handling exists; mass-conserving current behavior and actual source animation are distinct gates |
| Judge interaction shortcuts | Sat 6:00–7:30 PM | In progress | P0 | Manual controls, prompts, reset, history, action-plan display and export need final coordinator evidence |
| Reliability and provider failures | Sat 7:30–9:00 PM | Partial | P0 | Existing unit tests are not complete browser/no-network/provider-failure rehearsal |
| Props and first rehearsal | Sat 9:00–10:00 PM | Partial | P0 | Script exists; physical props, media and executed rehearsal remain outstanding |
| Google Photorealistic integration | Sat 10:00–11:30 PM | Not integrated; provider setup unverified | Optional | Backend admission guard exists; browser renderer, credentials, credits and fallback not verified |
| Visual polish and second rehearsal | Sat 11:30 PM–Sun 1:00 AM | In progress / rehearsal outstanding | P1 | Cloud geometry/wind changes need browser validation; rehearsal not evidenced |
| Freeze candidate and backup | Sun 1:00–2:00 AM | Outstanding | P0 | Rerun suites/build, resolve interaction blockers, copy/tag known-good artifact |
| Recovery buffer | Sun 2:00–5:30 AM | Replanning required | P0 | Active work has consumed buffer; finish bounded integration before adding features |
| Final smoke | Sun 5:30–6:30 AM | Planned | P0 | Three consecutive successful presentation-laptop flows, including recovery |
| Final rehearsal/recording | Sun 6:30–7:30 AM | Planned | P0 | Timed flow, teammate cues, fallback narration and recording |
| Submission freeze | Sun 7:30–8:00 AM | Planned | P0 | Verify artifact/links/assets, then stop core behavior edits |
| Stretch features | After verified freeze only | Deferred | P2 | Mobile/PWA, collaboration, vision, extra providers and custom physics shader |

## Remaining-work dependency chart

This is the execution order now, not a claim of elapsed completion:

```text
Backend release + exposure corrections ───┐
Renderer cloud + wind + budgets ──────────┼─> integrated API/UI checks
Coordinator controls + plan + exports ────┘          │
                                                  v
                                      suites + production build
                                                  │
                                                  v
                                      browser + failure drills
                                                  │
                                                  v
                                  presentation-laptop rehearsal x3
                                                  │
                                                  v
                                     freeze artifact + recording
```

Backend and renderer work can run independently; final UI validation depends on their stable contracts/results. Do not start optional integrations at the expense of the freeze gates.

## Milestone acceptance gates

| Gate | Required evidence | Current status |
|---|---|---|
| G1 — Seeded scope | One incident and supported prompt/reset flow verified against actual command behavior | Partial: backend default tested; interactive flow pending |
| G2 — Visible command center | Browser shows source, current metrics, plume, plan/history and honest data availability | In progress: coordinator UI work |
| G3 — Stateful interactive slice | Dispatch/manual edits/reset survive scrub/play/weather refresh; stale responses cannot overwrite them | In progress: helper tests are insufficient alone |
| G4 — Current automated baseline | Backend/frontend suites and production build pass after current changes; generation/geometry budgets recorded | Partial: latest build and 28 frontend tests reported passing before new video/voice/responder work; final backend integration and rerun pending |
| G5 — Provider/offline recovery | Keyless core flow and independent AI/audio/weather/map failures exercised without misleading empty/success state | Not complete; no guaranteed local offline map |
| G6 — Optional Google pass | Guarded actual tiles, visible credits, provider-denial recovery and request accounting | Not integrated/verified; omit from core pitch |
| G7 — Freeze candidate | Known-good build copied/tagged, startup checklist exercised, no unresolved blocking interactions | Outstanding |
| G8 — Presentation/submission | Three timed rehearsals, recovery line, props/assets/links verified and changes frozen | Planned |

## Supported implementation evidence

These are deliberately narrower than product-level completion claims:

- **API and model baseline:** [main.py](./backend/app/main.py), [API contracts](./backend/tests/test_api_contracts.py), [backend behavior tests](./backend/tests/test_backend_slice.py), [transport tests](./backend/tests/test_live_transport.py), [hazard-rendering tests](./backend/tests/test_hazard_rendering.py). Includes bounded Gaussian approximation, five-minute wind integration, simulated plans and candidate surface metadata. Does not validate source calibration, terrain CFD, evacuation safety or personal dose.
- **Context/services:** [context service](./backend/app/services/context.py), [context tests](./backend/tests/test_context.py), [weather fallback tests](./backend/tests/test_weather_orchestration.py). Live/cached/DEMO orchestration, weather/alerts/air quality/elevation/Overpass/routing and cache fallback exist; the old claim these services were absent was incorrect. Coverage/availability are not guaranteed.
- **AI/audio/Google backend:** [Gemini tests](./backend/tests/test_agent_provider.py), [ElevenLabs tests](./backend/tests/test_voice_provider.py), [map admission tests](./backend/tests/test_map_guard.py). Mocked provider correctness is not live voice playback, genuine resource deployment, photorealistic rendering or a hard billing guarantee.
- **Frontend helpers:** [timeline tests](./frontend/src/timeline.test.ts), [dispatch tests](./frontend/src/aiDispatch.test.ts), [playback tests](./frontend/src/playback.test.ts), [plume tests](./frontend/src/plumeLayer.test.js). New playback/cloud coverage requires current results; helper tests cannot establish WebGL visual quality or full DOM wiring.
- **Planning artifacts:** [build plan](./docs/JUDGE_READY_BUILD_PLAN.md), [request budget](./docs/API_CALL_BUDGET.md), [runbook](./docs/PERFORMANCE_RUNBOOK.md), [rehearsal script](./docs/DEMO_REHEARSAL_SCRIPT.md) exist. Their instructions/targets are not executed acceptance records, and references to old renderer paths require care.

## Active integration — do not mark complete prospectively

- [~] **Backend agent:** two-hour building/area outdoor exposure, mass-conserving release corrections, API bounds/caching/performance and focused regression results.
- [~] **Renderer agent:** merged dense cloud geometry with sparse parcel retention, negligible-concentration visual decluttering, depth/terrain behavior and bounded mesh budgets. Fifteen mesh tests are reported passing; final browser integration remains pending. The [research note](./docs/PLUME_DILUTION_AND_EXPOSURE_RESEARCH.md) recommends a provisional **renderer-only 1%-of-trace floor**, never physics deletion or a toxicological safety threshold. Hidden contributions must remain in transport, overlap summation, exposure and mass accounting; summed-field/lower-floor behavior needs verification.
- [~] **Coordinator:** manual hazard/source/weather controls with leak/burst/combined modes, release rate/duration and burst mass/time; scenario metrics, plan/history/reset/prompts and playback/exposure wiring. Backend contract integration and browser validation remain pending.
- [~] **Coordinator exports:** escaped CSV for all returned modeled building records, plus PNG/JPG map capture retaining attribution and simulation disclaimer. Verify complete rows, escaping/units/provenance, actual downloads and image content before completion. Perimeter GeoJSON remains a separate outstanding item.
- [~] **New video capture:** coordinator is implementing WebM simulation recording. Verify recording/stop/download, playable output, attribution/disclaimer, unsupported-browser handling and resource cleanup; no end-to-end acceptance yet.
- [~] **New chat/voice responders:** coordinator is implementing SpeechRecognition with transcript review and explicit Enter submission; backend agent is implementing responder parsing helpers. Verify supported commands against returned state, microphone/unsupported-browser failures and text fallback. Recognition is not response-audio playback or validated operational dispatch.
- [ ] **New-feature browser acceptance:** exercise complete WebM recording/download and chat/voice responder workflows after stable backend contracts; the earlier build/28-test checkpoint predates these additions.
- [~] **Joint final validation:** all suites/build, bounded payload/render performance, browser interactions and independent failures after the above work stabilizes.

## Outstanding feature claims from the original checklist

- [ ] React application and optional Cesium/Google renderer, if retained as requirements; current MapLibre implementation is a deliberate architectural difference, not those features completed.
- [ ] Guaranteed offline map with packaged terrain/buildings and tested style/tile failure recovery.
- [ ] Browser speech permissions/transcript and cached-audio playback end to end; text dispatch must remain usable independently.
- [ ] Altitude slicing and FLIR controls; old completion claims lack active UI evidence.
- [ ] AEGL-1/2/3 iso-surfaces: current TRACE/PEL/IDLH references and visual merged shells are not AEGL contours.
- [ ] Active-unit roster, unit markers/route overlays, genuine unit exposure/PPE model and manual location/indoor-context validation.
- [ ] Source explosion animation and complete candidate surface-contamination display. An event flag or API surface-zone list is not a working visualization.
- [ ] Uniform browser retries/backoff, complete attribution audit, mobile/field layout and verified current terrain zoom/failure behavior.
- [ ] Actual provider failure/no-key/no-network drills, presentation-laptop asset/audio checks, three rehearsals and frozen artifact.

## Real-world validation blockers

The original outline is aspirational. Before any real emergency use, independently benchmark dispersion/uncertainty against reference and field datasets; calibrate source, weather, terrain/building and deposition behavior; validate multi-hazard units, thresholds, mixture toxicology and radiation/infection interpretation; integrate actual population/occupancy/field observations; model indoor infiltration and personal exposure/PPE where claimed; and obtain qualified emergency-response review. Until then, exposure, action plans, boundaries and decontamination candidates remain explicitly **simulation-only**, not safe-route/evacuation/PPE instructions.

## Audit log

**2026-10-11:** replaced unsupported percentage/history and conflicting complete/planned labels with evidence-scoped gates. Corrected the active renderer and no-network limitation; downgraded unverified shortcuts, audio, Google/Cesium, advanced views/AEGL/personal-dose and broad reliability claims. Preserved real backend/provider/helper progress. Active cloud, exposure and coordinator UI/export work remains in progress pending final results. See [todo.md](./todo.md) for item-level status.
