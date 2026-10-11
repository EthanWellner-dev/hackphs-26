Aero-Hazard / Plume: 3D Multi-Hazard Meteorological Topographic & AI Dispatch Simulator

24-Hour Hackathon Product Architecture & Execution Roadmap

1. Executive Vision & High-Impact Demo Strategy

The Winning Pitch Formula: "Hook, Walkthrough, Ambush & Interaction"

To capture maximum attention in a 400-person MLH hackathon (hackPHS), the presentation relies on a structured 5-phase delivery: establishing real-world stakes, demonstrating how the platform works, executing an emergency "ambush" hook, and having judges test the live system themselves.

Phase 1: The Historical Hook (0–20s)

Hand judges physical laminated dossiers of past atmospheric disasters (e.g., Bhopal gas tragedy, East Palestine train derailment, Chernobyl fallout).

Pitch: "When airborne chemical, biological, or radiological disasters strike, incident commanders waste critical minutes translating raw weather and hazard data into actionable response strategies."

Phase 2: Platform & Core Capabilities Walkthrough (20s–50s)

Thoroughly demonstrate the live website dashboard using a pre-configured baseline scenario.

Walk judges through the core system layers so they understand the tool before taking control:

Explain the Mapbox 3D DEM Terrain & Building Footprints layer.

Show how Live NOAA/OpenWeather Wind Vectors drive particle movement.

Demonstrate the Chemical & Hazard Physical Library (density, buoyancy, toxicity thresholds).

Show the Time Scrubbing Bar ($t=0$ to $t=120\text{ min}$) to visualize plume drift over time.

Phase 3: The Ambush (50s–60s)

A teammate on an adjacent device triggers a video displaying a flashing red emergency alarm with warning audio.

Hand judges a sealed physical folder labeled "INCIDENT ALERT: CRITICAL SITE DISPATCH" containing a simulated emergency at the hackathon venue address.

Phase 4: Interactive Hands-On Dispatch & Agentic Control (60s–120s)

Hand the judge the main laptop: "You are the incident commander. Speak directly to our AI dispatcher or type the incident details."

The AI Dispatcher interviews the judge in real-time ("What chemical or isotope was released?", "Is it pressurized?", "Where is the breach?"), dynamically generating realistic spoken response queries via the ElevenLabs API.

The AI Agent continuously accepts live operational updates (e.g., "Deploy Engine 4 to 5th Ave", "The leak just exploded"), issuing real-time map updates and dynamic simulation recalculations.

Phase 5: Incident Action Plan & Contextual Advice (120s–150s)

Show the 3D gas cloud bending around street corridors and terrain elevation.

The AI cross-references OpenStreetMap micro-features (water fountains, HVAC intakes, schools) and user GPS context (Indoor vs. Outdoor) to generate pinpoint safety guidance for first responders and occupants.

2. Sponsor Integration Strategy (High Impact & Zero Overhead)

Best Project with ElevenLabs

Integration: Real-Time Dispatcher Voice Synthesis.

Execution: When the AI Dispatcher asks clarifying intake questions, confirms tactical commands, or announces critical safety advisories, the generated text is piped directly to the ElevenLabs Text-to-Speech API using a realistic "Emergency Dispatcher" or "Command Center" voice profile.

Impact: High sensory impact for judges—judges hear an authoritative dispatch officer responding to their inputs and operational commands in real-time.

(Note: Sponsor scope is strictly focused on ElevenLabs to maximize category win probability while keeping build complexity focused on core physics and AI intake.)

3. Platform Architecture & System Structure

Target Platform & Authentication Constraints

Primary Target: Desktop Web Application (Google Chrome optimized, 1080p command center view) with mobile-responsive layout for field updates.

Authentication Note: NO LOGIN OR USER AUTHENTICATION REQUIRED. Designed as an instant-access emergency workstation demo to eliminate judge onboarding friction.

