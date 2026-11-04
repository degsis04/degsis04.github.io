"""Stage 31: independent year-on-year rice area/yield decomposition, DGRE cross-document QA.
All calculations descriptive. N=9 province-level rice series, N=3 DGRE annual Yaran rows.
Do not claim river pumping, CTGS effects or scheme-specific Di yields.
"""
from pathlib import Path
import csv, json, hashlib, datetime, sys, math, traceback
R=Path(__file__).resolve().parents[1]; IN=R/"results"/"stage30_sourou_di_physical_water"
OUT=R/"results"/"stage31_sourou_reconciliation";OUT.mkdir(parents=True,exist_ok=True)
SRC_2022="https://dgre.gov.bf/documents/20/DOC_SYNT_2022_VF.pdf"
SRC_2023="https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf"
SRC_JAN="https://dgre.gov.bf/documents/6/Bulletin_Janvier_2024_Vf.pdf"
log={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"status":"STARTED","checks":{}, "measurement_support":{
"yield":"Sourou province all Annual Plaine/Bas-fond irrigated rice; NOT Di seven-sector yield",
"hydrology":"Yaran regulated reservoir storage; NOT Sourou intake or irrigation scheme pumping",
"institution":"NO verified cross-border CTGS release to Di",
"cross_year":"31 December to 1 January should be same gauge/site but source metadata/rating curves could differ"}}
def check(k,condition,details=""):
 log["checks"][k]={"pass":bool(condition),"details":details}
 if not condition:raise AssertionError(f"{k}: {details}")
