# Aero-Hazard / Plume Planning Documents

These documents define the proposed product structure before implementation. They intentionally contain architecture, contracts, provider choices, and operational boundaries only. No frontend or backend source code is included yet.

## Documents

- `PROJECT_STRUCTURE.md` - proposed React frontend and Python backend layout, responsibilities, and request flow.
- `DOMAIN_OBJECTS.md` - major objects exchanged between the UI, API, simulation, and AI services.
- `API_AND_MODEL_PLAN.md` - free-tier provider choices, Gemini model assignments, quotas, keys, and fallback rules.

## Product boundary

The hackathon build is a decision-support simulator for a fictional incident. It is not a certified plume model, evacuation authority, medical device, or emergency dispatch replacement. Every generated plan should be labeled as simulated and should expose its assumptions.

## Recommended first implementation slice

1. Load one venue scenario from a local fixture.
2. Render the map, source point, plume approximation, timeline, units, and metrics.
3. Send text dispatch input to the Python API and receive a validated scenario patch.
4. Generate a short dispatcher response with Gemini and cache/play it through ElevenLabs.
5. Add live weather and OpenStreetMap context only after the cached demo path works.

## Build and performance plan

- [Judge-ready build plan](./JUDGE_READY_BUILD_PLAN.md) — implementation phases, architecture, acceptance gates, and the five-minute judge flow.
- [Performance runbook](./PERFORMANCE_RUNBOOK.md) — request budgets, failure drills, startup order, and rehearsal checks.
- [API call budget](./API_CALL_BUDGET.md) — per-action request limits, cache tiers, TTLs, scheduler behavior, and cost stops.
- [Demo rehearsal script](./DEMO_REHEARSAL_SCRIPT.md) — the 150-second judge flow, seeded prompts, recovery lines, and rehearsal gates.

The non-negotiable order is: verify backend physics and cache behavior, build the local safe scene, add judge-visible state, then attempt the optional Google Photorealistic pass. Paid or city-scale 3D is never required for startup or the core interaction.

## Google 3D billing boundary

The optional USA-wide photorealistic scene uses a dedicated Google Maps project and a restricted browser key. The listed Photorealistic 3D Tiles allowance is 1,000 root tileset requests per month, but a Cloud Billing budget is an alert rather than a hard stop. The implementation must also set a lower Google quota, such as 900 root sessions/month, and fall back to `OPEN_3D` when the application guard or provider quota is reached. Never enable other Google Maps SKUs in that project.
