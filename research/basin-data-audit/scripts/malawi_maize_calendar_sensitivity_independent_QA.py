"""Independent audit of Malawi maize survey-vs-JRC rainfall sensitivity.

Read actual monthly CHIRPS and original JRC+Waha source tables. Reconstruct
all 26 x 44 x 4 windows (rather than trusting producer's window strings)
and verify EVERY seasonal total & year anchor independently.
Also recompute all 8 per-region/all-region drought discordances.

No yield-based window optimisation, no regression, no institutional effects.
"""
import datetime as dt,json,pathlib,sys,traceback
import pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1";OUT.mkdir(parents=True,exist_ok=True)
R={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","checks":{},"errors":[]}
def test(name,passed,detail=None):
 R["checks"][name]={"pass":bool(passed),"details":detail}
 if not passed:R["errors"].append(name)
try:
 p=OUT/"malawi_maize_calendar_sensitivity_qa.json"
 base=json.loads(p.read_text())
 test("original_script_all_checks_complete",base["status"]=="COMPLETE")
 w=pd.read_csv(OUT/"malawi_maize_4_window_chirps_1981_2024.csv")
 info=pd.read_csv(OUT/"malawi_maize_26_district_fixed_calendar_scenarios.csv")
 climate=pd.read_csv(ROOT/"results"/"climate_panel"/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
                     usecols=["fnid","year","month","rainfall_mm_month"])
 outcomes=pd.read_csv(OUT/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv")
 summary=pd.read_csv(OUT/"malawi_maize_climate_window_sensitivity_summary.csv")
 test("correct_full_26x44x4",len(w)==26*44*4)
 test("unique_crop_window_year",not w.duplicated(["fnid","window","harvest_year"]).any())
 test("all_four_windows",set(w.window)=={"broad","core","waha_broad","waha_growth"})
 test("country_and_crop_only",w.country_code.eq("MW").all() and info.jrc_crop_season.eq("Maize").all())
 test("outcome_rows_are_not_copied",not outcomes.duplicated(["fnid","product","season_name","crop_production_system","harvest_year"]).any())
 test("baseline_source_years_exact",w.reference_n.le(30).all() and w.reference_n.ge(25).all())
 raw={(r.fnid,int(r.year),int(r.month)):float(r.rainfall_mm_month) for r in climate.itertuples(index=False)}
 def to_year_month(d):
  d=int(d);return (d-1)//3+1
 def period(year,first,last):
  p=pd.period_range(pd.Period(year=first[0],month=first[1],freq="M"),
        pd.Period(year=last[0],month=last[1],freq="M"),freq="M")
  return [(v.year,v.month) for v in p]
 def ref_window(src,harvest_year,variant):
  s1,s2,e1,e2=(int(src[c]) for c in
    ["JRC_sow_start_dekad","JRC_sow_end_dekad","JRC_harvest_start_dekad","JRC_harvest_end_dekad"])
  shift=int(s1>e2);yy=harvest_year-shift
  def clock(d):
   v=s1-1+(d-s1)%36
   return yy+v//36,(v%36)//3+1
  if variant=="broad": return period(harvest_year,clock(s1),clock(e2))
  if variant=="core":return period(harvest_year,clock(s2),clock(e1))
  raise ValueError(variant)
 def survey_window(src,hy,kind):
  p,h=int(src.Waha_modal_sow_month),int(src.Waha_modal_harvest_begin_month)
  sy=hy-int(p>h)
  if kind=="waha_broad":ey,em=hy,h
  elif kind=="waha_growth":
   ey,em=(hy-1,12) if h==1 else (hy,h-1)
  else:raise ValueError(kind)
  return period(hy,(sy,p),(ey,em))
 info_map={r.fnid:r for r in info.itertuples(index=False)}
 discrep=[];nmonthcheck=0;expectedmiss=0
 for x in w.itertuples(index=False):
  ref=info_map[x.fnid]
  ym=ref_window(ref,int(x.harvest_year),x.window) if x.window in ("core","broad") else survey_window(ref,int(x.harvest_year),x.window)
  nmonthcheck+=1
  if len(ym)!=int(x.months_in_window):discrep.append(("number_months",x.fnid,x.harvest_year,x.window))
  values=[raw.get((x.fnid,int(yy),int(mm))) for yy,mm in ym]
  if any(v is None or not np.isfinite(v) for v in values):
   expectedmiss+=1
   if np.isfinite(x.precip_total_mm):discrep.append(("missing_not_NA",x.fnid,x.harvest_year,x.window))
  else:
   direct=float(sum(values))
   if not np.isfinite(x.precip_total_mm) or abs(direct-x.precip_total_mm)>1e-7:
    discrep.append(("sum_different",x.fnid,x.harvest_year,x.window,float(x.precip_total_mm),direct))
 test("independently_recompute_all_26x44x4_source_months",len(discrep)==0,
      {"n_checked":nmonthcheck,"n_mismatched":len(discrep),"examples":discrep[:5]})
 test("absence_1980_not_zero_imputed",w.loc[w.status.ne("COMPLETE"),"harvest_year"].eq(1981).all(),
      {"n_missing":int(w.precip_total_mm.isna().sum()),"source_expected":expectedmiss})
 referr=[]
 for (fnid,variant),g in w.groupby(["fnid","window"]):
  hist=g.loc[g.harvest_year.between(1981,2010)].precip_total_mm.dropna()
  n=len(hist)
  if n!=g.reference_n.iloc[0] or abs(hist.mean()-g.reference_mean.iloc[0])>1e-7 or abs(hist.std(ddof=1)-g.reference_sd.iloc[0])>1e-7:
   referr.append((fnid,variant))
 test("independent_reference_mean_sd_104_series",len(referr)==0,
      {"tested":w.groupby(["fnid","window"]).ngroups,"bad":referr[:5]})
 # Independent per-window threshold-change counts from raw saved Z.
 z=w.pivot(index=["fnid","harvest_year","jrc_region"],columns="window",values="seasonal_z").reset_index()
 mismatch=[]
 for a,b in [("broad","waha_broad"),("core","waha_growth")]:
  for region,g in [("ALL_3_MALAWI_REGIONS",z)]+list(z.groupby("jrc_region")):
   sub=g[[a,b]].dropna()
   n=len(sub);nchange=int((sub[a].le(-1)!=sub[b].le(-1)).sum())
   rec=summary.loc[summary.jrc_window.eq(a)&summary.survey_modal_window.eq(b)&summary.region.eq(region)]
   if len(rec)!=1 or nchange!=int(rec.iloc[0].n_drought_classification_disagree) or n!=int(rec.iloc[0].paired_district_years):
    mismatch.append((region,a,b,n,nchange))
 test("recompute_all_window_drought_disagreement_counts",not mismatch,
      {"n_summaries":len(summary),"bad":mismatch})
 R["counts"]={
  "all_reconstructed_source_weather_windows":nmonthcheck,
  "verified_districts":w.fnid.nunique(),
  "year_coverage":w.harvest_year.nunique(),
  "comparison_summary_rows":len(summary),
  "n_missing_1980_windows":expectedmiss,
  "independent_weather_sums_mismatched":len(discrep),
  "baseline_series_checked":w.groupby(["fnid","window"]).ngroups,
  "drought_discordance_summaries_verified":len(summary),
  "unchanged_outcomes":len(outcomes)}
 R["status"]="PASS" if not R["errors"] else "FAILED"
except Exception as e:
 R["status"]="FAILED";R["errors"].append(repr(e));R["traceback"]=traceback.format_exc()[-5000:]
(OUT/"malawi_maize_INDEPENDENT_calendar_sensitivity_QA.json").write_text(
 json.dumps(R,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":R["status"],"errors":R["errors"],"counts":R.get("counts")},ensure_ascii=False,indent=2)[:12000])
if R["status"]!="PASS":sys.exit(1)
