# Irrigation data feasibility: GMIA v5 pilot, 2026-11-03

## Computed, not inferred

Official [FAO Global Map of Irrigation Areas v5](https://www.fao.org/aquastat/en/geospatial-information/global-maps-irrigated-areas/latest-version/) archives:
- equipped area per pixel: hectares, around 2005;
- percentage of equipped area classified as irrigated using surface water;
- percentage of equipped area classified as irrigated using groundwater.

The [Python script](scripts/gmia_irrigation_source_pilot.py) downloaded original FAO files and the [TFDD 2024 BCU GIS](https://transboundarywaters.ceoas.oregonstate.edu/spatial-datasets), identified original file hashes and produced [BCU-level estimates](results/irrigation_pilot/gmia_v5_surface_groundwater_3basins_bcu.csv). [Full provenance and checks](results/irrigation_pilot/gmia_provenance.json).

**Verified result**: 25 BCU across NGER (Niger), VOLT (Volta), ZAMB (Zambezi); 23 BCU have a positive area equipped for irrigation in the *raster-centre aggregation*. The sum of FAO grid-cell equipped-area estimates across selected BCU is approximately **850,590 hectares** around 2005. These are not observed actual annual irrigated or planted crop hectares and may be biased at BCU boundaries by cell-center inclusion.

Examples of water-source shares of equipped area where reported by GMIA:

| BCU | Approx equipped ha | Estimated surface-water share of equipped area |
|---|---:|---:|
| NGER_MLI (Niger Basin, Mali) | 233186 | 99.58% |
| NGER_NER (Niger Basin, Niger) | 66708 | 98.13% |
| VOLT_GHA (Volta Basin, Ghana) | 23606 | 77.63% |
| ZAMB_ZMB (Zambezi Basin, Zambia) | 145978 | 95.53% |

**Strong caveats**: GMIA surface water may originate from a local stream, canal or reservoir, not necessarily the transboundary mainstem. Percentages for water-source rely on coarser statistical units mapped to fine pixels; FAO cautions that pixel-scale accuracy is poor. The source map is around **2005**, with no meaningful year-to-year variation. Absolute figures above are not field-level observations, and source-water percentages are *conditional on equipped hectares*, not fractions of all farmland. Hydrological connectivity must be established separately before using these as measures of treaty exposure.

**QA episode**: first attempted run failed on missing embedded CRS in Arc/Info ASCII grid. FAO official documentation confirms geographic grid boundaries (-180..180°, -90..90°) with 5 arc-minute cells; script now explicitly assigns EPSG:4326 after asserting source bounds and shape. Successful rerun shows `status=COMPLETE` and no errors. Do not claim raster carries a CRS itself.

## Next empirical data steps

1. Use [MIRCA-OS v2](https://hydroshare.cuahsi.org/resource/e4582ca0042148338bb5e0148b749ed6/) or specific historical version pinned by checksum for Maize/Sorghum/Rice crop-specific irrigated growing areas; note global v2 resource >10 GB and some subnational inputs are modeled, not direct measurements. Do NOT directly merge crop × cell as independent source observations.
2. Crop × district growing area masks overlain with BCU and known hydrological canal/reservoir locations. Predeclare likely-surface-water versus demonstrated-transboundary-river connectivity; no false precision.
3. CHIRPS v3 monthly final 1981–2024/2025 data (0.05°); use actual crop growing windows and consistent climatology. `mm/month` must not be confused with `mm/day`, river runoff or `m³/s`. First create stable within-district crop-season weather anomalies, then upstream runoff measures.
4. Validate runoff/discharge with licensed GRDC or national observed hydrometric data where access permitted. Original restricted gauge records are not to be publicly committed.
5. Revisit prevalence and variance of transboundary river-dependent agriculture *before* specifying main institutional interaction econometrics.

## User / assistant work division

Assistant: source auditing, code, downloads, reproducible quantitative and GIS calculations, identifying issues, scientific literature/source cards, draft manuscripts/visuals.

Researcher: agree scope and assumptions with supervisor, verify theoretical interpretation and original hydrologic mechanisms, obtain restricted station series under personal license if necessary, discuss contested document interpretation, make scientific judgments and accept responsibility for final thesis text and claims.
