#!/usr/bin/env python3
"""Reproduce aggregate arithmetic from Mathematica 2021 Table IV.2.
This is not a microdata audit, hydrology test, or causal estimate.
"""
import csv, json, pathlib, statistics, math
from decimal import Decimal
p=pathlib.Path(__file__).parent
src=p/"di_sectors_table_iv2.csv"
with src.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
assert len(rows)==7 and {r["sector"] for r in rows}=={"S1","S2","C1","C2","C3","C4","North"}
s=lambda key:sum(Decimal(r[key]) for r in rows)
assert s("area_ha")==2247 # Printed total 2246; 1-ha discrepancy likely rounding, not silently fixed
assert s("farmers_n")==4177
assert s("savings_fcfa")==55316918
for r in rows:
    implied=Decimal(r["savings_fcfa"])/Decimal(r["area_ha"])
    assert abs(implied-Decimal(r["savings_fcfa_per_ha_published"]))<=Decimal("0.5")
rice_area_pct=sum(Decimal(r["area_ha"])*Decimal(r["rice_area_pct"]) for r in rows)/s("area_ha")
assert round(rice_area_pct)==23
x=[float(r["rice_area_pct"]) for r in rows]
y=[float(r["end_season_recovery_pct"]) for r in rows]
z=[float(r["long_term_recovery_pct"]) for r in rows]
assert round(statistics.mean(y))==55 and round(statistics.mean(z))==85
slope=statistics.covariance(x,y)/statistics.variance(x)
slope_check=sum((u-statistics.mean(x))*(v-statistics.mean(y)) for u,v in zip(x,y))/sum((u-statistics.mean(x))**2 for u in x)
assert math.isclose(slope,slope_check,abs_tol=1e-12)
out={"status":"ARITHMETIC_PASS_WITH_1HA_GAP","sectors":7,
     "area_rows_ha":2247,"area_published_total_ha":2246,
     "farmers_sum":4177,"savings_fcfa_sum":55316918,
     "weighted_rice_area_pct":round(float(rice_area_pct),3),
     "descriptive_slope_endseason_recovery_pp_per_30pp_rice":round(slope*30,3),
     "microdata_accessed":False,"canal_discharge_accessed":False,
     "g3_fields_g4_flow_g5_institutions_closed":False,
     "source":"Mathematica 2021 Final Report, Table IV.2 (printed p.71); values manually transcribed from accessible text",
     "warning":"One scheme, seven sectors, reported aggregate data. Do not claim causal CTGS effect."}
(p/"qa_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
