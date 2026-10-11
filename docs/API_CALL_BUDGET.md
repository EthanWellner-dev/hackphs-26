# API Call Budget and Request Policy

**Status:** Final planning contract for the judge build  
**Goal:** make the demo feel instant while preventing accidental provider, Google Maps, or model spend.

## Non-negotiable rule

The judge interaction loop must be local-first. External APIs enrich the incident; they never gate the first render, plume animation, timeline scrubbing, reset, or text dispatch fallback.

The frontend must never call a provider directly. All provider access goes through the backend cache and provenance layer. The Google browser key is only usable after `/api/map/session` grants a guarded session.

## Request budget by user-visible action

| Action | Allowed app requests | Expected provider requests | Cache rule |
|---|---:|---:|---|
| Initial page load | 1 bootstrap request, or at most 4 legacy GETs | 0 when fixture/cache is present | Cache scenario/context/frame/map config in memory and session storage |
| Timeline drag | 0 while dragging; 1 after 220 ms settle | 0 | POST current scenario + time; reuse exact frame key |
| Dispatch | 1 POST | 0 for deterministic commands; at most 1 Gemini call on an uncached message | Cache by normalized message + canonical scenario + model |
| Audio response | 0 if cached | at most 1 ElevenLabs call per exact text/voice pair | Replay MP3; text-only fallback |
| Reset | 0 if baseline is cached | 0 | Restore the immutable baseline object locally |
| Open safe scene | 0 | 0 | Local vector/fixture scene |
| Request optional Google scene | 1 guard request, then 1 root tileset session maximum | 1 guarded Google root session | Reuse session; no recreation on camera/timeline/state changes |
| Provider refresh | explicit operator action only | bounded by provider TTL | Never refresh on render or timeline updates |

## Bootstrap contract

Preferred future shape:

```text
GET /api/bootstrap
  scenario
  frame at T+30
  context
  mapSession
  capabilities
```

Until the aggregate endpoint exists, the frontend may issue the four existing startup requests in parallel. The request scheduler must deduplicate identical in-flight requests and preserve cached values while refreshing.

A bootstrap response should be immutable for the active frontend session except for the scenario/frame returned by dispatch. It should not poll.

## Cache tiers

### Tier 0 — immutable demo fixtures

- Seeded scenario.
- Initial plume frames at T+0, T+30, T+60, and T+120 if precomputed.
- Nearby context/building fixture.
- Local scene metadata.

These make startup and offline rehearsal independent of network state.

### Tier 1 — process/session cache

- Backend frame cache: canonical scenario hash + scenario version + time + solver revision.
- Agent decision LRU: existing bounded cache.
- Voice/audio cache: exact response text + voice ID.
- Frontend in-memory cache: active frame, context, map guard, dispatch result.

### Tier 2 — persistent cache

- Provider JSON cache in `backend-cache/`.
- Google usage/session counter in `backend-cache/google-map-usage.json`.
- Browser `sessionStorage` for safe GET responses and last known bootstrap.

Every cache read must preserve the original provenance and attach age/freshness metadata where available.

## Canonical cache keys

```text
frame:{solverRevision}:{sha256(canonicalScenario)}:{scenarioVersion}:{timeMinutes}
agent:{model}:{sha256(normalizedMessage + canonicalScenario)}
audio:{voiceId}:{sha256(responseText)}
context:{provider}:{lat4}:{lon4}:{destinationLat4}:{destinationLon4}
map-session:{browserSessionId}
```

Never use only `timeMinutes` as a frame key. That would allow a post-dispatch frame to overwrite the baseline frame.

## Scheduler behavior

1. Read the cache before creating a request.
2. Reuse an identical in-flight promise.
3. Abort or ignore stale timeline responses.
4. Keep the last valid frame visible while a request is pending.
5. Do not retry user actions automatically unless the operation is idempotent.
6. Use one bounded retry for transient GET provider errors only; do not retry quota, authentication, validation, or billing errors.
7. Expose request name, cache hit, duration, and fallback status in developer diagnostics only.

## Provider TTL policy

| Provider | Freshness window | Manual refresh allowed |
|---|---:|---|
| Open-Meteo weather | 5 min | Yes |
| Air quality | 15 min | Yes |
| NOAA alerts | 5 min | Yes |
| Elevation | 24 h | Yes |
| OSM context | 24 h | Yes |
| OSM buildings | 24 h | Yes |
| OSRM route | 24 h | Yes |
| Gemini decision | exact request cache | No automatic refresh |
| ElevenLabs audio | permanent local cache for exact text | No automatic refresh |
| Google root tileset | guarded 3 h session | Never recreate from UI state |

## Cost and abuse stops

- Disable Photorealistic mode when the key is missing, the backend guard denies a session, or the fixed venue bounds are not active.
- Never allow a free camera to explore New York City, the entire United States, or an unbounded tile region during the demo.
- Never prefetch Google tiles, scrape tile URLs, or persist Google tile content.
- Do not request live context on every timeline tick.
- Do not call Gemini for deterministic phrases: explosion, increase/decrease wind, deploy, unknown, status, reset.
- Do not call ElevenLabs until the response is stable and cacheable.
- Keep the exact provider source and cache age visible in the provenance panel.

## Acceptance tests

The plan is complete only when these are measurable:

- Startup uses no more than one aggregate request or four parallel existing requests.
- A timeline drag produces no request until settled, then exactly one request for the final time.
- Timeline updates retain the dispatched scenario version.
- Reset produces zero network requests after bootstrap.
- Repeating the same dispatch produces a cache hit and no second model call.
- Replaying the same response produces a cache hit and no second audio call.
- Safe mode produces zero Google requests.
- Guarded Google mode creates at most one root session and reuses it.
- A failed or denied Google session leaves the local scene visible.
- Offline startup succeeds when Tier 0/Tier 2 cache is available.