def csvread(path):
 with open(path,encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def writecsv(name,rows,columns=None):
 if columns is None:columns=list(rows[0])
 with open(OUT/name,"w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
try:
 raw=csvread(IN/"province_sourou_2015_2023_nine_irrigated_rice_source_verified.csv")
 old=csvread(IN/"DGRE_Yaran_2022_2023_annual_storage_SOURCE_TRANSCRIPTION.csv")
 jan=csvread(IN/"DGRE_Yaran_January_2022_2024_storage_SOURCE_TRANSCRIPTION.csv")
 check("nine_original_rice_years",len(raw)==9 and [int(x["harvest_year"]) for x in raw]==list(range(2015,2024)))
 check("annual_2022_2023_count",len(old)==2 and {int(x["year"]) for x in old}=={2022,2023})
 check("jan_2022_2024_count",len(jan)==3 and {int(x["year"]) for x in jan}=={2022,2023,2024})
 data=[]
 for x in raw:
  a=float(x["area"]);p=float(x["production"]);y=float(x["yield"])
  check("value_units_yield_positive_"+x["harvest_year"],a>0 and y>0 and p>0)
  check("yield_production_area_identity_"+x["harvest_year"],abs(p/a-y)<1e-9)
  check("qc_flag_zero_"+x["harvest_year"],x["qc_flag"]=="0")
  check("correct_irrigated_source_scope_"+x["harvest_year"],
        x["fnid"]=="BF2020A24606" and x["crop_production_system"]=="Plaine/Bas-fond irrigated (PS)" and x["season_name"]=="Annual")
  data.append({"year":int(x["harvest_year"]),"a":a,"y":y,"p":p})
 changes=[]
 for prev,cur in zip(data,data[1:]):
  da=cur["a"]-prev["a"];dy=cur["y"]-prev["y"];dp=cur["p"]-prev["p"]
  ca=(cur["y"]+prev["y"])/2*da
  cy=(cur["a"]+prev["a"])/2*dy
  chk=abs((ca+cy)-dp)
  check(f"exact_symmetric_decomposition_{prev['year']}_{cur['year']}",chk<1e-8,chk)
  # Multiplicative identity independently checked with logs. 
  lp=math.log(cur["p"]/prev["p"])
  la=math.log(cur["a"]/prev["a"])
  ly=math.log(cur["y"]/prev["y"])
  check(f"log_identity_{prev['year']}_{cur['year']}",abs(lp-la-ly)<1e-11)
  changes.append({
   "year_previous":prev["year"],"year_current":cur["year"],
   "area_previous_ha":prev["a"],"area_current_ha":cur["a"],
   "yield_previous_t_ha":prev["y"],"yield_current_t_ha":cur["y"],
   "production_previous_t":prev["p"],"production_current_t":cur["p"],
   "area_change_ha":da,"area_change_pct":100*(cur["a"]/prev["a"]-1),
   "yield_change_t_ha":dy,"yield_change_pct":100*(cur["y"]/prev["y"]-1),
   "production_change_t":dp,"production_change_pct":100*(cur["p"]/prev["p"]-1),
   "symmetric_area_component_t":ca,"symmetric_yield_component_t":cy,
   "symmetric_area_abs_share":abs(ca)/(abs(ca)+abs(cy)) if abs(ca)+abs(cy)>0 else 0,
   "symmetric_yield_abs_share":abs(cy)/(abs(ca)+abs(cy)) if abs(ca)+abs(cy)>0 else 0,
   "log_change_production":lp,"log_change_area":la,"log_change_yield":ly,
   "spatial_support":"Sourou PROVINCE not Di; neither component is causal water allocation effect",
   "method":"exact symmetric two-factor decomposition P=Area*Yield"})
 writecsv("Sourou_rice_2015_2023_ALL_interannual_exact_area_yield_decomposition.csv",changes)
 c23=next(x for x in changes if x["year_current"]==2023)
 check("2022_23_production_fall",c23["production_change_t"]<0)
 check("2022_23_area_dominant",c23["symmetric_area_abs_share"]>0.7,c23["symmetric_area_abs_share"])
 hydro=[{"year":2021,"jan1":608.0,"max":721.0,"min":117.0,"min_date_as_published":"2020-07-10",
  "dec31":580.0,"spill_days":102,"source":SRC_2022,"table":"Table 12 printed p49",
  "year_label_warning":"2021 minimum date published as 2020; not corrected"},
 {"year":2022,"jan1":511.0,"max":884.0,"min":105.0,"min_date_as_published":"2022-06-21",
  "dec31":717.0,"spill_days":117,"source":SRC_2023,"table":"Table 12 printed p49",
  "year_label_warning":"2022 annual 2022 report lists min date 2021-06-21; prefer 2023 report for date with contradiction retained"},
 {"year":2023,"jan1":717.0,"max":726.0,"min":143.0,"min_date_as_published":"2023-06-21",
  "dec31":668.0,"spill_days":126,"source":SRC_2023,"table":"Table 12 printed p49",
  "year_label_warning":"2023-12-31 annual end does not match bulletin 2024-01-01"}]
 writecsv("DGRE_Yaran_2021_2023_three_annual_measures_with_quality_flags.csv",hydro)
 jan_by={int(x["year"]):x for x in jan}
 bounds=[]
 for v in hydro:
  yy=v["year"];following=jan_by.get(yy+1);same=jan_by.get(yy)
  if same: bounds.append({"boundary":"same_year_start "+str(yy),"year":yy,"report_year":yy,
   "annual_report_value_Mm3":v["jan1"],"monthly_bulletin_value_Mm3":float(same["volume_01jan_Mm3"]),
   "difference_Mm3":float(same["volume_01jan_Mm3"])-v["jan1"],"source_annual":v["source"],
   "source_monthly":SRC_JAN,"interpretation":"compare two documents for Jan1; difference may be rounding, reference or revision"})
  if following:
   vnext=float(following["volume_01jan_Mm3"])
   bounds.append({"boundary":"Dec31 "+str(yy)+" to Jan1 "+str(yy+1),
      "year":yy,"report_year":yy+1,"annual_report_value_Mm3":v["dec31"],
      "monthly_bulletin_value_Mm3":vnext,"difference_Mm3":vnext-v["dec31"],
      "source_annual":v["source"],"source_monthly":SRC_JAN,
      "interpretation":"CROSS DOCUMENT DATE GAP; not an observed overnight release or pumping volume"})
 # Additional annual to next-year annual report on year boundary
 for f,p in zip(hydro,hydro[1:]):
  bounds.append({"boundary":"Annual Dec31 "+str(f["year"])+" to annual Jan1 "+str(p["year"]),
   "year":f["year"],"report_year":p["year"],"annual_report_value_Mm3":f["dec31"],
   "monthly_bulletin_value_Mm3":p["jan1"],"difference_Mm3":p["jan1"]-f["dec31"],
   "source_annual":f["source"],"source_monthly":p["source"],
   "interpretation":"ANNUAL CROSS REPORT GAP, should be audited; not flow or correction"})
 writecsv("Yaran_2021_2024_cross_document_year_boundary_QA.csv",bounds)
 gaps={(r["year"],r["report_year"],r["boundary"].startswith("Dec31")):r["difference_Mm3"] for r in bounds}
 check("2021_2022_gap_minus69",abs((hydro[1]["jan1"]-hydro[0]["dec31"])+69)<1e-12)
 check("2022_2023_boundary_consistent",abs(float(jan_by[2023]["volume_01jan_Mm3"])-hydro[1]["dec31"])<1)
 check("2023_2024_gap_minus82_661",abs(float(jan_by[2024]["volume_01jan_Mm3"])-hydro[2]["dec31"]+82.661)<1e-9)
 check("two_material_unreconciled_gaps",
       sum(abs(x["difference_Mm3"])>10 for x in bounds)>=2)
 check("2022_minimum_date_typo_logged",hydro[1]["year_label_warning"].find("2021-06-21")>=0)
 # 2021 min date in original official pdf 2022 annual table is 2020, do not silently correct
 check("2021_minimum_date_previous_year_logged",hydro[0]["min_date_as_published"].startswith("2020"))
 # Same-year join only to demonstrate mismatch of spatial supports
 join=[]
 for h in hydro:
  yy=h["year"];obs=next(z for z in data if z["year"]==yy)
  join.append({"year":yy,"reservoir_min_Mm3":h["min"],"reservoir_max_Mm3":h["max"],
     "reservoir_dec31_Mm3":h["dec31"],"rice_yield_t_per_ha_PROVINCE":obs["y"],
     "rice_area_ha_PROVINCE":obs["a"],"rice_production_t_PROVINCE":obs["p"],
     "irrigation_intake_Q_observed":False,"scheme_yield_observed":False,
     "causal_allowed":False,
     "message":"Only 3 common years, mismatched scales and source QA conflicts"})
 writecsv("Yaran_2021_2023_vs_rice_PROVINCE_NOT_A_REGRESSION.csv",join)
 log["counts"]={"rice_years":len(data),"exact_yoy_decompositions":len(changes),
  "reservoir_annual_years":len(hydro),"reservoir_vs_rice_descriptive_years":len(join),
  "source_conflict_flags":sum(abs(x["difference_Mm3"])>10 for x in bounds)}
 log["2022_2023"]={"production_delta_t":c23["production_change_t"],
   "area_component_t":c23["symmetric_area_component_t"],
   "yield_component_t":c23["symmetric_yield_component_t"],
   "area_component_fraction_of_total_drop":c23["symmetric_area_component_t"]/c23["production_change_t"],
   "area_pct":c23["area_change_pct"],"yield_pct":c23["yield_change_pct"],"production_pct":c23["production_change_pct"]}
 log["scientific_gates"]={
 "agriculture_year_change_decomposition":"PASS mathematical, 9 province rice years, causal interpretation not permitted",
 "annual_hydrology_2021_2023":"PARTIAL three annual summary years, with two irreconciled year boundaries and copied date errors",
 "reservoir_to_di_actual_pump_flow":"NO",
 "five_plus_seasons_hydrology_matched_to_di_crop":"NO",
 "verified_treaty_release":"NO",
 "genuine_WaPOR_scene_downloaded":"NO",
 "approach":"Collect as-built polygon, local pump operation logs, official stage-volume series and independently QA hydro levels"}
 log["status"]="PASS_QA_CONFLICTS_EXPLICIT"
except Exception as e:
 log["status"]="FAIL";log["error"]=repr(e);log["trace"]=traceback.format_exc()[-3500:]
(OUT/"stage31_derived_province_rice_DGRE_QA.json").write_text(json.dumps(log,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in log.items() if k in
 ["status","2022_2023","counts","error"]},ensure_ascii=False))
sys.exit(0 if log["status"]=="PASS_QA_CONFLICTS_EXPLICIT" else 1)