+-----------------------------------------------------------------------------------+
|                               SYSTEM ARCHITECTURE                                 |
+-----------------------------------------------------------------------------------+
                                          |
            [ Natural Language Input ]    |    [ Manual Override Controls ]
            (Voice / Text Dispatcher)     |    (Dropdowns, Sliders, Pin Tool)
                         |                |                  |
                         v                +--------+---------+
            [ LLM AI Operations Agent ]   |
            - OpenAI GPT-4o / Gemini Flash Parser  |
            - Active Intake & Agentic Command Logic|
            - OSM Micro-Feature & GPS Sensor Engine|
                         |                         |
                         +------------+------------+
                                      |
                                      v
                   [ Dynamic Hazard Scenario Payload ]
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
[ Mapbox GL JS v3 DEM ]     [ Live Weather Vector API ]   [ ElevenLabs Voice Engine ]
(3D Buildings & Terrain)    (Wind Speed, Dir, Stability)   (Spoken Audio Generation)
         |                            |                            |
         +----------------------------+----------------------------+
                                      |
                                      v
                 [ WebGL 3D Advection-Diffusion Shader ]
                 (3D Particle Dispersion & Elevation Collision)
                                      |
                                      v
              [ Real-Time Emergency Action Plan & UI Dashboard ]




4. Frontend & Backend Blueprint (No Executable Code)

A. Directory & File Structure

aero-hazard/
├── public/
│   ├── assets/
│   │   ├── presets/              # Pre-cached fallback DEM & weather JSONs for venue
│   │   └── audio/                # Local audio cache
├── src/
│   ├── components/
│   │   ├── Map/
│   │   │   ├── MapViewport.jsx   # Mapbox GL JS 3D container & canvas overlay
│   │   │   ├── UnitMarkers.jsx   # Tactical unit & event overlay markers
│   │   │   └── ShaderLayer.jsx   # WebGL canvas overlay for advection-diffusion
│   │   ├── Dispatcher/
│   │   │   ├── ChatConsole.jsx   # Interactive voice/text dispatch input box
│   │   │   └── AudioPlayer.jsx   # ElevenLabs TTS streaming player
│   │   ├── Dashboard/
│   │   │   ├── ControlPanel.jsx  # Manual overrides (sliders, chemical pickers)
│   │   │   ├── Timeline.jsx      # Scrubbing bar (t=0 to t=120 min)
│   │   │   ├── HazardMetrics.jsx # Concentration metrics & exposure levels
│   │   │   └── ActionPlan.jsx   # Real-time disaster response recommendations
│   ├── engine/
│   │   ├── shaders/
│   │   │   ├── advection.frag   # Fragment shader for fluid advection-diffusion
│   │   │   └── raymarch.vert    # Vertex shader for 3D terrain height sampling
│   │   ├── physics/
│   │   │   └── HazardDatabase.js # Physical constants (Chlorine, Ammonia, Iodine-131, Anthrax)
│   │   ├── context/
│   │   │   ├── osmContext.js    # Overpass API parser for micro-features (fountains, HVAC)
│   │   │   └── sensorContext.js # Web Geolocation & Indoor/Outdoor state detector
│   ├── services/
│   │   ├── apiWeather.js        # Weather API service (OpenWeather/NOAA)
│   │   ├── apiLLM.js            # Agentic Dispatcher LLM service with Tool Calling
│   │   └── apiElevenLabs.js     # Text-to-Speech audio generation service
│   ├── App.jsx                  # Main application state orchestrator
│   └── main.jsx                 # Application entry point




B. Core Objects & Data Schemas

1. Scenario Config Object (ScenarioPayload)

Central data structure passed from the Dispatcher / Manual Controls to the Physics Engine and Map.

{
  "incidentId": "INC-8892",
  "location": {
    "latitude": 40.3487,
    "longitude": -74.6593,
    "addressName": "Hackathon Venue Main Building"
  },
  "hazard": {
    "type": "CHEMICAL", 
    "name": "Chlorine Gas",
    "molecularWeight": 70.9,
    "densityRelativeToAir": 2.47,
    "decayHalfLifeSeconds": null,
    "toxicityThresholds": {
      "IDLH_ppm": 10.0,
      "PEL_ppm": 1.0
    }
  },
  "release": {
    "rateKgPerSec": 15.0,
    "durationMinutes": 30,
    "isOverpressurized": true,
    "hasExploded": false
  },
  "weather": {
    "windSpeedMetersPerSec": 4.5,
    "windDirectionDegrees": 225,
    "temperatureCelsius": 18.0,
    "pasquillStabilityClass": "D"
  },
  "activeUnits": [
    {
      "unitId": "ENGINE-4",
      "label": "Engine Company 4",
      "latitude": 40.3491,
      "longitude": -74.6580,
      "status": "DEPLOYED"
    }
  ],
  "userContext": {
    "userLatitude": 40.3488,
    "userLongitude": -74.6591,
    "environmentState": "INDOORS",
    "nearbyOSMFeatures": [
      { "type": "water_fountain", "distanceMeters": 45 },
      { "type": "hvac_intake", "distanceMeters": 12 }
    ]
  }
}




