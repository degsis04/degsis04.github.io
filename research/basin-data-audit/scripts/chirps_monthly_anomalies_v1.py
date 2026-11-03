"""Cross-shard verification + monthly climatology of CHIRPS v3 final precipitation.

Derived monthly and 3-/6-month anomalies, only once all four 1981–2024
source-verified district precipitation shards are available. Baseline: 1981–2010,
calendar-month-specific, independently calculated for each district.
This is *local weather*, not upstream naturalized flow, actual crop-season
weather, or the effect of governance.
"""
import datetime as dt,json,pathlib,sys,traceback
import pandas as pd,numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"climate_panel";OUT.mkdir(parents=True,exist_ok=True)
SHARDS=["1981_1991","1992_2002","2003_2013","2014_2024"]
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),
     "product":"CHIRPS v3 final rain 253 HarvestStat districts 1981-2024",
     "status":"STARTED","errors":[],"warnings":[
     "Monthly rainfall is local district exposure, not irrigation-water supply, upstream routed runoff, or crop-specific phenology.",
     "Calendar-month anomalies are descriptive; rainfall dependence on crop stage must be separately verified.",
     "District raster-cell center approach leaves boundary error, especially small polygons and irrigated areas.",
     "For very dry months, z scores can be unstable: require baseline rainfall sd>=5 mm; otherwise NA."
     ]}
def save(): (OUT/"full_climate_monthly_qa.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
try:
 panels=[]
 for name in SHARDS:
  p=OUT/f"chirps_provenance_{name}.json"
  csv=OUT/f"chirps_v3_district_monthly_{name}.csv"
  if not p.exists() or not csv.exists():
   LOG["status"]="WAITING_FOR_SHARDS"
   LOG["errors"].append(f"Not yet computed: {name}")
   break
  provenance=json.loads(p.read_text())
  if provenance["status"]!="COMPLETE":
   LOG["status"]="BLOCKED_BY_FAILED_SHARD"
   LOG["errors"].append(f"Failed source QA shard {name}: {provenance.get('errors')}")
   break
  t=pd.read_csv(csv)
  if t["rainfall_mm_month"].dropna().lt(0).any():
   raise ValueError(f"Negative rain in shard {name}")
  if t.duplicated(["fnid","year","month"]).any():
   raise ValueError(f"Repeated district/year/month in shard {name}")
  expected=provenance["counts"]["districts"]*provenance["counts"]["months"]
  if len(t)!=expected:raise ValueError(f"bad rows {name}")
  if len(provenance["source_file_hashes"])!=1+provenance["counts"]["months"]:
   raise ValueError(f"missing source hashes for shard {name}")
  panels.append(t)
 if LOG["status"]=="STARTED":
  a=pd.concat(panels,ignore_index=True)
  assert not a.duplicated(["fnid","year","month"]).any()
  assert a.fnid.nunique()==253
  assert a.year.nunique()==44 and set(a.year)==set(range(1981,2025))
  assert len(a)==253*44*12,(len(a),253*44*12)
  assert a.groupby("fnid").size().eq(44*12).all()
  assert a.groupby(["fnid","month"]).size().eq(44).all()
  a=a.sort_values(["fnid","year","month"]).reset_index(drop=True)
  a["rainfall_mm_month"]=pd.to_numeric(a.rainfall_mm_month,errors="coerce")
  a["dry_month_low_support"]=a["valid_grid_cell_centres"].lt(3)
  a["rainfall_3m_mm"]=a.groupby("fnid")["rainfall_mm_month"].transform(lambda s:s.rolling(3,min_periods=3).sum())
  a["rainfall_6m_mm"]=a.groupby("fnid")["rainfall_mm_month"].transform(lambda s:s.rolling(6,min_periods=6).sum())
  monthly_stats=[]
  for variable in ["rainfall_mm_month","rainfall_3m_mm","rainfall_6m_mm"]:
   baseline=a.loc[a.year.between(1981,2010)].groupby(["fnid","month"])[variable].agg(
         baseline_n="count",baseline_mean="mean",baseline_std="std").reset_index()
   baseline.columns=["fnid","month",f"{variable}_n_ref",f"{variable}_mean_ref",f"{variable}_sd_ref"]
   a=a.merge(baseline,on=["fnid","month"],how="left",validate="many_to_one")
   mean=a[f"{variable}_mean_ref"]
   stdev=a[f"{variable}_sd_ref"]
   n=a[f"{variable}_n_ref"]
   okay=n.ge(25)&stdev.ge(5)&a.valid_grid_cell_centres.ge(3)
   a[f"{variable}_anom_mm"]=a[variable]-mean
   a[f"{variable}_z"]=np.where(okay,(a[variable]-mean)/stdev,np.nan)
   a[f"{variable}_deficit_z"]=np.where(a[f"{variable}_z"].notna(),
                                    np.maximum(-a[f"{variable}_z"],0),np.nan)
   monthly_stats.append({"variable":variable,
      "valid_standardized_values":int(a[f"{variable}_z"].notna().sum()),
      "missing_or_unstable_values":int(a[f"{variable}_z"].isna().sum()),
      "n_reference_histograms":int(len(baseline))})
  if a.rainfall_mm_month.dropna().lt(0).any():raise ValueError("negative precipitation")
  a.to_csv(OUT/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",index=False)
  LOG["status"]="COMPLETE"
  LOG["counts"]={"rows":len(a),"districts":a.fnid.nunique(),
    "distinct_months":a[["year","month"]].drop_duplicates().shape[0],
    "missing_rain_values":int(a.rainfall_mm_month.isna().sum()),
    "raw_months_by_year":a.groupby("year")["month"].nunique().to_dict(),
    "anomaly_series":monthly_stats,
    "baseline":"1981-2010 per district, calendar ending month"}
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(repr(e))
 LOG["traceback"]=traceback.format_exc()[-6000:]
finally:
 save();print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],
                         "counts":LOG.get("counts")},indent=2,ensure_ascii=False)[:10000])
if LOG["status"]=="FAILED":sys.exit(1)
