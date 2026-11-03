"""Independent QA for JRC-defined CHIRPS crop-season precipitation totals.

Independent month range generation: pandas PeriodIndex from stored
year-month start/end, not the producer's original modulo-dekad routine.
Verifies 8 predetermined country/season samples, 2 window definitions, 4
harvest years; baseline statistics and missing 1980 months.
"""
import datetime as dt,json,pathlib,sys,traceback
import pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
SEASON=ROOT/"results"/"seasonal_climate_v1"
CLIMATE=ROOT/"results"/"climate_panel"
REPORT={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
        "checks":{},"errors":[],"sample":[]}
def check(label,condition,info=None):
 REPORT["checks"][label]={"pass":bool(condition),"details":info}
 if not condition:REPORT["errors"].append(label)
try:
 official=json.loads((SEASON/"seasonal_climate_provenance.json").read_text())
 assert official["status"]=="COMPLETE"
 s=pd.read_csv(SEASON/"JRC_crop_season_CHIRPS_1981_2024.csv")
 c=pd.read_csv(CLIMATE/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
               usecols=["fnid","year","month","rainfall_mm_month"])
 c["period"]=pd.PeriodIndex(year=c.year,month=c.month,freq="M")
 lookup=c.set_index(["fnid","period"]).rainfall_mm_month
 check("source_rows_29744",len(s)==29744,len(s))
 check("all_raw_nonneg",s.precip_total_mm.dropna().ge(0).all())
 check("1981_missing_only_anchored_full_crop_cycle",
       s.loc[s.window_data_status.ne("COMPLETE"),"harvest_year"].eq(1981).all() and
       s.loc[s.window_data_status.ne("COMPLETE"),"full_crop_cycle_crosses_year"].all(),
       {"n_missing":int(s.window_data_status.ne("COMPLETE").sum())})
 check("weather_years_44",set(s.harvest_year)==set(range(1981,2025)))
 # Independent FULL SEASON anchor check. A core window can be entirely in
 # preceding calendar year even when it does not itself cross December.
 sos=s.JRC_sos_start_dekad.astype(int)
 d0=s.JRC_sos_end_dekad.astype(int);d1=s.JRC_eos_start_dekad.astype(int)
 cropcross=s.JRC_eos_end_dekad.astype(int).lt(sos)
 core=s.loc[s.window.eq("core")].copy()
 anchor=s.loc[s.window.eq("core"),"harvest_year"].astype(int) - cropcross.loc[core.index].astype(int)
 expected_from_year=anchor + d0.loc[core.index].lt(sos.loc[core.index]).astype(int)
 expected_to_year=anchor + d1.loc[core.index].lt(sos.loc[core.index]).astype(int)
 check("independent_anchor_start_year_all_core_rows",bool(core.from_year.astype(int).eq(expected_from_year).all()),
       {"n_checked":len(core),"n_bad":int((~core.from_year.astype(int).eq(expected_from_year)).sum())})
 check("independent_anchor_end_year_all_core_rows",bool(core.to_year.astype(int).eq(expected_to_year).all()),
       {"n_checked":len(core),"n_bad":int((~core.to_year.astype(int).eq(expected_to_year)).sum())})
 gh=s.loc[(s.country_code=="GH") & (s.jrc_crop_season=="Maize (Second)") &
          s.window.eq("core")&s.harvest_year.eq(2020)]
 check("ghana_second_maize_growth_2020_must_be_2019",bool(len(gh)>0 and
       gh.from_year.eq(2019).all() and gh.to_year.eq(2019).all()),
       {"n_checked":len(gh)})
 ml=s.loc[(s.country_code=="ML")&(s.jrc_crop_season=="Rice (Rainfed)") &
          s.window.eq("core")&s.harvest_year.eq(2020)&s.full_crop_cycle_crosses_year]
 check("mali_season_rice_growth_2020_must_be_2019",bool(len(ml)>0 and
       ml.from_year.eq(2019).all() and ml.to_year.eq(2019).all()),
       {"n_checked":len(ml)})
 check("one_per_source_season_year_window",not s.duplicated(["fnid","jrc_crop_season","window","harvest_year"]).any())
 selected=[]
 for cc in sorted(s.country_code.unique()):
  z=s.loc[s.country_code.eq(cc)]
  # Deterministic: prefer a cross-year season if present, else first stable season.
  cross=z.loc[z.crosses_calendar_year].sort_values(["fnid","crop","jrc_crop_season","window"])
  one=(cross if len(cross) else z).iloc[0]
  selected.append((cc,one.fnid,one.jrc_crop_season))
 for cc,fnid,season in selected:
  for win in ["core","broad"]:
   for hy in [1981,1990,2000,2020,2024]:
    q=s.loc[s.fnid.eq(fnid)&s.jrc_crop_season.eq(season)&s.window.eq(win)&s.harvest_year.eq(hy)]
    assert len(q)==1,(cc,fnid,season,win,hy,len(q))
    z=q.iloc[0]
    date1=pd.Period(year=int(z.from_year),month=int(z.from_month),freq="M")
    date2=pd.Period(year=int(z.to_year),month=int(z.to_month),freq="M")
    months=pd.period_range(date1,date2,freq="M")
    obs=[float(lookup.loc[(fnid,m)]) if (fnid,m) in lookup.index else np.nan for m in months]
    recalculated=sum(obs) if all(np.isfinite(obs)) else np.nan
    if np.isnan(recalculated):
     pass_test=np.isnan(z.precip_total_mm)
    else:
     pass_test=abs(recalculated-z.precip_total_mm)<.0000001
    REPORT["sample"].append({"country":cc,"fnid":fnid,"crop":season,"year":hy,"window":win,
     "from":str(date1),"to":str(date2),
     "n_months":len(months),"source_recorded_n_months":int(z.months_window),
     "recalculated_mm":float(recalculated) if np.isfinite(recalculated) else None,
     "stored_mm":float(z.precip_total_mm) if np.isfinite(z.precip_total_mm) else None,
     "is_equal":bool(pass_test)})
 check("independent_arithmetic_match_all_examples",
       all(q["is_equal"] for q in REPORT["sample"]),
       {"n":len(REPORT["sample"]),"failed":[r for r in REPORT["sample"] if not r["is_equal"]][:4]})
 check("season_month_count_independent",
       all(q["n_months"]==q["source_recorded_n_months"] for q in REPORT["sample"]))
 # independently calculate 1981-2010 reference mean/std for the selected crop-season windows
 btest=[]
 for _,q in s.groupby(["fnid","jrc_crop_season","window"]):
  if not any((q.fnid.iloc[0]==f and q.jrc_crop_season.iloc[0]==se) for _,f,se in selected):continue
  hist=q.loc[q.harvest_year.between(1981,2010)&q.window_data_status.eq("COMPLETE")]
  if hist.empty:continue
  a=hist.precip_total_mm.mean();sd=hist.precip_total_mm.std(ddof=1);n=len(hist)
  stored=hist.iloc[0]
  btest.append({"n":n,"mean_diff":abs(a-stored.baseline_mean_mm),
        "std_diff":abs(sd-stored.baseline_sd_mm),
        "n_matches":n==stored.baseline_count})
 check("independent_baseline_recalculation",
       all(x["mean_diff"]<1e-7 and x["std_diff"]<1e-7 and x["n_matches"] for x in btest),
       {"tested":len(btest),"max_mean_diff":max(x["mean_diff"] for x in btest),
        "max_std_diff":max(x["std_diff"] for x in btest)})
 REPORT["countries_validated"]=sorted(s.country_code.unique().tolist())
 REPORT["total_checks"]=len(REPORT["sample"])
 REPORT["status"]="PASS" if not REPORT["errors"] else "FAILED"
except Exception as e:
 REPORT["status"]="FAILED";REPORT["errors"].append(str(e)[:500])
 REPORT["traceback"]=traceback.format_exc()[-3000:]
(SEASON/"seasonal_climate_independent_QA.json").write_text(json.dumps(REPORT,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":REPORT["status"],"errors":REPORT["errors"],"countries":REPORT.get("countries_validated"),
 "sample_checks":REPORT.get("total_checks"),"checks":REPORT.get("checks")},ensure_ascii=False,indent=2)[:11000])
if REPORT["status"]!="PASS":sys.exit(1)
