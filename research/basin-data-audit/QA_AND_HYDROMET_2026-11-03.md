# Data QA + hydrometeorological pilot | 2026-11-03

This is a **real computation** with pinned public source files, not synthetic observations. This report distinguishes sample counts, validation checks, and scientific limitations. Not a regression or a drought index.

## Independently verified source inputs

- [HarvestStat Africa v1.2 CSV and GPKG](https://doi.org/10.5061/dryad.vq83bk42w); see [QA log including SHA-256](results/qa_v1/qa_provenance.json).
- [OSU TFDD 2024 BCU shapefile](https://transboundarywaters.ceoas.oregonstate.edu/spatial-datasets), verified SHA-256.
- HarvestStat v1.2 codebook: area **ha**, production **metric tonnes**, yield **metric tonnes per hectare**.
- Separate [code for independent QA](scripts/independent_qa.py).

## Confirmed numeric results

- HarvestStat 217487 rows, 33 countries; 818 unique TFDD BCU IDs.
- 198014 original-crop observations with positive production/area/yield, qc_flag=0. **Yield is mechanically equal to production/area**, at max relative difference 7.64e-13. Never describe these as three independent measurements.
- 1981–2024 Maize/Sorghum/Rice source records: 55719; after QC 51547; with >=80% same-country BCU admin intersection 35353.
- Independent crosswalk recomputation using **shapely direct intersections** (vs prior geopandas overlay): **695 identical admin polygons** meeting the >=80% criterion, 0 identifier differences.
- Summed BCU overlap never exceeds 1.01 of district area; max is 1.000000000298 (floating point noise).
- Independent re-aggregation of stored season-specific tables: **40 qualifying BCU**, **17 basins** with at least one adequate seasonal crop series; **9 basins**, **95 pair × crop combinations** with overlapping cross-country calendars. Those are not independent institutional observations.
- Threshold sensitivity:
  - 70% => 741 districts and 143022 filtered rows (all crops)
  - 80% => 695 districts and 134300 filtered rows
  - 90% => 640 districts and 122839 filtered rows
  - 95% => 601 districts and 114086 filtered rows

## Anomalies found (none concealed)

1. BCU identifier suffix differs from official CCODE for **three special multi-territory units**: `INDU_CHN/IND_1`, `NILE_EGY/SDN_1`, `GANG_CHN/IND_1`. Stored [list](results/qa_v1/bcu_suffix_country_mismatches.csv). **Zero** administrative polygons passing 80% assigned to these IDs; we match source `CCODE`, not suffix.
2. In original HarvestStat, **13331 district × crop × harvest-year keys** have multiple rows representing seasons/production systems (30144 source rows). Source `fnid × product × harvest_year × season_name × crop_production_system` is unique. **Never sum/average these as though independent annual yield replicates**. Cross-border crop year overlap is **not** season comparability.
3. Earlier provenance used ambiguous wording "geodesic-style equal-area" for EPSG:6933. It is an **equal-area map projection**, not an explicit geodesic area calculation. Numeric overlap independently matches.
4. A clean QC flag is not independent measurement validation. Errors in area or production are mechanically present in yield.
5. Source year range including 2026 is present as data metadata; not a guarantee the year is a complete annual sample.
6. None of these QA passes verifies historic administrative boundaries, crop locations within districts, or institutional implementation.

## New verified hydro-meteorological dataset: CHIRPS v3 monthly four-month pilot

- [Official CHIRPS v3](https://www.chc.ucsb.edu/data/chirps3), [monthly Africa final TIFF directory](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/), [data DOI](https://doi.org/10.15780/G2JQ0P).
- Exact downloaded months: January and August **1985**, January and August **2010** (four source files, SHA-256 values archived).
- Observed source raster: **1500 × 1600 pixels**, CRS EPSG:4326, resolution **0.05°**, Africa domain longitudes -20..55°, latitudes -40..40°.
- Five selected basins (Niger, Lake Chad, Volta, Nile, Zambezi): **47 unique TFDD BCU**, **188 BCU-month intersections**, all with positive numbers of valid rainfall pixels, unit **mm/month**. No missing data in this pilot extract.
- Method: mask raster by polygon (pixel-centre rule), weight retained gridded cell values approximately by pixel area (cos latitude), exclude nonfinite/negative raster values. **Not full fractional pixel intersection**, not crop area, not upstream contributing catchment. Thus a reproducible raster QC and BCU-level local rainfall illustration, not the final hydrological exposure.
- [Source SHA and raster metadata](results/hydromet_pilot/hydromet_provenance.json), [188 observed values](results/hydromet_pilot/chirps_v3_bcu_four_months.csv), [Python processing script](scripts/chirps_v3_pilot.py).

Some **real** example grid estimates, mm/month:

| BCU | Jan 1985 | Aug 1985 | Jan 2010 | Aug 2010 |
|---|---:|---:|---:|---:|
| Niger (NGER_NER) | 0.02 | 77.14 | 0.01 | 105.42 |
| Volta (VOLT_BFA) | 0.02 | 213.93 | 0.16 | 279.87 |
| Zambezi (ZAMB_ZMB) | 242.47 | 0.15 | 204.56 | 0.17 |
| Nile (NILE_ETH) | 8.20 | 305.48 | 11.22 | 334.82 |
| Lake Chad (LKCH_TCD) | 0.02 | 83.15 | 0.01 | 108.45 |

Those months deliberately sample seasonal contrasts, **not** representative drought extremes; a 4-month extract cannot define anomalies/Q90, and BCU-level rainfall alone does not measure river flow.

## Hydromet data decisions and safeguards

[Source registry with raw physical units and use status](hydromet/hydromet_sources_v1.csv).

1. CHIRPS3 monthly final precipitation will be a **local rainfall control and basic hydroclimatic exposure**. Expand to long time series only after confirming target crops/planting-harvest windows and target geographic units. Monthly total is mm/month, not mm/day or m3/s.
2. ERA5-Land monthly averaged stream `moda` hydrological accumulations are **m water equivalent/day**; monthly water depth in **mm/month** requires multiplying by (1000 	imes mathrm{days_in_month}). Do not apply this conversion to hourly or `mnth` products without verifying the stream; ECMWF official [documentation](https://confluence.ecmwf.int/spaces/CKB/pages/140385202/ERA5-Land+data+documentation).
3. GloFAS v5 reanalysis is **daily discharge in m³/s**, but it assumes 1486 active reservoirs as of early 2026 throughout historical simulations. It cannot represent actual time-varying historic reservoir infrastructure; official [documentation](https://confluence.ecmwf.int/spaces/CEMS/pages/690294321/GloFAS+v5+reanalysis).
4. GRDC is best for **in situ validation** where stations are available, with station-specific regulatory metadata; original observations are third-party-restricted and must not be published to GitHub. Official [portal](https://grdc.bafg.de/data/data_portal/).
5. For causal interpretation, **locally averaged rainfall is not upstream naturalised river supply**. Upstream catchments must first be delineated from river routing and irrigation withdrawals, and river/crop season temporal alignment verified.
6. CHIRPS v3 daily estimates can be disaggregated with ERA5 or IMERG; for basic monthly totals use CHIRPS monthly source directly without introducing daily timing modelling.

## Current scientific status

**Verified**: numerical integrity of historical source inventories and primary crop/GIS joins, tested geographic threshold sensitivity, reproducible CHIRPS monthly BCU pipeline.
**Not yet verified**: true agricultural spatial location inside district; exposure to *transboundary* river irrigation; local/upstream climate history for full period; river gauge validation; exact enforcement/implementation of governance mechanisms; statistical power; econometrics or causal effects.

**Next milestone**: choose target district × crop × planting-harvest window from actual HarvestStat series (no time leakage); generate full monthly CHIRPS v3 climate exposure with crop-region or upstream region masks; then obtain in situ GRDC station metadata for two pilot basins, and assess ERA5-Land runoff time series separately.
