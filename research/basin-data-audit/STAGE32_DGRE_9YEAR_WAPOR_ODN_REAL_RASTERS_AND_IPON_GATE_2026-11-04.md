# Этап 32 · реальные растры WaPOR ODN и 9-летняя гидрология Yaran / Sourou

**04.11.2026. Результат: GO для воспроизводимой георастровой обработки и описательной гидрологии; HOLD для Di intake и causal institutional effects.** Основание: проверенные исходные GeoTIFF FAO + официальные таблицы DGRE. Не принимать зону наличия продукта WaPOR за рисовую оросительную систему, а измерение запаса Yaran за расход на насосы Di.

## 1. Первые действительно скачанные спутниковые данные Office du Niger

Сохранены вычислительные скрипты и метаданные фактических **6 GeoTIFF FAO WaPOR v3 Level 3 Office du Niger, annual AETI 2018–2023**:
- [Официальный исходный URL pattern](https://gismgr.fao.org/DATA/WAPOR-3/MOSAICSET/L3-AETI-A/) => \`WAPOR-3.L3-AETI-A.ODN.{YEAR}.tif\`, также индивидуальные JSON.
- [Полный download/SHA256/Grid audit](results/stage32_wapor_odon_real_rasters/stage32_wapor_ODN_original_download_and_QA.json) PASS без исключений.
- GeoTIFF CRS **EPSG:32629**, размер **2161×4430 пикселей**, **20 м × 20 м**, NODATA −9999. Все 6 геометрических сеток и их valid mask абсолютно одинаковы; **2 462 098 действительных пикселей**, 400 м² каждый, **984,8392 км² площади действительной области продукта**.
- TIFF internal scale \`0.1\`, независимая [спецификация Digital Earth Africa / WaPOR](https://docs.digitalearthafrica.org/en/latest/data_specs/WaPOR_specs.html) подтверждает единицу продукта **мм/год**. Масштаб применён ПОСЛЕ чтения исходных integer TIFF, никаких произвольных коэффициентов.
- Все 6 оригинальных TIFF имеют отдельный SHA256 (и JSON metadata), указанные в [inventory](results/stage32_wapor_odon_real_rasters/wapor3_ODN_2018_2023_L3_AETI_A_REAL_original_raster_inventory.csv). Бинарные источники не коммитились в GitHub, хранились на временном runner.
- [Six-year fully reproducible means](results/stage32_wapor_odon_real_rasters/wapor3_ODN_common_valid_raster_footprint_2018_2023.csv):

| Year | RAW mean | scaled AETI mm/year |
|---|---:|---:|
|2018|8639.8672567|**863.9867**|
|2019|9677.2720773|**967.7272**|
|2020|10098.0055006|**1009.8006**|
|2021|10575.5648341|**1057.5565**|
|2022|10971.9522119|**1097.1952**|
|2023|12247.8757076|**1224.7876**|

Изменение среднего 2018–2023 **+41,760%**, 2022–2023 **+11,629%**. Имеем шесть временных точек **одной** территории; 2.46 млн пикселей пространственно коррелированы, их нельзя рассматривать как 2.46 млн независимых институциональных наблюдений.

**Независимый source confirmation**: два TIFF 2022 и 2023 повторно загружены и сверены по ранее сохранённым SHA256, отдельно вычислены pixel differences через полную маску. [QA independent](results/stage32_wapor_odon_real_rasters/wapor3_ODN_2022_2023_INDEPENDENT_pixel_change_QA.json) 12/12 PASS: 2022 **1097,1952 мм**, 2023 **1224,7876 мм**, **+127,5923 мм**, медиана **+116 мм**. **81,3827%** пикселей увеличились, **18,5954%** уменьшились, **0,02185%** не изменились. Изменение на уровне каждого пикселя имеет 10-й перцентиль −57,3 и 90-й +332,6 мм/год. Нет претензий на crop mask, irrigation delivery, Niger abstraction или статистическую причинность.

**ВАЖНО:** найденное уведомление FAO о переиздании L3 в июле 2024 затрагивает уровневые переменные, а уведомление от **21.03.2025 касается ИМЕННО NPP и AGBP**, а не AETI. Формулировка «исправленный WaPOR AETI 2025» была бы ошибочной. Источник: [FAO Data Access / correction notices](https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data-access/en).

## 2. 2015–2023: исходные официальные гидрологические таблицы DGRE по Sourou Yaran

Из прямых PDF первоисточников восстановлены годовые запасы водохранилища Yaran, **не observed water release и не Di irrigation intake**. Формат: 1 января, максимум года, минимум года, 31 декабря, число дней перелива:

| year | Jan1 | max | min | Dec31 | spill days |
|---|---:|---:|---:|---:|---:|
|2015|431.58|763.92|64.62|528.43|76|
|2016|522.79|650.53|99.50|440.35|40|
|2017|432|511|111|333|0|
|2018|327|808|64|618|96|
|2019|618|618|127|511|22|
|2020|506|802|117|613|107|
|2021|608|721|**105**|580|102|
|2022|511|884|105|717|117|
|2023|717|726|143|668|126|

Все volumes млн м³. [Source table and printed pages](results/stage32_sourou_real_hydrology/DGRE_Yaran_2015_2023_nine_annual_first_report_source_tables.csv). [QA](results/stage32_sourou_real_hydrology/stage32_DGRE_9year_SOURCE_CHECK.json) **26/26 PASS** (в смысле source-consistency checks) и 9-year descriptive province rice overlap; source dates individually available. [script](scripts/stage32_dgre_9year_manual_table_source_gate.py).

### Исправление ошибки из предыдущего этапа

В официальном [DGRE годовом отчёте 2021](https://dgre.gov.bf/documents/19/Synth%C3%A8se_annuelle_ressources_2021.pdf), **печатная с. 66, таблица 1-9 непосредственно в теле документа**, для 2020: minimum **117** (10 июля 2020), для 2021: minimum **105** (21 июня 2021). При этом оглавление того же PDF по ошибке нумерует Sourou как Table 1-13; это печатное внутреннее несоответствие метаданных, но сама таблица в тексте однозначна. В более позднем [отчёте DGRE за 2022](https://dgre.gov.bf/documents/20/DOC_SYNT_2022_VF.pdf) ретроспективно строка 2021 переиспользует **117** и дату **10 июля 2020**, 2022 минимум указан как 105 и датой 21 июня 2021, что похоже на сдвиг копирования столбцов. Прежний Stage31 использовал 117 как 2021; **текущее исправление: 2021 = 105 по contemporaneous annual report**, а 117 обязательно остаётся как conflicting retrospective published alternate. Это НЕ новый физический эффект и не автоматическое «исправление» исходного PDF.

Не устранены прочие cross-report chronology errors:
- **31 Dec 2021 580** vs **1 Jan 2022 ~511.462**, difference −68.538 млн м³ (или −69 по annual Jan1 511). 
- **31 Dec 2023 668** vs **1 Jan 2024 585.339**, difference −82.661 млн м³.
- **31 Dec 2022 717** vs **1 Jan 2023 ~716.566**, difference −0.434 (within rounding).
- 2015→2016 -5.64, 2016→2017 -8.35, 2017→2018 -6, 2019→2020 -5, 2020→2021 -5; dates, reservoir conservation, revised curves not independent daily confirmed. No year-break values may be described as pump withdrawals or 1-day actual measured river discharge.

[8 year-boundary audit CSV](results/stage32_sourou_real_hydrology/DGRE_Yaran_all_8_2015_2023_report_boundary_quality_flags.csv) · [9-year descriptive join to province rice, with no-regression flag](results/stage32_sourou_real_hydrology/Yaran_2015_2023_NINE_year_reservoir_vs_province_rice_DESCRIPTIVE_NOT_REGRESSION.csv).

## 3. Di: accurate as-built pump geography remains unverified

[Mathematica MCC final evaluation 2021](https://www.mathematica.org/-/media/publications/pdfs/international/2021/burkina_faso_adp_final_report.pdf) describes **seven operational 2014 Di pump sectors** for **2246 hectares**, AMVS river→pumps and WUA pumps→farms. [SCET engineering 2010–2013](https://www.scet-tunisie.com/en/projects/development-2500-ha-irrigated-areas-sourou-valley) describes a **2500ha project / 8 pumps of design capacity 500–1000 L/s / explicit GIS product**. As-built vs design scope differs. We cannot infer exact seven pump coordinates from a plan, name or Di town center. 2014 newspaper report independently describes operational handover of one of seven pumping stations [Sidwaya](https://www.sidwaya.info/2014/05/30/perimetre-irrigue-de-di/).

A bounded [OpenStreetMap Overpass preliminary search](results/stage32_sourou_real_hydrology/stage32_OSM_Di_Pump_and_Canal_candidate_discovery_QA.json) within 22km of approximate Di commune reference 13.169° N, −3.415° E failed **due to Overpass network access**: timeout on kumi.systems and HTTP 502 on overpass-api.de. **No verified pump position was obtained** and absence is not proof pumps are unmapped or nonexistent. Do not substitute seven invented points or claim GPS.

**Hydrology:** DGRE Yaran is reservoir stage gauge, not Di irrigation pump gauge, and upstream Mouhoun / Léry gate seasonal reversal and regulation mean \`upstream flow\` cannot be assumed from a nearby arbitrary hydropost.

**Next defensible physical request:** primary as-built map of 7 Di pumping sites (WGS84 coordinates) and 7 command-area polygons; operation logs (m3, pump hours, flow rate), Lery valve flows and rating curves (2015–23), verified origin of scheme-specific rice yield or same scheme plot records. Do not declare 'scheme treatment' or formal institutional effect before these gates.

## 4. New official corroborating lead: IPON for Office du Niger

[FAO Application Catalogue](https://www.fao.org/in-action/remote-sensing-for-water-productivity/applications-and-uses/applications-catalogue/product-detail/ipon-tool-irrigation-performance-of-office-du-niger38544db9-cf19-41d5-8c7a-623a8d32139c/en) confirms **IPON (Irrigation Performante de l'Office du Niger)**, codesigned with **IWMI and Office du Niger** and publicly handed over in September 2025. Its 11 indicators **combine WaPOR remote sensing with *in situ measurements of irrigation water consumption* by zone/casier**. There are now official operational datasets at a common scheme-level physical unit that may solve source-support mismatch if raw tables can be accessed.

[FAO links to public beta Tableau IPON](https://public.tableau.com/app/profile/water.eleaf/viz/IWMI_IPADT_Dashboard_20240320/Overview). The dynamic JS Tableau table has **NOT** yet been extracted; don't assume raw in-situ data available to download just because UI visible. This is a highly relevant next task: recover exact IPON sources, units, season, spatial zone/casier IDs, water allocation vs consumptive use and licence. Quantify no IPON indicator until real original values independently retrieved.

## 5. Updated scientific decision (Go/No-Go)

- Sourou: nine official *storage* years are now available, but **NO** daily/seasonal gauge flow and **NO** Di pump water m3 or GPS asbuilt; original technical linkage **INCOMPLETE**.
- WaPOR ODN: true multi-year 20m AETI imagery and numeric QA **PASS**. But valid product extent **NOT** proven scheme field crop mask, 6 yrs **NOT** causal institutional panel, IPON data **NOT** extracted.
- The next empirical contribution can be **geospatial irrigation adequacy / productivity at verified ODN casier** if FAO/IPON zone geometry and water supplied are accessible. Institutional interpretation must remain separate and source-documented; local Office du Niger management is NOT automatically a treaty effect of Niger Basin Authority.
- No unverified dates, GPS locations, scheme outcomes, field-level water releases or underlying formulas are invented.

Code and data are public reproducible in this stage32 branch, original GeoTIFF binaries stored only transiently in GitHub Actions.
