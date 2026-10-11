# Plume dilution, exposure endpoints, and visual culling

Verified against the sources below on 2026-10-11. These are research-backed design recommendations, not a certification of model accuracy or a determination that an area is safe.

## Can dilute gas be deleted?

**Dilution does not destroy gas mass.** Concentration can fall because the same mass occupies a larger volume. Conservation of mass applies to gases; diffusion redistributes molecules rather than removing them. In a closed, nonreactive system, diffusion tends toward spatially uniform concentration, not zero concentration. [1, 2]

Implementation implication: retire a *render object* independently of its physical state. Physical mass can leave the modeled domain through accounted boundary flux, or transfer through explicitly modeled reactions, deposition, adsorption, or other sinks. Record those transfers; do not pretend that low concentration itself is a sink. Chemical reaction can consume a parent species without destroying total mass.

## Health endpoints are chemical- and duration-specific

EPA publishes AEGLs for **10 minutes, 30 minutes, 1 hour, 4 hours, and 8 hours**. AEGL-1 concerns notable discomfort/irritation or certain reversible effects; AEGL-2 concerns irreversible or serious long-lasting effects or impaired escape; AEGL-3 concerns life-threatening effects or death. EPA explicitly notes that effects can occur below AEGL-1 and that unusually susceptible individuals may respond below corresponding AEGL levels. Therefore, **below AEGL-1 is neither “no gas” nor a universal safe condition**. [3]

NOAA defines a toxic Level of Concern (LOC) as a concentration associated with a specified exposure duration. ALOHA uses **60-minute AEGL values** in its chemical library; its threat zones indicate where concentration is predicted to exceed a selected LOC at some time after release. This is not equivalent to proving a person experienced that concentration continuously for an hour. [4]

Implementation implication: store endpoint chemical, units, duration, source, and status; retain concentration-time histories. Do not apply an instantaneous comparison or a simple concentration-times-time scaling as a universal toxicological dose model. Missing AEGLs mean missing guidance, not zero hazard.

## Recommended display floor (engineering choice, not EPA/NOAA guidance)

Define a documented, positive `traceConcentration` for the selected chemical, units, and display configuration. An initial **renderer-only** floor can be:

```text
visualCullConcentration = 0.01 * traceConcentration
```

This means **1% of the configured trace concentration**, not 1% gas by volume, not 1% remaining mass, and not a safety threshold. Keep this reference fixed during a scenario rather than tying it to the current plume peak. If no trace reference exists, require an explicit display setting instead of inventing a health endpoint.

Apply culling to the **summed concentration field**: overlapping individually faint puffs may collectively exceed the floor. Keep culled contributions in transport, exposure calculations, overlap summation, and mass accounting. Re-render if concentrations rise. Prefer conservative aggregation/coarsening to physics deletion.

Validate this provisional floor by comparing rendered contours at lower floors. Separately test conservation and unchanged exposure results with visual culling enabled/disabled. Label hidden regions “below display threshold,” never “safe.”

## Units and calm/inert behavior

NIOSH defines gas/vapor ppm by volume and supplies ppm-to-mg/m³ conversion factors at **25°C and 1 atmosphere**. [5] For an ideal gas at those conditions:

```text
mg/m³ = ppm * molecularWeight_g_per_mol / 24.45
```

The factor changes with temperature and pressure. Molecular weight is not density; pollutant mass concentration is not pure-gas density or total mixture density. A 2D mass/area field cannot become mg/m³ without a defensible vertical distribution or mixing depth.

Inertness does not stop diffusion. Zero mean wind does not imply zero molecular diffusion or justify deleting the cloud. [2] NOAA warns that below **3 mph**, mixing can be slower and concentrations higher than ALOHA predicts. It also warns about near-source patchiness, assumes constant wind and flat terrain, and does not model atmospheric chemical reactions. Do not treat a suppressed ALOHA contour as evidence of absent gas. [6]

## Verified sources

1. NASA, *Conservation of Mass*: https://www.grc.nasa.gov/www/k-12/airplane/mass.html
2. OpenStax via LibreTexts, *Effusion and Diffusion of Gases*: https://chem.libretexts.org/Bookshelves/General_Chemistry/Chemistry_2e_(OpenStax)/09%3A_Gases/9.05%3A_Effusion_and_Diffusion_of_Gases
3. EPA, *About Acute Exposure Guideline Levels*: https://www.epa.gov/aegl/about-acute-exposure-guideline-levels-aegls
4. NOAA, *Toxic Levels of Concern*: https://response.restoration.noaa.gov/oil-and-chemical-spills/chemical-spills/resources/toxic-levels-concern.html
5. CDC/NIOSH, *Pocket Guide Introduction*, Conversion Factors: https://www.cdc.gov/niosh/npg/pgintrod.html
6. NOAA, *ALOHA's Limitations*: https://response.restoration.noaa.gov/oil-and-chemical-spills/chemical-spills/response-tools/alohas-limitations.html
