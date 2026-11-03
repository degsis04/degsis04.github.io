"""Conservative secondary QA: Separate truly observed irrigated rice from general/rainfed series.

Never label aggregate 'All (PS)' or 'none' as irrigation observations.
A threshold of 8 real valid years & 6 consecutive yrs is a small-N PILOT
eligibility screen; not causal identification or sufficient econometric power.
"""
import pathlib,json,datetime as dt,re,traceback,sys,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
IN=ROOT/"results"/"rice_feasibility"
OUT=IN
report={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "criterion":"Directly classified irrigated Rice series with >=8 harvest years and longest 6+ contiguous harvest years; source PS labels not automatically equivalent to scheme/canal irrigation"}
try:
 s=pd.read_csv(IN/"rice_district_season_observed_series.csv")
 a=pd.read_csv(IN/"rice_district_feasibility_screen.csv")
 assert not s.duplicated(["fnid","season_name","crop_production_system"]).any()
 def cls(v):
  v=str(v).casefold()
  if "rainfed" in v or "rain-fed" in v or "pluvial" in v:return "explicit_rainfed"
  if "irrigat" in v:return "explicit_irrigated_broad"
  if v in ("all (ps)","all","none","nan","unspecified"):return "aggregate_or_unclassified"
  return "other_unverified"
 s["outcome_system_class"]=s.crop_production_system.map(cls)
 s["irrigated_series_8y_6consecutive"]=(
   s.outcome_system_class.eq("explicit_irrigated_broad")&
   s.valid_years.ge(8)&s.longest_consecutive.ge(6))
 s.to_csv(OUT/"rice_series_production_system_audit.csv",index=False)
 stats={}
 for label,g in s.groupby("outcome_system_class"):
  stats[label]={"series":len(g),"districts":int(g.fnid.nunique()),
   "series_8yr_6continuous":int(((g.valid_years>=8)&(g.longest_consecutive>=6)).sum())}
 exposed=a.loc[a.potential_irrigated_rice_10pct_100ha].copy()
 direct=s.loc[s.irrigated_series_8y_6consecutive].copy()
 directfn=set(direct.fnid)
 exposed["has_direct_irrigated_rice_yield_series_8years"]=exposed.fnid.isin(directfn)
 exposed["has_long_aggregate_rice_series_only_or_in_addition"]=exposed.fnid.isin(
    s.loc[(s.outcome_system_class.eq("aggregate_or_unclassified"))&(s.valid_years>=10)&(s.longest_consecutive>=6),"fnid"])
 exposed["has_long_explicit_rainfed_series"]=exposed.fnid.isin(
    s.loc[(s.outcome_system_class.eq("explicit_rainfed"))&(s.valid_years>=10)&(s.longest_consecutive>=6),"fnid"])
 exposed["2020_source_area_ha_not_outcome_direct"]=True
 exposed.to_csv(OUT/"irrigation_exposed_districts_outcome_type.csv",index=False)
 report["all_rice_season_system_count_by_class"]=stats
 report["irrigation_exposed_districts_n"]=len(exposed)
 report["exposed_with_observed_8yr_irrigated_outcome"]=int(exposed.has_direct_irrigated_rice_yield_series_8years.sum())
 report["exposed_with_long_aggregate_outcome"]=int(exposed.has_long_aggregate_rice_series_only_or_in_addition.sum())
 report["exposed_with_long_rainfed_outcome"]=int(exposed.has_long_explicit_rainfed_series.sum())
 report["exposed_direct_by_basin"]={str(k):int(v) for k,v in
   exposed.loc[exposed.has_direct_irrigated_rice_yield_series_8years].groupby("BCODE").size().items()}
 report["direct_pilot_districts"]=exposed.loc[exposed.has_direct_irrigated_rice_yield_series_8years,
   ["fnid","adm_admin_1","adm_admin_2","BCODE","irrigated_ha","fraction_irrigated"]].to_dict("records")
 report["warnings"]=[
   "Burkina source label 'Plaine/Bas-fond irrigated (PS)' can include bottomland/floodplain systems; exact canal source unverified",
   "MIRCA 2020 irrigation exposure is not a pretreatment treatment-status observation for outcomes before 2020",
   "Long rainfed series do not measure irrigated rice responsiveness",
   "All (PS) and none categories have unknown irrigation split; 39-year Mali data are mixed-production outcomes",
   "No proof any international water treaty changes a scheme's actual access to water"]
 report["status"]="COMPLETE"
except Exception as e:
 report["status"]="FAILED";report["error"]=str(e)[:400];report["traceback"]=traceback.format_exc()[-2500:]
(OUT/"rice_production_system_qa.json").write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+"\n")
print(json.dumps(report,indent=2,ensure_ascii=False,default=str)[:9000])
if report["status"]!="COMPLETE":sys.exit(1)
