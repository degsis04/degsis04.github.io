# Этап 26 — Malawi rainfed maize: spatiotemporal inference audit
**Дата 04.11.2026. Статус: численный аудит PASS, строгий пространственный Conley / соседство FNID — OPEN.**

## Источник
Данные: `../malawi_rainfed_weather_yield_v1/malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv`, исходный GitHub blob SHA `9c45f3ee12f8d0a515ea6f4c77149f1a9ba11f9b`. Это только 812 **Main / Rainfed** наблюдений за 1983–2020. Строгая выборка 16 FNID / 584 наблюдения, расширенная — 23 FNID / 812; по 38 harvest years.

## Что рассчитано
Независимый JS FWL двухсторонне снимает FNID FE и harvest-year FE. Все восемь beta, district- и year-clustered CR1 standard errors повторили [ранее опубликованный расчёт](../malawi_rainfed_weather_yield_v1/malawi_rainfed_maize_weather_yield_8_FE_models_EXPLORATORY.csv) до 1e-10. Это независимый контроль знака и размерности, а не новая причинная модель.

Новая двухсторонняя кластерная дисперсия `V_district + V_year − V_district×year` с CR1-поправкой для каждой компоненты: стандартная ошибка **0.0346–0.0381** для четырёх окон strict16, тогда как district-only была 0.0217–0.0228, year-only 0.0380–0.0410. Ни одна из восьми двухсторонних дисперсий не отрицательна.

Дополнительные проверки: Bartlett/Newey–West на годовых суммах FWL scores, bandwidth 2, 3, 4; исключение каждого из 38 годов на каждом из 8 вариантов (304 анализа); каждого непрерывного трёхлетнего блока (36×8=288); каждого пятилетнего (34×8=272). Знак beta положительный во всех. Индексы осадков JRC broad имеют положительный Pearson r для 120/120 пар FNID strict16 с минимум 20 общими годами; средняя r≈0.6285, внутри одного большого региона r≈0.8733, между регионами r≈0.5106. **Это не Moran I**: зависимость одного weather field не является формальным пространственным тестом остатка.

## Научные ограничения (обязательны для текста)
- Cluster by year допускает произвольную одновременную корреляцию районных ошибок внутри года, cluster by district — серийную корреляцию внутри района; их двухсторонняя сумма не покрывает все межрайонные временные spillovers.
- Year-score HAC — диагностическая временная чувствительность; не заменяет географическую Conley spatial HAC и не даёт здесь подтверждённых p-values.
- 16 district clusters и 38 years; простые cluster p-values не заявлять confirmatory. Варианты окон коррелированы.
- Year FE поглощают общие общенациональные засухи. Beta оценивает относительную погоду и относительный урожай внутри страны и года.
- HarvestStat area/production/yield не доказаны неизменными по методике APES/FDW во все годы.
- **Нет** treaty indicator, river discharge, irrigation intake или water-allocation exposure. Результат не равен влиянию ZAMCOM/CTGS.

## Воспроизвести
```bash
node research/basin-data-audit/scripts/malawi_stage26_spatiotemporal_qa.js
```
Скрипт читает сохранённый входной CSV из репозитория, не требует npm-пакетов, и создаёт `stage26_8model_spatiotemporal_se.csv` (в расширенной структуре с 3-year block min/max) и `stage26_QA.json`. При несовпадении исходных коэффициентов/SE или смене объёма он аварийно завершится.

**Go/No-Go:** E06 → **ЧАСТИЧНО**. Следующий шаг — проверить координаты и геометрию тех же FNID через оригинальный HarvestStat GIS в метрической проекции и Conley SE с заранее установленными радиусами; только потом считать spatial-correction gate закрытым.
