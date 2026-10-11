# Chemical fate, surface deposition, and decontamination research

**Research checked:** 2026-10-10. **Use:** backend simulator design only. This is not a cleanup authorization, exposure assessment, or regulatory model.

## Does chemical weight change how fast an area changes?

Yes, but molecular weight alone is not the governing variable.

- **Gas density affects near-source motion.** At the same temperature and pressure, a gas's density is approximately proportional to molecular weight. A dense-than-air gas can drain and pool near the ground; a lighter-than-air gas tends to rise. The actual result also depends on release temperature, pressure, jet momentum, wind, turbulence, terrain, and whether the material evaporates from a liquid.
- **Molecular weight is not a simple “faster/slower” knob.** Wind-driven advection transports the center of mass at the wind velocity. Molecular diffusion depends on temperature, pressure, and molecular diffusivity; heavier molecules often diffuse somewhat more slowly, but atmospheric turbulent mixing usually dominates at the scale shown by this demo.
- **Volatility and boiling point can dominate.** A low-boiling liquid may rapidly evaporate and create a vapor cloud; a low-vapor-pressure liquid may mostly remain on surfaces or soil. Solubility, vapor pressure, Henry's law behavior, reactivity, and aerosol particle size can matter more than molecular weight.
- **Chemical transformation changes persistence.** Sunlight, oxidation, hydrolysis, microbial action, and radioactive decay can remove or transform material. Rain can wash deposited material from one surface to another, while dry deposition and resuspension can move particles back into air.

The backend should therefore use density for buoyancy/near-ground behavior, but should not claim that density directly determines plume travel speed. A future hazard library needs volatility, vapor pressure, water solubility, Henry's-law or partitioning behavior, reactivity, deposition velocity, and half-life where applicable.

## Can chemicals stick to walls and surfaces?

Yes. A gas cloud may adsorb to porous or reactive materials, condense on cold surfaces, or deposit as droplets/particles. Indoor surfaces, HVAC filters, soil, vegetation, clothing, and equipment can become secondary sources. Persistence is chemical- and surface-specific: chlorine is reactive and can be consumed by moisture and surfaces; ammonia can be absorbed by water films and react with acidic material; radioactive or biological aerosols are particle/deposition problems rather than just gas-density problems. These examples are qualitative and must not be used to select a cleanup method.

A safe simulator behavior is:

1. Distinguish **airborne concentration** from **surface loading**.
2. Mark a surface as potentially contaminated only when the modeled plume intersects it and the hazard profile says deposition/adsorption is relevant.
3. Show affected structures and surfaces as **candidate sanitation/decontamination zones**, not as certified clearance boundaries.
4. Keep these zones active after airborne concentration falls, with a separate persistence/decay/resuspension state.
5. Never invent a decontaminant, contact time, PPE, re-entry limit, or clearance test. Those require the substance-specific SDS, qualified industrial hygiene, and incident-command guidance.

## Sources

- NOAA Air Resources Laboratory, READY Pasquill classes: https://www.ready.noaa.gov/READYpgclass.php
- NOAA Air Resources Laboratory, HYSPLIT transport and dispersion model overview: https://www.ready.noaa.gov/HYSPLIT.php
- U.S. EPA, Air Quality Dispersion Modeling — Preferred and Recommended Models: https://www.epa.gov/scram/air-quality-dispersion-modeling-preferred-and-recommended-models
- U.S. EPA, ALOHA software overview: https://www.epa.gov/cameo/aloha-software
- Open-Meteo API documentation: https://open-meteo.com/en/docs
- CDC/ATSDR, Toxicological Profile for Chlorine (PDF): https://www.atsdr.cdc.gov/toxprofiles/tp88-c4.pdf
- CDC/NIOSH, Pocket Guide to Chemical Hazards index: https://www.cdc.gov/niosh/npg/npgsyn-a.html

## Implementation boundary

This research supports relative visualization and task prioritization. It does not make the frontend image's displayed plume, ppm, affected area, or cleanup boundary operationally valid. Any decontamination area must be labeled simulated/candidate until confirmed by sampling and an approved response plan.
