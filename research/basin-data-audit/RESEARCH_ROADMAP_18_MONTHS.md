> **НАУЧНАЯ РЕВИЗИЯ 03.11.2026.** Настоящий файл — ранний исторический план. После внешней рецензии и повторного пересчёта актуальны [Design Decision Memo](design/DESIGN_DECISION_MEMO_v1.md), [Gate A (330 → 103 страты)](design/GATE_A_DATA_READOUT_2026-11-03.md), [Codebook институтов](design/INSTITUTION_CODEBOOK_v1.md), [DAG и Pre-Analysis](design/PRE_ANALYSIS_AND_DAG_v1.md), [обоснованные gates](design/DECISION_GATES_AND_SPRINT_v1.md). Нельзя считать `9 бассейнов с общими годами` подтверждённой сезонной межстрановой панелью или заранее обещать DiD. Юридически действовавшие и внедрённые институты пока не кодированы. Для текущих выводов пользоваться документами v1.1.

> **DATA-IDENTIFICATION GATE — 03.11.2026:** В предыдущем screen 28 районов с длинными рядами были смешаны категории `All`, `Rainfed` и `Irrigated` по рису. Повторная проверка типов исходов установила, что среди 47 районов с модельной значимой орошаемой площадью в MIRCA-OS v2 лишь **4** имеют отдельный ряд орошаемого риса не короче 8 лет; все находятся в Буркина-Фасо. Из этих данных нельзя построить доказательную многострановую модель причинного влияния межгосударственного института. Нужны дополнительные схемно-специфичные outcomes (включая WaPOR/IPON), либо переход к смешанным районным исходам с корректным описанием экспозиции и ограничений. [Полный пересчёт](RICE_WATER_SOURCE_LOGIC_AUDIT_2026-11-03.md).

# Dissertation research roadmap | Nov 2026–May 2028

## Mission
Understand whether and how documented cross-border water governance rules modify agricultural sensitivity to upstream hydrological drought; give basin organisations actionable, uncertainty-aware evidence.

## Research products
1. Versioned open, documented administrative/basin agricultural panel with provenance and QC.
2. In-situ-validated hydroclimatic drought metrics, avoiding downstream-regulated discharge as automatically exogenous.
3. Source-quoted and historically dated registry of concrete water management procedures.
4. Reproducible transparent association models; causal language only if quasi-experimental conditions met.
5. One deep Asian external-validity study (Mekong first-choice; India only with appropriate transboundary identification).
6. Short policy brief (2–4 pages) and optional interactive atlas showing uncertainty.

## Month and decision gates
| When | Primary work | Evidence gate |
|---|---|---|
| Nov 2026 – Jan 2027 | HarvestStat v1.2 × TFDD audited; crop/season-specific panel year count, non-random missingness, province overlap threshold checks | >=3 multi-country basins with usable repeated harvest years? If no, pivot to specific case |
| Feb – Apr 2027 | Official historically dated basin rules; screen ~8 candidate basins; station availability list GRDC/MRC; compare available crop-country years | >=2 institutional rule dimensions with documentary dates or pivot to governance case study |
| May – Jul 2027 | Hydrology: spatial upstream runoff/precip seasonal drought + real station validation; crop phenology, irrigation river connectivity | Retain natural shock only if station/raster concordance and treatment timing adequate |
| Aug – Oct 2027 | Fit transparent descriptive and heterogeneity models, use uncertainty at institutional clustering level, placebo/robustness | Reject causal framing absent credible identification |
| Nov 2027 – Jan 2028 | Asian transfer test: Mekong Vietnam provincial rice & station data; check intercountry harmonization | Only add full second comparison if harmonization and institutions genuinely comparable |
| Feb – May 2028 | Thesis, replication repository, concise basin commission policy brief, seminar draft/review | Final documented evidence tables, not just decorative atlas |

## Weekly rhythm (30–40min sessions)
Mon paper-method card; Tue source/provenance audit; Wed code/QC review; Thu institution/event coding; Fri model or map; weekend 20min summarize, log decisions. One self-contained milestone per fortnight.

## Status 2026-11-03
COMPLETED: official HarvestStat v1.2 and TFDD file provenance; counts of QC/positive records; conservative admin-to-BCU geographic crosswalk. See [report](REPORT_2026-11-03.md).
STARTED: [institution registry](institutions/primary_official_registry_v0.csv) citing official OMVS, NBA, MRC sources.
NOT YET DONE: source-and-year-verified final crop panel; mapped irrigated crop locations; hydroclimate time series; station validation; institutional implementation checks; statistical power analysis; Asian agricultural harmonization; regressions. No causal evidence claimed.
