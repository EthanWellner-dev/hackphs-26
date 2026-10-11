# Judge Demo Rehearsal Script

## One-sentence pitch

> Aero-Hazard turns a chemical release, weather, and local context into a fast, explainable plume forecast and commander action plan — without depending on live services to stay operational.

## Visual target

Use the supplied dark tactical command-center reference as the hierarchy:

- Header: product name, simulator label, and system state.
- Dominant center: fixed venue scene with a bright source marker, colored plume bands, wind vectors, and restrained labels.
- Left/near scene: incident summary, hazard metrics, and action plan.
- Right rail: timeline, field context, provenance, and system logs.
- Avoid decorative dashboards that compete with the plume. The plume, current time, threat band, and next action must be readable from a few feet away.

## 150-second run

### 0–15 seconds: hook

Show the baseline chlorine release at the seeded venue.

Say:

> “This is the answer to one operational question: if the release changes now, what is threatened next, and what should the commander do?”

Point to the source, wind arrow, TRACE/PEL/IDLH legend, and approximation disclaimer.

### 15–35 seconds: explain the layers

Point to four facts only:

1. The backend owns the validated scenario and plume calculation.
2. The scene shows transport direction and threshold bands.
3. Nearby context identifies response factors such as schools, roads, hydrants, or HVAC-related fixtures.
4. The action plan exposes assumptions and provenance instead of pretending certainty.

Do not open provider dashboards or show raw JSON.

### 35–70 seconds: judge interaction

Invite the judge to type or say:

> “The leak just exploded. Increase the wind and deploy Engine 4 south.”

Expected visible changes:

- Scenario version increments.
- Release state becomes escalated.
- Plume changes direction/intensity.
- Source pulse appears once.
- Command history records the event.
- Active unit state shows Engine 4.
- Action plan updates.
- Text response appears immediately; cached voice is optional.

### 70–100 seconds: time travel

Scrub from T+0 to T+60 or T+120.

Say:

> “The commander can inspect the next two hours without asking the weather provider or the map provider to recompute the world.”

Verify that the scenario version, command state, and provenance remain intact.

### 100–130 seconds: operational value

Open the action-plan details and show:

- Immediate actions.
- PPE guidance.
- Isolation radius.
- Shelter direction.
- Decontamination/surface caveat where applicable.
- Nearby context used.
- LIVE/CACHED/DEMO provenance.
- Simulation-only disclaimer.

### 130–150 seconds: resilience and wow pass

If the guarded Google scene is reliable, show the fixed venue camera as a visual enhancement and keep attribution visible. Otherwise stay in the local safe scene and say:

> “The same plume and action plan remain available when the map provider is unavailable. The expensive renderer is an optional background, not the product.”

Optionally demonstrate reset. Reset must return to baseline without a network request.

## Seeded prompts

1. **Baseline:** `Give me the current incident status.`
2. **Escalation:** `The leak just exploded; increase the wind and deploy Engine 4 south.`
3. **Unknown intake:** `I don't know the release status.`
4. **Recovery:** `Reset to the baseline incident.`

Deterministic prompts are preferred during judging because they demonstrate reliability and avoid unnecessary model calls.

## Recovery lines

- **Backend unavailable:** “The last validated frame is still visible; the local scene is designed for this failure.”
- **Gemini unavailable:** “The deterministic command path is active; the safety state does not depend on an LLM.”
- **Voice unavailable:** “The text response remains authoritative for this simulation; audio is an enhancement.”
- **Google unavailable:** “The provider mesh fell back, but our plume physics and action plan are application-owned.”
- **Judge asks if it is real:** “It is a bounded decision-support simulation, not a certified evacuation or atmospheric authority.”

## Rehearsal gates

Run the complete flow three times in each mode:

- Offline/no-key safe mode.
- Cached backend with provider keys available.
- Optional guarded Google mode, only if the fixed camera and fallback pass.

Record:

- Time to first visible scene.
- Time from dispatch submit to visible changed plume.
- Number of network requests during the run.
- Provider requests after bootstrap.
- Google root-session count.
- Whether reset works without reload.
- Whether a judge can read the key state from 2–3 meters away.

If the optional wow pass causes a blank scene, latency spike, or additional root session, disable it before the presentation.
