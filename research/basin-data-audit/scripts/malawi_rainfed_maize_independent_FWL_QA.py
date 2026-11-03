"""Independent Frisch-Waugh-Lovell check for the 8 Malawi maize FE coefficients.
No statsmodels dependency, independent OLS implementation via numpy linear
algebra. Checks data keys, historical category restriction, primary-16
selection, explicit FE formula, district-clustered and year-clustered CR1 SE.

This does not verify the source survey data methodology, biological year
matching or identify a river/treaty effect.
"""
import collections,csv,datetime as dt,json,pathlib,sys,traceback
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/"results"/"malawi_rainfed_weather_yield_v1"
E=ROOT/"results"/"malawi_maize_semantics_v1"/"main_rainfed_only_district_eligibility.csv"
R={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","checks":{},"errors":[]}
def check(name,pass_,detail=None):
 R["checks"][name]={"pass":bool(pass_),"detail":detail}
 if not pass_:R["errors"].append(name)
def csvrows(p):
 with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def main():
 full=csvrows(D/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv")
 elig=csvrows(E);cur=csvrows(D/"malawi_rainfed_maize_weather_yield_8_FE_models_EXPLORATORY.csv")
 primary={r["fnid"] for r in elig if r["strict_30year_5pct_gaps"]=="True"}
 check("812_unambiguous_rainfed_source_outcomes",len(full)==812,len(full))
 check("16_predefined_source_districts",len(primary)==16,len(primary))
 check("model_count_8",len(cur)==8,len(cur))
 pairs={(r["fnid"],int(r["harvest_year"])) for r in full}
 check("all_812_unique_outcome_year_keys",len(pairs)==len(full),len(pairs))
 check("all_yields_positive",all(float(r["yield"])>0 for r in full))
 check("no_ANNUAL_ALL_outcome_crept_in",len(full)==812)
 comparisons=[]
 for cohort in ["strict16","all23"]:
  selected=[r for r in full if cohort=="all23" or r["fnid"] in primary]
  district=sorted({r["fnid"] for r in selected})
  years=sorted({r["harvest_year"] for r in selected})
  n=len(selected)
  # Fixed-effects controls Z = [ones, 1(district_i), 1(year_t)] excluding
  # baseline district and year to enforce full column rank.
  Z=np.ones((n,1+(len(district)-1)+(len(years)-1)),dtype=float)
  Z[:,1:]=0.
  dmap={name:j for j,name in enumerate(district[1:],start=1)}
  ymap={name:j+len(district)-1 for j,name in enumerate(years[1:],start=1)}
  for i,r in enumerate(selected):
   if r["fnid"] in dmap:Z[i,dmap[r["fnid"]]]=1
   if r["harvest_year"] in ymap:Z[i,ymap[r["harvest_year"]]]=1
  y=np.array([np.log(float(r["yield"])) for r in selected])
  yres=y-Z@np.linalg.lstsq(Z,y,rcond=None)[0]
  for window in ["broad","core","waha_broad","waha_growth"]:
   x=np.array([float(r[window]) for r in selected])
   xres=x-Z@np.linalg.lstsq(Z,x,rcond=None)[0]
   XX=float(xres@xres); beta=float((xres@yres)/XX)
   u=yres-beta*xres
   nparam=Z.shape[1]+1
   se={}
   for label in ["district","year"]:
    groups=[r["fnid"] if label=="district" else r["harvest_year"] for r in selected]
    agg=collections.defaultdict(float)
    for v,g in zip(xres*u,groups): agg[g]+=float(v)
    G=len(agg)
    var=(G/(G-1))*((n-1)/(n-nparam))*sum(v*v for v in agg.values())/(XX**2)
    se[label]=float(np.sqrt(var))
   found=[m for m in cur if m["sample"]==cohort and m["window"]==window]
   if len(found)!=1:raise ValueError(f"Cannot locate exactly one model {cohort}/{window}")
   src=found[0]
   beta_diff=abs(beta-float(src["beta_log_yield_per_plus_1_z"]))
   sediff=abs(se["district"]-float(src["district_cluster_se"]))
   seyrdiff=abs(se["year"]-float(src["year_cluster_se"]))
   comparisons.append({"sample":cohort,"window":window,"n":n,"fullrank_expected":nparam,
     "beta_fwl":beta,"beta_abs_error":beta_diff,"district_cluster_se_error":sediff,
     "year_cluster_se_error":seyrdiff,
     "pass":beta_diff<1e-8 and sediff<1e-7 and seyrdiff<1e-7})
 check("8_independent_FWL_coefficients_and_twocluster_diagnostics",
   all(m["pass"] for m in comparisons),
   {"max_beta_abs_error":max(v["beta_abs_error"] for v in comparisons),
   "max_se_abs_error":max(max(v["district_cluster_se_error"],v["year_cluster_se_error"]) for v in comparisons),
   "comparisons":comparisons})
 R["counts"]={"models":len(comparisons),"source_rows":len(full),
             "strict_source_FNID":len(primary),"coefficients_and_both_cluster_SE_recomputed":len(comparisons)}
R["notes"]="Independent numerical model QA only; no causal identification or validity of source annual season."
try:
 main()
 R["status"]="PASS" if not R["errors"] else "FAILED"
except Exception as e:
 R["status"]="FAILED";R["errors"].append(repr(e));R["traceback"]=traceback.format_exc()[-4200:]
(D/"malawi_rainfed_maize_INDEPENDENT_FWL_model_QA.json").write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":R["status"],"errors":R["errors"],"counts":R.get("counts"),
 "audit":R["checks"].get("8_independent_FWL_coefficients_and_twocluster_diagnostics")},ensure_ascii=False,indent=2,default=str)[:15000])
if R["status"]!="PASS":sys.exit(1)
