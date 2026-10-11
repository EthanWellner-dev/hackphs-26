# Performance and Demo Runbook

## Purpose

Use this runbook to keep the judge flow fast, deterministic, and safe from accidental provider or Google Maps charges.

## Startup order

1. Start the backend with the local environment file loaded.
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
| Visible particles | 24 | 24 |
| Visible volume cells | 16 | 16 |
| Timeline debounce | 220 ms | 250 ms |
| Google root sessions per app session | 1 | 1 |
| Normal-demo provider requests after bootstrap | 0 | 0 |
| Local scene | 55+ FPS | 45 FPS |
| Initial safe-path JavaScript | Keep map SDKs out of initial route | No eager paid renderer |

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