2. Disaster Advice Object (EmergencyActionPlan)

Generated by the LLM Engine post-simulation to give immediate on-the-spot response steps.

{
  "hazardSeverity": "CRITICAL",
  "immediateActions": [
    "You are detected INDOORS within 50m of the breach. Seal window seams and disable HVAC unit #2 immediately.",
    "Engine Company 4 deployed at 5th Ave: Maintain upstream position; do not enter low-lying street corridor."
  ],
  "firstResponderPPE": "Level A Vapor-Protective Suit with SCBA required within PEL boundary.",
  "isolationRadiusMeters": 300,
  "decontaminationGuidance": "Water fountain source identified 45m east; establish primary wash station downwind."
}




C. Major Functional Modules

1. Agentic Intake & Command Engine (apiLLM.js)

Function: processUserDispatchInput(userInputHistory, currentConfig)

Logic:

Sends user input (speech/text) to LLM configured with function tools (update_simulation, deploy_unit, trigger_event).

Parses natural language commands (e.g., "Unit 4 on 5th Ave", "The tank exploded") and converts them into structured updates to ScenarioPayload.

If parameters are missing during initial report, outputs clarifying intake questions.

Continuously updates simulation state and returns tactical status confirmation.

2. OpenStreetMap & Sensor Context Engine (osmContext.js, sensorContext.js)

Function: fetchMicroContext(lat, lng) & getUserEnvironmentState()

Logic:

Queries OpenStreetMap Overpass API for nearby urban micro-features (water sources, fountains, hydrants, schools, HVAC intakes).

Uses Web Geolocation API and device telemetry (accuracy radius, light sensor, network state) to determine if user is INDOORS or OUTDOORS.

Feeds micro-feature spatial context directly into the AI advice generation pipeline.

3. Voice Dispatcher Engine (apiElevenLabs.js)

Function: speakDispatcherResponse(textPrompt)

Logic:

Receives text output from processUserDispatchInput.

Sends request to ElevenLabs /v1/text-to-speech endpoint using a clear voice model ID (e.g., "George - Dispatch Commander").

Returns streaming audio buffer for immediate web browser playback.

4. Advection-Diffusion Solver (ShaderLayer.jsx)

Function: renderPhysicsFrame(glContext, scenarioPayload, elapsedTime)

Logic:

Binds elevation heightmap texture (sampled from Mapbox DEM) and 3D building bounds.

Passes wind velocity vectors $\mathbf{u} = (u, v)$ as uniform parameters to the WebGL fragment shader.

Evaluates transport equation over grid cells:

$$\frac{\partial C}{\partial t} = -\mathbf{u} \cdot \nabla C + D \nabla^2 C + S - \lambda C$$

Renders volumetric density color map (Red = IDLH threshold, Yellow = PEL threshold, Blue = Trace dispersion).

5. Comprehensive Multi-Hazard Library

Hazard Category

Sample Hazards

Physical Behavior in Simulator

Chemical

Chlorine, Ammonia, Methane

Heavy gas pooling in low elevation terrain vs. light buoyant atmospheric ascent.

Nuclear / Radiological

Iodine-131, Cesium-137

Downwind transport combined with exponential radioactive decay ($\lambda = \frac{\ln 2}{t_{1/2}}$) and dry particle settling.

Biological

Aerosol Pathogens, Anthrax

Temperature/UV-sensitive decay rate with turbulent atmospheric diffusion.

6. Hour-by-Hour 24-Hour Build Plan

Time Window

Module Focus

Primary Tasks & Deliverables

Hours 00–03

Foundation & Setup

Initialize React Vite project, Mapbox GL JS v3 map viewer with 3D DEM building extrusions. Setup local venue data cache.

