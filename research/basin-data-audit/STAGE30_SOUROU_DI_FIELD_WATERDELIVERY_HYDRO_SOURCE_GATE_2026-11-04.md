# Этап 30 · Sourou–Léry → Di/Niassan: физическая водоподача, реальный гидрорежим, сельхозисходы и институты
**4 ноября 2026 · статус: scheme hydraulic chain DOCUMENTED; exact pump→parcel polygons OPEN; hydro source conflict STOP; institutional release effect NOT IDENTIFIED.**

## 0. Главный научный итог (Go/No-Go)

У **нового Di perimeter (MCC 2014) на восточном берегу Суру** первично задокументирована физическая цепочка **Sourou/regulated storage → river-to-primary canals (AMVS) → 7 electrically powered pumping stations (S1 S2 C1 C2 C3 C4 North) → canals and turn-based valves (WUA) → farmers' plots**. Это **не** свидетельство того, что все 7 насосов имеют открытые WGS84 координаты или что имеются измеренные deliveries m³/plot и реальные crop-cut coordinates. Нельзя закрывать физический G3/G4/G5 лишь за счёт инженерной схемы.

Первичный источник: [Mathematica 2021 final MCC evaluation](https://www.mathematica.org/-/media/publications/pdfs/international/2021/burkina_faso_adp_final_report.pdf), ch. IV printed pp. 63–66, Figures IV.1/IV.3 и описания AMVS/WUA. [MCC summary](https://www.mcc.gov/resources/doc/evalbrief-040221-bfa-diverse-agriculture/) подтверждает functionality pumps and canals but also defective drains, valves, fee bottlenecks and varying water access. Внутри MCC evaluation это **система локального управления**, не CTGS international gate-operations data.

**Чёткое разделение:**
1. Di NEW MCC ≈2246 ha, 7 sectors / 7 pumps, physically connected supply, cross-section by WUA; project 2009–14, observed 2019–20.
2. Existing Niassan projects = отдельные старые периметры, лишь получали technical assistance и модернизацию; нельзя автоматически относить насосы Di к Niassan.
3. Older Di pivot irrigation = отдельная историческая схема, не тот же учёт MCC new perimeter.
4. [SCET Tunisie project](https://www.scet-tunisie.com/projets/amenagement-de-2500-ha-de-perimetres-irrigues-dans-la-vallee-du-sourou): engineering DESIGN about **2500 ha / 8 stations / 110 km channels**. Это отличается от 2246 ha / seven stations по отчёту финальной оценки. **Не объединять** эти цифры; дизайн и as-built могут иметь разные периметры, точный overlay не опубликован.
5. [2025 OpenEdition geographic paper](https://journals.openedition.org/tem/12997): Figure 3 (план районов 2014 г.) различает Di/Niassan blocks, но исходного GeoJSON/cadastral GIS для их 2020-2023 площадей в проверенном открытом доступе нет. Иллюстрация карты НЕ является официальным georeferenced layer; не оцифровывать как survey-grade polygon без масштаба и контрольных точек.

[16 documented links with evidence grade and blockers](results/stage30_sourou_di_physical_water/sourou_di_water_links_evidence_registry_stage30.csv). GIS: [только официально координатированный Yaran station](results/stage30_sourou_di_physical_water/Yaran_Official_Gauge_NOT_Lery_Gate_NOT_Di_Intake.geojson) — NO invented Di pumps or Lery gates.

## 1. Гидрология: природный поток ≠ регулируемый запас ≠ водоподача

[DGRE Burkina Faso 2023 annual hydrology, edited 2024](https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf) hydrology printed pp.46–49:
- Станция **Yaran**, IRD **1202702205**, опубликованные географические координаты **12°58′48.8″ N, 03°26′49.4″ W** = **(lat 12.9802222222; lon −3.4470555556)**. Это уровни воды и расчётный запас ретенции, **не станция измерения объёма, поступающего к семи насосам Di**.
- При естественном режиме Sourou был *affluent/défluent* Mouhoun с сезонным разворотом. С 1976 построен первый порог, а с 1984 есть отвод Mouhoun в Sourou upstream of Lery gate и управляемое деление между storage Sourou и downstream Mouhoun. Это не обычный стационарный headwater routing; у любого «upstream hydropost» нужно проверить направление, год строительства и operator releases.
- DGRE сообщает, что downstream users **должны получать минимальные 3–4 м³/с** при маловодье. Это **нормативно/эксплуатационно заявленная цель**, НЕ измеренный ряд и **НЕ подтверждённое положение CTGS transboundary release/quota**. Минимум downstream Mouhoun ≠ irrigation offtake Di.

**Доступные проверенные цифровые таблицы, исходно прямо прочитанные из PDF страниц, не OCR/рисунок**:
1. [DGRE 2023 Table 12](results/stage30_sourou_di_physical_water/DGRE_Yaran_2022_2023_annual_storage_SOURCE_TRANSCRIPTION.csv), printed p49:
   - 2022: storage Jan1 **511**; max **884** (Oct2); min **105** (Jun21); Dec31 **717** Mm³; spilling **117** days.
   - 2023: Jan1 **717**; max **726** (Oct2); min **143** (Jun21); Dec31 **668** Mm³; spilling **126** days.
   - DGRE reported percentages imply denominator **~608 Mm³**.
2. [DGRE January 2024 Table 16](results/stage30_sourou_di_physical_water/DGRE_Yaran_January_2022_2024_storage_SOURCE_TRANSCRIPTION.csv), printed p24:
   - 01 Jan / 31 Jan 2022 **511.462 / 393.329 Mm³**, net storage change **−118.133**;
   - 2023 **716.566 / 631.656**, net change **−84.910**;
   - 2024 **585.339 / 450.701**, net change **−134.638**.
   - The table uses capacity at PEN **603 Mm³** (independently reproduced the printed fill % within 0.01 pp).
   - Net storage decline is NOT river downstream discharge or irrigation pumping: inflow, releases, withdrawals, evaporation, seepage are not distinguished.

**Unresolved contradiction — DO NOT SPLICE DAILY DATA:**
- 2023 DGRE annual report Table 12 says **31 Dec 2023 storage 668 Mm³**. January 2024 bulletin Table 16 says **01 Jan 2024 storage 585.339 Mm³**. Neighboring dates differ by **−82.661 Mm³**; no measured operational reason, revised rating curve or correction bulletin verified. Compare 2022 Dec31 **717** with 2023 Jan1 **716.566**: difference **−0.434**, consistent with integer rounding. So 2023–2024 discontinuity cannot be dismissed as ordinary year-boundary alignment.
- Reference capacity **608 inferred from annual percentages versus 603 explicitly published by monthly bulletin**; 5 Mm³ difference. Do not compare fill percentages across PDFs or construct synthetic daily release 82.7Mm³.
- [Hydrological QA output](results/stage30_sourou_di_physical_water/stage30_water_source_drought_outcome_QA.json) **11/11 program checks PASS with critical source conflict recorded**. 'PASS' means conflicts detected and documented, NOT the data scientifically reconciled.

## 2. Агрорезультат 2015–2023: реальный 9-летний ряд, НЕ Di system outcome

Pinned original [HarvestStat Africa v1.2 CSV, commit 5b62fb5](https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/5b62fb5/public/hvstat_africa_data_v1.2.csv): **25 312 039 bytes**, SHA-256 `f659e121e315b9d8656699e4b16421ed3b313e4c8d09d15199452000836dbef9`, **217 487** original rows; independent source checksum PASS in GitHub Actions. [Source nine rice observations](results/stage30_sourou_di_physical_water/province_sourou_2015_2023_nine_irrigated_rice_source_verified.csv): FNID `BF2020A24606`, **Rice, Annual, Plaine/Bas-fond irrigated (PS)**, one row per year 2015–2023, QC0 all 9, all area, yield, production positive and `yield = production/area` exactly.

**Important spatial support:** these are *whole Sourou province* rice categories, not land surveyed at Di seven pumps or Niassan rehabilitation; cropping season recorded as `Annual`, actual field seasons not established. Even a precise map of Di does not allow automatic transfer of province yield to the scheme.

As a strictly NON-CAUSAL comparison [2022–2023 documented merged file](results/stage30_sourou_di_physical_water/Sourou_2022_2023_STORAGE_vs_PROVINCE_RICE_NO_FIELD_LINK.csv):

| Source variable | 2022 | 2023 | Change |
|---|---:|---:|---:|
| Provincially irrigated-category rice yield, t/ha | 5.468402 | 4.176699 | −23.621% |
| Provincial irrigated-category area, ha | 4769.02 | 2060.00 | −56.805% |
| Provincial production, t | 26078.92 | 8604.00 | −67.008% |
| Yaran annual storage minimum, Mm³ | 105 | 143 | **higher** in 2023 |
| Yaran 31 Dec storage, Mm³ | 717 | 668 | lower in 2023 |
| Spill days | 117 | 126 | more in 2023 |

**No inference that 2023 was drier for irrigation**. Observed seasonal low reservoir was HIGHER, year-end storage LOWER, spill days HIGHER. We have no actual plot-specific deliveries, electric hours, field plots, source crop calendar, or transboundary water-allocation decision. Covariates confounded, sample for reservoir table only 2 years.

**Major confounder**: [Ouandé et al. 2025 study at University Joseph Ki-Zerbo](https://progres.gov.bf/ujkz/publications/13577/details) finds insecurity and Covid significantly disrupt farm access, water turns, inputs and markets; these coincide with 2020+ outcome years. No numeric causal attribution made here.

## 3. Институты: три разных уровня, не смешивать

**(A) Local operating institution:** seven WUAs controlled valves/fees and farmer water turns for Di, while AMVS maintained river-to-pumping infrastructure. Reports describe actual routine operation and maintenance issues, e.g. late fees/electricity expenditure and deficient drainage. This is *observed/reported implementation of a local irrigation institution*, relevant for availability beyond raw hydrology.

**(B) National project/regulator control:** [MCA BF 2012 report](https://www.abcburkina.net/fr/nos-dossiers/vu-au-sud-vu-du-sud/868-455-droit-de-reponse-du-mca-bf) reports DGRE+AMVS meetings Jan/Mar/Apr 2012 and planned/announced progressive Lery gate opening associated with infrastructure works and water provision. This is first-hand PROJECT ACCOUNT, not verified raw daily gate opening volume; 2012 is not CTGS treaty's implementation date.

**(C) International coordination:** [IIED CTGS legal mandate](https://www.iied.org/fr/g04226) and [CTC joint technical committee document](https://www.iied.org/fr/g04221) formalize cross-border coordination, joint technical contact and stakeholders. Documented meetings in 2013 and 2015 (per stage v1.9), but reviewed CTGS mandate includes basin cooperation and advice, **no source proving it instructed the Lery operators to modify valve or Di irrigation allocations in any given agricultural year**. This does not mean proof of no such decisions: operational evidence remains **UNKNOWN**.

The 3–4 m³/s downstream minimum mentioned by DGRE is **not** established as CTGS international allocation quota or actually fulfilled. Do NOT create `treaty_after_2013=1` and regress on 2015–2023 category rice.

## 4. Evidence gates as of Stage30

| Evidence gate | What can be claimed | Status |
|---|---|---|
| G0 river/reservoir source in Di | Official/commissioned published infrastructure source | **PASS DOCUMENTARY** |
| G1 geography of broad region | Di on east Sourou; Yaran exact official gauge coordinate; MCC seven sectors map | **PASS BROAD, not 7-pump GIS** |
| G2 irrigated agriculture outcome | 9-year provincial series, 2015–2023 | **PASS province; NO Di scheme** |
| G3 actual intake→field polygons | Seven sector pumps, delivery mechanism documented; **not** coordinates or command-area polygons | **PARTIAL narrative; GIS NO-GO** |
| G4 hydro input at intake | DGRE Yaran reservoir storage, not pump flows; cross-report storage conflict | **NO-GO** |
| G5 actual international applied release | CTGS creation/meetings; no verified effect on gate openings or Di WUA | **NO-GO** |
| G6 crop-specific station/timing | No field-linked pumping logs / hydropost intake calibrated | **NO-GO** |

## 5. Next exact data request (must be verifiable, no artificially invented GIS)

1. **AMVS / MCA-BF / engineering SCET**: 7 postconstruction Di pumps and 7 *as-built* sector polygons, intake and river/canal connection points, canal directions, operating hours/electricity consumption and seasonal delivery in 2015–2023; explicitly confirm differences with SCET's preliminary eight/2500ha design, and Niassan distinct pumps/polygons. Need validated public data or written provenance; no confidential farmer identities.
2. **DGRE Yaran/Léry**: daily/weekly 2015–2023 reservoir stage→volume conversion tables (rating/hypsometry for 603 vs 608), daily upstream Mouhoun diversion, gate setting, downstream releases, actual 31/12/2023 vs 01/01/2024 disagreement, and observed releases vs DGRE-stated 3–4m³/s minimum.
3. **CTGS / CTC / Basin of Mouhoun**: source-signed 2013-23 minutes / specific water sharing and operational notices, how recommendations were communicated to DGRE and AMVS, any documented intervention on Lery valve operation or distribution, distinguish procedures from actual compliance.
4. **Agricultural outcomes:** true irrigation scheme-specific crop×year×season area, production and yield OR reliable satellite plot outcomes (clearly remote-sensing proxies). Without 1 and 4, no province-to-pump causal fit. 2019/20 MCC crop-cut microdata access through ICPSR does not imply long panel.
5. **Fallback:** if geographic/operational evidence impossible, use comparative process tracing of local WUA vs cross-border CTGS and descriptive environmental hydrology; do not claim causal treaty reduction of food insecurity.

**Scientific STOP:** do not regress Yaran storage vs two province rice years, do not interpret 2023 output collapse as drought, do not replace missing water intakes with reservoir gauge coordinates. New physics and operations corroboration is necessary before 'hydrological resilience' effects.

## 6. Reproducibility and independently checked contradictions

- [Source/checksum/indicator script](scripts/stage30_sourou_water_storage_and_rice_source_QA.py)
- [Published 16-item evidence registry](results/stage30_sourou_di_physical_water/sourou_di_water_links_evidence_registry_stage30.csv)
- [Only verified map point, Yaran not Di intake](results/stage30_sourou_di_physical_water/Yaran_Official_Gauge_NOT_Lery_Gate_NOT_Di_Intake.geojson)
- [Computed QA](results/stage30_sourou_di_physical_water/stage30_water_source_drought_outcome_QA.json)
- Original bibliography: all links in each table. Official DGRE has *both* table screenshots examined to cross-check the numbers; one source discrepancy remains openly unresolved.

**Decision:** Stage30 SOURCE+PHYSICAL RECONNAISSANCE COMPLETE; full stage30 FIELD×FLOW×OUTCOME×INSTITUTION linkage **INCOMPLETE, blocked**. NEXT = obtain scheme-specific primary operational evidence, not next multiple weather regressions.
