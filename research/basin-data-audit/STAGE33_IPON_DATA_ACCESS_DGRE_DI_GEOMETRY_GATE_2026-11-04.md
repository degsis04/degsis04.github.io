# Этап 33 · IPON: пространственные зоны и измеренные подачи; DGRE: исходные архивы; Di: исполнительная GIS
**04.11.2026. Статус: SOURCE AND ACCESS AUDIT DONE; IPON DATA ACCESS BLOCKED; DGRE MONTHLY EXCERPT CALCULATED; PHYSICAL INTAKE STILL OPEN.**

## 1. Главный вопрос
Проверить, доступны ли действительно открытые polygon/casier-level исходные данные национального оператора Office du Niger и измеренная подача воды по зоне/сезону, а не только спутниковые AETI общей маски. Параллельно выяснить, можно ли получить исполнительный GIS Di и реальный дневной ряд расходов/уровней DGRE за 2015–2023, с отдельной проверкой station identity.

## 2. IPON / Office du Niger: есть данные внутри системы, но официальный публичный экспорт не проверен

**Оригинальные свидетельства, не интерпретация по скриншоту:**
- [FAO, IPON application catalogue](https://www.fao.org/in-action/remote-sensing-for-water-productivity/applications-and-uses/applications-catalogue/product-detail/ipon-tool-irrigation-performance-of-office-du-niger38544db9-cf19-41d5-8c7a-623a8d32139c/en): IPON 11 показателей производительности орошения, для культур/лет/сезонов и зон/casiers. Физическая подача/consumption совмещается с WaPOR. **НЕ следует считать, что публикация описания открывает отдельные измерения в CSV**.
- [FAO, workshop 06–07.11.2024](https://www.fao.org/in-action/remote-sensing-for-water-productivity/news-and-events/news/news-detail/fao-hosts-workshop-to-evaluate-the-beta-version-of-the-ipadt-tool-for-irrigation-performance-at-the-office-du-niger/fr): участники **завершали карту и идентификаторы зон и участков**, включая внешние площади. Это подтверждает наличие геометрии/справочников у авторов, но **не наличие опубликованного GIS**.
- [IWMI, 08.06.2026](https://www.iwmi.org/blogs/listen-before-you-build/): IPON работает по **tertiary-level casiers**, Office du Niger самостоятельно обновляет проект после передачи 2025 г.; в системе есть наземные измерения воды, 11 индикаторов, эксплуатационное использование. Размер около 130,000 га относится к operational scheme как заявлено IWMI, **не к нашим действительным пикселям WaPOR 984.8392 км²**.
- [FAO официальная передача, 30.09.2025](https://www.fao.org/in-action/remote-sensing-for-water-productivity/news-and-events/news/news-detail/official-handover-of-the-ipon-digital-tool-to-the-office-du-niger-under-the-wapor-project/en): оператор Office du Niger принял финальную систему, а не доказал публичную лицензию для всех исходных in situ данных.
- [Публичная Tableau beta](https://public.tableau.com/app/profile/water.eleaf/viz/IWMI_IPADT_Dashboard_20240320/Overview).

**Строго выполненный тест доступности оригинальных экспортов:** GitHub Actions с обычным публичным HTTPS без учётных данных запрашивал профиль, embed HTML, `.csv`, `.xlsx`, `.twbx` для dashboard Overview. [Подробный QA](results/stage33_ipon_public_access/IPON_Tableau_exact_public_export_QA.json):
  - профиль HTTP 200, **но фактически HTML от AWS WAF**, не таблица;
  - embed HTML HTTP 200, код страницы есть, **численные CSV и исходные polygon layers не извлечены**;
  - dashboard `.csv` HTTP **404**, `.xlsx` HTTP **404**, `.twbx` HTTP **404**;
  - **0 проверенных доступных machine-readable загрузок**, **0 подтверждённых индивидуальных georeferenced casier-polygons**, **0 подтверждённых исходных in-situ records**.
**Статус:** IPON metadata = CONFIRMED; AUTHOR HOLDS ZONE/CASIER GIS = PUBLISHED CONFIRMED; public GIS/data export = NOT CONFIRMED / BLOCKED. 404 не доказывает отсутствие данных у оператора и не разрешает обойти аутентификацию. Скриншот Dashboard нельзя оцифровать как calibrated dataset. Мы НЕ приписываем всему WaPOR valid-mask принадлежность casier и НЕ вычисляем water supplied из AETI.

**Оценочные переменные, которые нужны для корректной модели:** `zone_id`, `casier_id`, original WGS84 polygon+CRS+validity; `rice_or_sugarcane`, seasonal window, yield/area; измеренная вода `irrigation_delivery_m3` + method/source field gauge, calibration, quality flags; ID hydraulic intake and connection to Markala canals; documented release/allocation decisions. Точность day/week/month нужна отдельно для timed hydro stress. За 2018–23 можно начать компоновку только после проверки этих полей.

## 3. DGRE: воспроизводимая дополнительная помесячная таблица, а не фиктивный суточный расход

Официальный [бюллетень DGRE за январь 2019](https://eauburkina.com/images/SNIEau/Janvier_2019.pdf), **Tableau 11 / печатная стр.19**, видимые страницы PDF проверены. Запас Yaran (млн м³):

| Январь года | 1 января | 31 января | изменение запаса | % PEN на 1 и 31 января |
|---|---:|---:|---:|---|
| 2017 | 432 | 354 | **−78** | 119.88 / 98.20 |
| 2018 | 327 | 263 | **−64** | 90.70 / 73.13 |
| 2019 | 618 | 466 | **−152** | 171.53 / 129.44 |

[Код и QA](scripts/stage33_DGRE_Jan2019_and_station_id_QA.py) воспроизводит все значения, отдельно сверяет Jan 1 2017/18/19 с годовым массивом DGRE [stage32](results/stage32_sourou_real_hydrology/DGRE_Yaran_2015_2023_nine_annual_first_report_source_tables.csv) и пересчитывает проценты с округлением. **14/14 проверок PASS**.

**ВАЖНО:** документ 2019 задаёт `plan d'eau normal` 360 млн м³, бюллетень 2024 использует `capacité totale` 603 млн м³. Это **разные опубликованные опорные определения**, поэтому процентные запасы разных лет нельзя сравнивать без уточнения что обозначает PEN и произошёл ли пересчёт зависимости volume(stage). Формально 360≠603, но это само по себе не доказательство ошибки измерения. Объёмы на 1 и 31 января относятся к **регулируемому запасу**, а разности −78,−64,−152 млн м³ НЕ являются наблюдёнными насосными отборами/сбросами или «объёмами полива Di».

Не получен **полный дневной ряд 2015–2023**. Данные DGRE публикуются в отдельных месячных бюллетенях (и графиках), а официальная форма [DGRE «Demande de données»](https://dgre.gov.bf/demande-de-donnees/) позволяет запрашивать исходные `Débit`, `Cote`, `Shapefile des ouvrages` и периоды daily/weekly/monthly. Статус доступности первичных архивов не подтверждён до ответа учреждения. Не создавать «полный» ряд из графических изображений, округлённых годовых минимумов или интерполяции.

## 4. Критическая идентификация двух разных гидропостов «Yaran»

[Атлас долины Sourou (Mali), Zwarts, Bekkema & van der Kamp 2019, часть 3, рисунок 3](https://www.altwym.nl/wp-content/uploads/2019/05/atlas_sourou_partie-3_225-dpi-final.pdf): исторический discharge у **Lanfièra**, описанный как «près de Yaran», **SIEREM BFQ4048**, координаты **12.753N −3.433W**, Jan1985–Jun2007. Это исторические расходы Q м³/с (в статье графики), временно НЕ совпадают с новым сельхозрядом 2015–2023.

[Официальный DGRE 2023 Yaran](https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf): **IRD 1202702205**, **12°58′48.8″ N / 03°26′49.4″ W** = **12.980222N −3.447056W**, объёмы/уровни. При независимом расчёте по сферической геодезии между опубликованными координатами **25.3119 км**, поэтому **ни название, ни близость реки не доказывают одну и ту же station identity/порог**. Программа записала оба набора с флагами NO MERGE. Даже идентичность поста не гарантировала бы сопоставимость Q и storage без rating curves и регулирования Лери.

## 5. Исполнительный GIS Di: аудит доступных документов

- [Mathematica 2021 MCC](https://www.mathematica.org/-/media/publications/pdfs/international/2021/burkina_faso_adp_final_report.pdf): new Di, **7 построенных насосных секторов / 2246 га**, AMVS→WUA water-delivery chain, нет WGS84 as-built coordinates/seven polygon shapefiles.
- [SCET Tunisie, инженерный проект](https://www.scet-tunisie.com/projets/amenagement-de-2500-ha-de-perimetres-irrigues-dans-la-vallee-du-sourou): **проектная** версия ~2500 га / **8 станций** / указано **SIG de l'emprise des ouvrages**. Подтверждено, что для проектирования создавали GIS, но **файлы исполнительной версии не скачаны**, 8-design≠7-asbuilt.
- [ERA International, отдельная реабилитация 2012](https://era-inter.com/projects/etude-apd-dce-de-rehabilitation-de-4-perimetres-irrigues-gravitaires-de-1585-ha-dans-la-vallee-de-sourou/): перечислены **старые** периметры Niassan 500 га, Débé 475, Gouran 540, CRTO Di 70 га. Они **не являются** новым MCC Di 2246 га, их нельзя агрегировать как одну схему/насосы.
- Предыдущий OSM Overpass source audit завершился timeout+502, отсутствие OSM координат не равнозначно отсутствию реальных насосов.
- [Рамсарская форма по Sourou](https://rsis.ramsar.org/ris/1885) содержит AMVS как организацию управления долиной; <data license/source gate> отдельное от коммерческого as-built проекта.
- Официальный источник AMVS (по опубликованному Ramsar 2017) адрес `amvs@fasonet.bf` **исторический, актуальность сейчас не проверена**; при обращении сначала проверять текущий контакт.

**Итог GIS:** существование проектной GIS системы = **CONFIRMED**, исполненные координаты 7 Di + хозяйственно связанные поля = **NOT OBTAINED**.

## 6. Приоритетный запрос данных, без авторизации, без фальшивых рядов

**A / Office du Niger / IWMI / FAO WaPOR:**
- export `casier_id, zone_id, source_geometry, polygon CRS, mapping year`, реестр main/secondary/tertiary canal and intake;
- выгрузка для каждого casier×crop×season×year 2018–2023: measured/inferred `Q m3/s`, `delivery_m3`, observation method, meter and QC, seasonal crop mask and area;
- справочник первичных vs расчётных IPON indicators (11), formulas, license, changes between public 2024 beta and 2025 final release;
- explicit public license or research-use terms, no farmer identifiers.

**B / AMVS / MCC / SCET (Di):**
- исполнительный план семи построенных станций с координатами CRS, названиями, 7 секторными polygons, canal connectivity;
- привязка к старой схеме CRTO Di 70 га / Niassan 500 га, причины разницы 8/2500 design против 7/2246 as-built;
- измерения насосов часы, расход/объём, сезон, аварии, обслуживание и происхождение воды.

**C / DGRE (Sourou–Léry):**
- DGRE «Demande de données»: станция Yaran ID IRD 1202702205 и Barrage Léry, old Lanfièra BFQ4048 отдельно;
- **daily 2015–2023** stages, verified stage→storage volume curves (PEN360 / capacity603 / 608 in older reports), uncertainties/revisions, flows at Léry gate and downstream Mouhoun; rainfall and reservoir operational schedule;
- отдельно запросить объяснение **2021Dec31 580 vs 2022Jan1 511.462** и **2023Dec31 668 vs 2024Jan1 585.339** млн м³.
- запрашивать archive metadata, public license и documented quality flags.

**Не отправлено:** формы и письма требуют персональных отправительских данных и выбора адресата, это зафиксированный checklist, не обещание получить их автоматически.

## 7. Решение по исследовательскому дизайну

Дальнейшая количественная модель оправдана **только при валидной единице «касиер × сельскохозяйственный сезон» с подтверждённой GIS и water-supply записью**. Для промежуточной описательной гидрологии можно использовать оригинальные частичные DGRE таблицы с источниковыми флагами. Активация IPON — положительный результат **национального института** Office du Niger, но **не доказательство эффекта межгосударственного режима** или механизмов Niger Basin Authority. Не строить искусственное `treaty*rainfall` у 1–2 стран и не выдавать AETI за расход на водозаборе.

**Этап 33 завершён как source-access audit + проверенный помесячный расчёт DGRE. IPON публичная исходная геометрия / измеренные deliveries — BLOCKED / not publicly verified. Di asbuilt — BLOCKED. Реальный следующий gate — получение первичных документов через источниковые учреждения, либо альтернативный полностью открытый hydro/GIS-кейс.**
