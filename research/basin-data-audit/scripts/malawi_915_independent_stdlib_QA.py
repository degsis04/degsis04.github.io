"""Second independent numerical QA for Malawi 915 maize source definitions.

Only stdlib csv, decimal, collections (does not reuse pandas groupby code).
Rechecks 915 source-derived rows and does NOT silently repair the two
qc_flag=0 production anomalies. No climate modelling.
"""
import collections,csv,datetime as dt,json,pathlib,sys,traceback
from decimal import Decimal,InvalidOperation
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/"results"/"malawi_maize_semantics_v1"
REPORT={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","checks":{},"errors":[]}
def ck(k,pass_,meta=None):
 REPORT["checks"][k]={"pass":bool(pass_),"detail":meta}
 if not pass_: REPORT["errors"].append(k)
def read(filename):
 with (D/filename).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
try:
 orig=read("all_915_source_record_decision_audit.csv")
 primary=json.loads((D/"Malawi_915_primary_original_source_QA.json").read_text())
 ck("original_checked_against_pinned_source",primary["status"]=="PASS")
 ck("all_915_records",len(orig)==915,len(orig))
 ps=collections.Counter((x["season_name"],x["crop_production_system"]) for x in orig)
 ck("exact_two_original_categories",ps=={("Main","Rainfed (PS)"):812,("Annual","All (PS)"):103},
    {str(k):v for k,v in ps.items()})
 fnids={x["fnid"] for x in orig}
 ck("actual_outcome_geography_23_not_26",len(fnids)==23,len(fnids))
 ck("single_crop",all(x["fnid"].startswith("MW") for x in orig))
 full=[(x["fnid"],x["harvest_year"],x["season_name"],x["crop_production_system"]) for x in orig]
 ck("source_full_key_unique",len(set(full))==915)
 counts=collections.Counter((x["fnid"],x["harvest_year"]) for x in orig)
 doubles=[k for k,n in counts.items() if n>1]
 ck("two_duplicated_district_year_keys",len(doubles)==2,len(doubles))
 ck("2020_duplicates_only",all(y=="2020" for _,y in doubles),doubles)
 ck("no_three_per_year",max(counts.values())==2)
 ck("row_source_qc0",all(x["qc_flag_p"]=="0" for x in orig))
 errors=[];extremes=[]
 for x in orig:
  area=Decimal(x["area_p"]);prod=Decimal(x["production_p"]);yv=Decimal(x["yield_p"])
  e=abs((prod/area-yv)/yv)
  if e>Decimal("1e-8"):errors.append(x["fnid"]+"/"+x["harvest_year"])
  if yv>10 or prod>1000000:extremes.append((x["fnid"],x["harvest_year"],str(yv),str(prod)))
 ck("yield_arithmetic_all_915_again",not errors,errors[:3])
 ck("two_unflagged_extremes",len(extremes)==2,extremes)
 ck("specifically_Lilongwe_2024_7x_national",
    any(x["fnid"]=="MW2018A20104" and x["harvest_year"]=="2024" and
        Decimal(x["production_p"])/Decimal("2712578")>7 for x in orig))
 ck("specifically_Thyolo_2023_gt50t_ha",
    any(x["fnid"]=="MW2018A20330" and x["harvest_year"]=="2023" and
        Decimal(x["yield_p"])>50 for x in orig))
 # Independent first/last-year check that source labels DO NOT
 # imply identical years, even when all are crop=maize.
 yrs=collections.defaultdict(list)
 for x in orig: yrs[(x["fnid"],x["season_name"],x["crop_production_system"])].append(int(x["harvest_year"]))
 valid={}
 for k,v in yrs.items():
  y=sorted(set(v));span=y[-1]-y[0]+1; gaps=span-len(y)
  valid[k]=(len(y)>=30 and gaps/span<=.05)
 longgood=sum(int(ok) for (fnid,season,ps),ok in valid.items() if season=="Main" and ps=="Rainfed (PS)")
 ck("16_strict_main_rainfed_districts",longgood==16,longgood)
 flag_decisions=collections.Counter(x["pre_regression_status"] for x in orig)
 ck("no_uncertain_extreme_marked_ready",
    all(x["pre_regression_status"]=="BLOCK_OUTLIER_UNRESOLVED" for x in orig
        if Decimal(x["yield_p"])>10 or Decimal(x["production_p"])>1000000))
 REPORT["counts"]={
  "n":len(orig),"n_fnids":len(fnids),"distinct_fnid_year":len(counts),
  "source_category_labels":{"/".join(k):v for k,v in ps.items()},
  "n_dual_label_year":len(doubles),
  "dual_label_years":[{"fnid":x,"year":y} for x,y in doubles],
  "n_outlying_source_rows":len(extremes),
  "outliers":[{"fnid":x,"year":y,"yield_t_ha":z,"production_t":t} for x,y,z,t in extremes],
  "n_strict_main_rainfed_districts":longgood,
  "review_decisions":dict(flag_decisions)}
 REPORT["status"]="PASS" if not REPORT["errors"] else "FAIL"
except Exception as ex:
 REPORT["status"]="FAIL";REPORT["errors"].append(repr(ex))
 REPORT["traceback"]=traceback.format_exc()[-2000:]
(D/"Malawi_915_INDEPENDENT_standard_library_QA.json").write_text(
 json.dumps(REPORT,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":REPORT["status"],"errors":REPORT["errors"],
                  "counts":REPORT.get("counts")},ensure_ascii=False,indent=2)[:12000])
if REPORT["status"]!="PASS":sys.exit(1)
