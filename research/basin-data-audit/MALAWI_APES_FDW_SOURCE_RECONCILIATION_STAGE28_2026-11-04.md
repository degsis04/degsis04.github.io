# Этап 28 — источниковая сверка APES → FDW → HarvestStat Малави
**4 ноября 2026. Статус: source-audit PASS with substantial scientific limits. B08 ЧАСТИЧНО, а НЕ полностью готово.**

## 1. Что считалось источником, а что — производным результатом
- Исходный официальный [релиз HarvestStat Africa v1.2](https://github.com/HarvestStat/HarvestStat-Africa/releases/tag/v1.2) содержит вложенный `fdw_raw_data_v1.2.zip`: 54 698 516 байт, SHA-256 `6e8128f8854f38172aea24583e537395242abafab4382441b3d53805c44b452b`, совпал с независимыми метаданными оригинального Dryad [10.5061/dryad.vq83bk42w](https://doi.org/10.5061/dryad.vq83bk42w). Наружный релиз: 94 024 434 байта, SHA-256 `2ff71261f39b207c0b9d5becaa9efce891cba035d80e0df0acadc7b9b190218f`; CRC обоих архивов пройден.
- Неизменённый файл `adm_crop_data_raw_MW.csv`: **51 892 исходных FDW строк, 65 полей**, в т.ч. `fnid`, `period_date`, `season_year`, `crop_production_system`, `source_organization`, `source_document`, `publication_name`, `indicator`, `status`. Это исходный **FDW**, а не оригинальные районные ведомости Министерства APES.
- В FDW Malawi all crops **41 763** записей с `source_document=Annual Production Estimate Survey`, **8 214** FEWS NET Agro-Maps, **1 785** FAO Summary, **118** альтернативные APES; это записи индикаторов, **не** уникальные обследования.
- Для maize grain (white) 5 200 индикаторных строк: 1 724 Area Planted, 1 724 Quantity Produced, 1 724 Yield, 28 Area Harvested. Эти показатели не подменяются друг другом.
- Тестовая группа HarvestStat v1.2: 915 maize строк / 23 FNID, из них 812 `Main/Rainfed (PS)` (1983–2020) и 103 `Annual/All (PS)` (2018–2024). Это аналитически отобранные записи, не все 1 099 maize строки первоначальной базы.

## 2. Прямое сопоставление всех 915 с raw FDW

Первая, предельно строгая сверка `same current FNID + calendar harvest_year + season_name + crop_production_system`: **161/915** строк с найденными raw-парами, все **161** совпадают по `Area Planted` и `Quantity Produced`, **142** по отдельному raw индикатору Yield. Ещё **19** (2024 `Annual/All`) имеют в FDW отсутствующий непосредственно измеренный Yield, однако HarvestStat вычисляет `production/area`. Ни одной прямой `Area Harvested` пары не подтверждено на уровне этих 915 наблюдений.

Вторая, независимая по логике сопоставления сверка по `нормализованное имя района + регион + тот же год + тот же season_name + тот же crop_production_system`: **893/915** строк с raw-парой; **737/915** точно совпадают и по посевной площади, и по производству; **864/915** имеют совпавший исходный Yield; **718** совпадают по трём измерениям. В 732 случаях исходная районная запись имеет старый FNID; всего обнаружены генерации `MW1971A2, MW1998A2, MW2003A2, MW2018A2`. **Это ID/именная, а НЕ геометрическая валидация**.

Для Main/Rainfed отдельно: **812** HarvestStat, **790** FDW записи того же имени/года/системы, **634** площадь + производство совпали, **780** Yield совпал, **22** не имеют прямой однозначной местной строки. Последние **22**: **Neno 1985–2002 (18 лет)** и **Balaka 1984–1987 (4 года)**. До проверки физического преобразования их нельзя называть наблюдённым именно в нынешнем районе урожаем.

**Исторические несовпадения:** **146** записей Main/Rainfed имеют другие area/prod, но точно ту же yield; вычисленный независимым методом коэффициент `HS_area/FDW_Area_Planted` равен `HS_production/FDW_Quantity Produced`, максимальная разность между двумя коэффициентами **3.37e−12**. Ещё **10** записей Balaka 1988–1997 меняют урожайность: изменения не объясняются одним общим скалярным коэффициентом для района.

## 3. Найдено авторское исходное объяснение — не догадка

Первоисточники: [`CropData_MW_Profile.ipynb` на официальном commit 5b62fb5](https://github.com/HarvestStat/HarvestStat-Africa/blob/5b62fb5/notebook/CropData_MW_Profile.ipynb) и [`tools.py`](https://github.com/HarvestStat/HarvestStat-Africa/blob/5b62fb5/notebook/tools.py).

1. Малавийский ноутбук вызывает `FDW_PD_Sweeper(..., area_priority="Area Planted")`. В `tools.py` строки 421–430 основная `Area Planted` заполняется отсутствующей `Area Harvested`, затем технически переименовывается в `Area Harvested`. Это означает, что переменная **`area` преимущественно площадь посева**, даже если внутренний код/заголовки после отбора называют её harvested. Не путать с наблюдаемой площадью реально собранного урожая.
2. Данные старых административных сеток FEWS NET 1971, 1998 и 2003 переводятся к `MW2018A2` (2018) через `FDW_PD_CreateAdminLink`, `FDW_PD_RatioAdminLink` и `FDW_PD_ConnectAdminLink`. В `tools.py` строки 681–820 авторы используют **production-based (PBR)** или **cropland-based (CBR)** доли; масштабируют **площадь и производство одними коэффициентами** и суммируют полученные доли для целевых районов. Отсюда стабильная сохранённая урожайность у 146 масштабированных строк, и потенциальное её изменение при агрегировании нескольких исходных районов.
3. `crop_new = prod_new / area_new` показывает, что финальный Yield в HarvestStat является вычисленной относительной величиной **после** пространственного преобразования. Схемы `Main` и `Annual` сохраняются раздельно. Наименование `harvest_year` не доказывает наблюдаемую фактическую фенологию.
4. Последующие флаги QC в `Combine_CropData.ipynb` не возвращают исходные старые границы и не удостоверяют точность сельхозплощадей. Две крайние Annual/All строки 2023/2024 остаются в карантине из v1.7.

## 4. Независимый APES вторичный архив: что получилось и чего НЕ получилось

[Maxwell Mkondiwa, `Malawi_APES_Data_App`](https://github.com/MaxwellMkondiwa/Malawi_APES_Data_App), snapshot commit `fbd5629f1200c3c18b615ad87c83297c2ed0bd75` от ноября 2023. Публичный dashboard заявляет APES district crop series **1982–2019**, но в **фактически опубликованном статическом CSV-equivalent таблицы** (встроен в HTML) обнаружено лишь **2 240** строк, 28 районов, восемь культурных категорий, **2000–2009**, с 8 согласованными колонками; **840** записей кукурузы трёх отдельных видов `Local/Hybrid/Composite Maize` (28 районов × 10 лет × 3 типа). Оригинальный HTML: 56 098 740 байт, SHA-256 `f27ecfcfeb2bf1d710ee9e45bc8ef93deee6bfb5299f7a9bbb61b32e04e06828`.

Проверка единиц: `MTs ≈ HAs × Yield / 1000`, что предполагает Yield в **кг/га**, а не т/га (медианная относительная ошибка численного восстановления ≈1.75×10⁻¹¹, 97,2% допустимы в пределах 1%). Из 812 Main/Rainfed HarvestStat по точному имени+региону+году сопоставлено только **86** рядов с **кандидатной суммой** трёх maize categories, **ни одна** не равна исходной площади или производству HarvestStat; медианное относительное расхождение для гипотетической суммы составляет **49,4% по площади** и **60,4% по производству**. **Это НЕ независимая валидация**, потому что неизвестны общие определения crop systems, исходные даты APES и корректность сложения Local/Hybrid/Composite. Нельзя «исправлять» ни один ряд по этому dashboard или считать его полным официальным министерским архивом.

## 5. Влияние новой источниковедческой находки на нашу weather–yield регрессию

Из **584** наблюдений основной 16-районной выборки:
- **570** имеют исходный совпавший Raw FDW Yield, то есть ещё **14** полученных рядов не могут подтвердить исходный yield напрямую: **10 Balaka 1988–1997 с географически пересчитанной урожайностью, 4 Balaka 1984–1987 без того же района в raw**.
- **437** имеют и совпадение raw посевной площади, и производство; остальные **147** получены после масштабирования или региональной композиции (133 с сохранённым yield, 10 с изменённым, 4 без прямого district-key).
- Дополнительные исходно зафиксированные diagnostic samples, без подгонки под значимость:

| Sample (16 districts) | N | β JRC broad | two-way district+year SE |
|--|--:|--:|--:|
| all Main/Rainfed | 584 | 0.103048 | 0.034627 |
| only direct raw Yield match | 570 | 0.101390 | 0.036462 |
| raw Area Planted + Production match | 437 | 0.111310 | 0.046718 |
| harvesting years ≥1998 | 362 | 0.110906 | 0.053867 |

Все четыре климатических окна сохраняют β>0 на этих подвыборках; [CSV](results/malawi_apes_fdw_source_audit_v1/malawi_source_based_weather_yield_sensitivity.csv) содержит 20 диагностических FE моделей, включая очень короткий 2018–2020 период (42 строки, **не** допустим как основная модель). 14 программных проверок PASS, включая независимый direct dense dummy OLS-FWL на 437 строках с разницей коэффициента **2.78×10⁻¹⁷**. При ограничениях неопределённость увеличивается, отбор не случаен; это **НЕ причинный эффект** осадков или соглашения ZAMCOM.

## 6. Методологический вердикт и следующие действия

**ПРОДОЛЖАТЬ R1, но не объявлять административную / полевую причинную устойчивость доказанной.** Изменённая административная география, имеющаяся методика пересчёта площадей, отсутствие единых APES первичных ведомостей и дальнейший разрыв Main/Rainfed↔Annual/All требуют отдельной источниковедческой оговорки в методах магистерской. E06 spatial-SE PASS не решает ошибки агрегирования исходов. `B08` меняется с «источник не доступен» на **частично**: первичный raw FDW и открытый авторский код получены, но документы Малавийского Ministry/земельная/урожайная история и качество самого APES всё ещё не полностью проверены; `E07` также частично.

**Следующее проверяемое действие:** точная реконструкция архива administrative shapefiles 1971/1998/2003, `link_ratio` для 16 районов, классификация PBR/CBR по времени и зоне; после этого county-year weather × crop overlap или robustness от географически пересчитанных рядов. Параллельно запрос/поиск первичных APES/FDW документаций для соответствия `Main` годам, а не просто повтор FEWS NET.

**Артефакты**: [source discovery QA](results/malawi_apes_fdw_source_audit_v1/discovery_original_FDW_and_APES_html_QA.json), [строгий по FNID-year](results/malawi_apes_fdw_source_audit_v1/malawi_915_FDW_raw_source_value_reconciliation.csv), [сверка по району+году](results/malawi_apes_fdw_source_audit_v1/historical_APES_FDW_vs_HarvestStat_by_district_year_unharmonized_identity.csv), [исторические FNID](results/malawi_apes_fdw_source_audit_v1/historical_FDW_district_names_Fnid_versions.csv), [year QA](results/malawi_apes_fdw_source_audit_v1/historical_FDW_match_by_year_name_based.csv), [APES dashboard QA](results/malawi_apes_fdw_source_audit_v1/secondary_APES_dashboard_extraction_QA.json), [weather-yield robustness](results/malawi_apes_fdw_source_audit_v1/malawi_source_based_weather_yield_sensitivity.csv).

All source original raw data are public but **not redistributed in this repo**. All downloaded raw binary files are stored only in temporary GitHub Actions paths. Source SHA and provenance pinned. No personal farm-level data.
