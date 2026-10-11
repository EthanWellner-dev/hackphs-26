# Performance and Demo Runbook

## Purpose

Use this runbook to keep the judge flow fast, deterministic, and safe from accidental provider or Google Maps charges.

## Startup order

1. Run the VS Code task **Backend API (local)** (uses `backend/.venv/Scripts/python.exe`), or run `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000` with the backend environment active. Open `http://127.0.0.1:8000/docs`; health is `/api/health`.
2. Start the frontend.
3. Confirm the health endpoint returns `status=ok`.
4. Confirm the frontend shows the seeded incident and `OPEN_3D`/local-safe renderer status.
5. Confirm the first view contains no blank map and no loading spinner after the cached fixture is available.
6. If enabling Google Photorealistic mode, call the backend map-session endpoint first and confirm that it returns a non-null session ID and explicit `PHOTOREALISTIC` mode.

## Safe-mode defaults

Use safe mode for development and rehearsal:

```text
GOOGLE_PHOTOREALISTIC_ENABLED=false
GOOGLE_PHOTOREALISTIC_FALLBACK_MODE=OPEN_3D
```

The frontend must not construct a Google renderer from the presence of `GOOGLE_MAPS_API_KEY` alone. A key is not authorization to open a new session.

## Request budget

The enforceable per-action policy is maintained in [API_CALL_BUDGET.md](./API_CALL_BUDGET.md). This runbook is the operator-facing version; if a proposed feature exceeds that budget, it is out of scope for the judge build.

### Startup

- Scenario: one cached request.
- Context: one cached request.
- Initial plume: one cached request.
- Map session: one cached request.
- No provider request is required for the local scene.

### Interaction

- Dispatch: one POST request, plus optional cached audio behavior.
- Timeline: one settled request per selected time. Use the current scenario with `POST /api/plume`; never rebuild the default scenario with `GET /api/plume` after dispatch.
- Map: zero new Google root sessions during dispatch, timeline scrubbing, camera movement, or overlay updates.

## Performance budgets

| Measurement | Target | Hard stop |
|---|---:|---:|
| Backend plume generation | <100 ms | 1 s |
| Visible particles | 600 typical, instanced | 1,600 renderer cap |
| Visible volume cells | 10 | 10 |
| Timeline debounce | 90 ms | 25 cached five-minute frames per scenario revision |
| Google root sessions per app session | 1 | 1 |
| Weather refresh after bootstrap | Every 300 seconds | Cached provider snapshot reused between refreshes |
| Local scene | 55+ FPS | 45 FPS |
| Initial safe-path JavaScript | Keep map SDKs out of initial route | No eager paid renderer |

## Forecast playback and exposure view

- **PLAY 2 HOURS** starts at T+0 on first play, advances in five-minute steps and stops at T+120. Pause/resume and restart are available. Buffering waits for the next frame instead of skipping predicted intervals. Scrubbing, dispatch and weather changes cancel playback; revision-scoped caching holds at most 25 frames.
- **2H EXPOSURE** is a fixed T+0–120 incident forecast, not the instantaneous scrubber frame. It displays bounded area samples and available building footprints. Click a polygon for peak, mean and time-integrated outdoor concentration.
- A concentration-time integral in **ppm·min** (gas) or **mg·min/m³** (aerosol) is not inhaled or absorbed dose. Occupancy, indoor infiltration, breathing rate and PPE are not modeled. Colors compare mean modeled concentration with the selected hazard's concentration references; they are not validated two-hour safe-dose classifications.
- Exposure results invalidate when scenario or weather changes. Empty/missing building coverage is labeled; no houses or occupants are fabricated.
- **CSV LIST** exports all returned building exposure records with units and interpretation, not only the top rows visible on screen. **PNG MAP / JPG MAP** capture the shaded viewport and include source attribution, weather provenance and a simulation disclaimer. Wait for map tiles and exposure calculation before exporting.
- **VIDEO ↓** preloads the same full-quality 25 frames, then records forecast playback to WebM. Browser MediaRecorder/canvas capture support is required. Pause or scenario changes interrupt playback; do not interpret a shortened recording as a complete forecast.
- Release controls expose constant-rate leak, instantaneous gas release and combined leak-plus-burst, with rate, duration, impulse mass/time and hazard presets. These model gas transport, not blast damage.
- The small blue orb starts browser speech recognition when supported. Review the transcript and press Enter; typed messages use the identical dispatch endpoint. Microphone denial/unsupported browsers retain text input. Responder markers represent simulated positions, not live vehicle tracking.
- Dilution/culling rationale and authoritative references: [Plume dilution and exposure research](./PLUME_DILUTION_AND_EXPOSURE_RESEARCH.md). The display cutoff is not a safety limit and never deletes physical mass or exposure contributions.

## Readiness and weather evidence

Backend verification on 2026-10-11: 85 tests pass, including weather fallback orchestration, mass scaling, changing-wind transport and API contracts. A live bootstrap returned Open-Meteo `LIVE`, `MODEL_CURRENT`, `stale=false`, a 15-minute native sample interval and `refreshAfterSeconds=300`. A 10 kg scenario produced about 11.82 ppm at T+30; doubling mass doubled concentration. These values are smoke-test evidence, not calibrated hazard predictions.

Open-Meteo is primary; provider failure or stale-cache warnings trigger a NOAA hourly forecast fallback. NOAA is labeled forecast, not a station observation. If both fail, stale/DEMO provenance remains explicit and other context providers are still queried. Five-minute transport knots interpolate provider forecasts; they do not claim five-minute measured wind. Incident epochs survive API serialization.

**Not operationally validated:** obstacle deflection is heuristic, not terrain CFD; affected area is a bounded approximate raster; population data is unavailable. Radiological/biological outputs are mass concentration, not dose/infection risk. Mixtures lack component-specific toxicology. Unit deployment is not a real resource-management system; indoor detection, safe-route validation, calibrated source terms, field-sensor assimilation, and emergency-authority review remain outstanding. Do not present this as suitable for independent evacuation, PPE or decontamination decisions.

## Failure drills

### No API keys

Expected result: local scenario, local plume, text dispatch fallback, and `OPEN_3D`/local renderer status. No blank state.

### Gemini unavailable

Expected result: deterministic command shortcuts and a visible deterministic provider label.

### ElevenLabs unavailable

Expected result: text response remains complete; cached audio or text-only status is shown.

### Live context unavailable

Expected result: cached or demo context with provenance and warning labels.

### Google session denied or quota exhausted

Expected result: no Google tiles request; local/open scene remains visible; guard reason is displayed.

### Slow network

Expected result: last valid frame remains visible while a new timeline frame loads. A stale response must not overwrite a newer selected time.

## Judge flow rehearsal

1. Start from the seeded baseline.
2. Say or type: `The leak just exploded; increase the wind and deploy Engine 4 south.`
3. Verify scenario version increments and the plume/action plan visibly changes.
4. Scrub to T+60 and T+120.
5. Verify command state is still present after timeline changes.
6. Open action-plan details and point out isolation, shelter, PPE, provenance, and disclaimer.
7. Reset to baseline.
8. Repeat once offline and once with the optional guarded map mode.

## Capture checklist

Record these values during the final rehearsal:

- Backend test count and result.
- Frontend build result.
- Startup request count.
- Provider request count after bootstrap.
- Google root-session count.
- Worst plume generation time.
- Worst timeline response time.
- Approximate local render FPS.
- Whether the reset flow completes without a page reload.

If any hard stop is exceeded, disable optional map effects first. Do not reduce safety labels or remove fallback behavior to improve the visual score.