Hours 03–07

LLM & ElevenLabs Integration

Build LLM JSON parser and agentic tool calling for emergency intake and map commands. Connect ElevenLabs TTS API.

Hours 07–11

3D WebGL Shader Engine

Implement WebGL fragment shader overlay on Mapbox. Code 3D advection-diffusion transport with terrain sampling.

Hours 11–15

Context Engine & Hazard Library

Connect OSM Overpass API for spatial micro-features and browser GPS sensor context. Map physical hazard profiles.

Hours 15–18

UI Command Center Dashboard

Assemble timeline scrubbing bar ($t=0$ to $t=120\text{ min}$), manual override panel, and threat metric cards.

Hours 18–21

Prop Setup & Polish

Finalize laminated historical dossiers and physical "Hot Incident File" folder. Test local fallback caching.

Hours 21–24

Rehearsal & Hardening

Practice presentation script with team members and full voice dispatch testing.

7. Stretch Goal / Winning Suite Roadmap (If Built Ahead of Schedule)

Multi-User Real-Time Mobile Response & Agent Network

If the team completes the core web platform early:

Mobile Web View: Responsive, light PWA layout optimized for field personnel mobile screens.

Role-Based Live Sync: WebSockets / Firebase Realtime synchronization allowing multiple participants to join the active incident session.

Role Assignments:

Incident Commander: Oversees global plume map, edits release parameters, issues site-wide advisories.

AI Operations Agent: Continuously updates unit locations, processes field natural language updates, and recalculates plume impact in real-time.

First Responder / Field Units: Receives immediate localized hazard warnings based on mobile GPS, views indoor/outdoor micro-advice (e.g., HVAC shutoff, nearest water source), and views unit-specific protective gear requirements (PPE Level A/B).

Evacuation Lead: Coordinates facility shelters and road blocks away from downwind plume corridors.

Centralization: Centralized command view where the commander and AI agent co-pilot the response effort.

8. Demo Presentation Script (2.5-Minute Pitch)

+-----------------------------------------------------------------------------------+
|                            2.5-MINUTE JUDGE DEMO FLOW                             |
+-----------------------------------------------------------------------------------+
| 0:00 - 0:20 | Hand historical disaster dossiers to judges                         |
| 0:20 - 0:50 | Walkthrough website features (Mapbox 3D, Physics, Weather, Timeline) |
| 0:50 - 1:00 | Teammate plays fake alarm video; hand judge venue hot file          |
| 1:00 - 1:50 | Judge speaks/types to AI Dispatcher; Agent executes map commands    |
| 1:50 - 2:30 | Review 3D plume, OSM micro-context, and GPS Indoor/Outdoor Plan    |
+-----------------------------------------------------------------------------------+




Step 1: Historical Hook (0:00–0:20)

Hand judges laminated disaster dossier cards.

"When airborne chemical or radiation leaks happen, existing static maps can't account for how gas moves through real terrain and around buildings."

Step 2: Platform Walkthrough (0:20–0:50)

Show live website dashboard using a demo sample.

"Here is our core 3D Command Center platform. It integrates Mapbox 3D elevation heightmaps, building footprints, live NOAA wind vectors, and a custom WebGL advection-diffusion solver. Notice how scrubbing the timeline shows atmospheric dispersion over two hours."

Step 3: The Ambush Hook (0:50–1:00)

Teammate plays emergency alarm video on secondary laptop. Hand judge the venue hot file.

"We just received an emergency alert at this venue address!"

Step 4: Interactive Dispatch & Agentic Control (1:00–1:50)

Hand judge the laptop/tablet.

Encouraged to state: "Chlorine gas leak at main entrance, pressurized. Deploy Unit 4 to 5th Ave."

The AI Dispatcher speaks back using ElevenLabs: "Incident logged. Unit 4 deployed to 5th Avenue. Requesting estimated release rate and containment status." The unit marker appears on 5th Ave dynamically.

Step 5: Contextual Action Plan & Plume Visualization (1:50–2:30)

Watch the 3D yellow gas cloud flow down street corridors around the high school venue.

Review the dynamically generated Emergency Action Plan: highlighting GPS location, indoor/outdoor shelter advice, and nearest OpenStreetMap micro-features (HVAC intakes, water sources).