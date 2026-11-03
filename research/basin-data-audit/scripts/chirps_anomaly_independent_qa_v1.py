"""Independent consistency tests on full CHIRPS 1981–2024 climatic panel.

Checks dimensions, completeness, climatology parameters and cross-year rolling
window arithmetic without downloading any new source data.
"""
import datetime as dt,json,pathlib,sys,traceback
import pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/"results"/"climate_panel"
Q=ROOT/"results"/"climate_validation"
Q.mkdir(parents=True,exist_ok=True)
L={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","checks":{},"errors":[]}
def c(key,passed,info=None):
 L["checks"][key]={"pass":bool(passed),"info":info}
 if not passed:L["errors"].append(key)
try:
 prov=json.loads((P/"full_climate_monthly_qa.json").read_text())
 c("initial_anomaly_QA_complete",prov["status"]=="COMPLETE")
 a=pd.read_csv(P/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv")
 c("expected_record_count",len(a)==253*44*12,len(a))
 c("panel_keys_unique",not a.duplicated(["fnid","year","month"]).any())
 c("source_months_full",a.year.nunique()==44 and a.groupby(["fnid","year"]).month.nunique().eq(12).all())
 c("source_grid_no_missing_precipitation",a.rainfall_mm_month.notna().all())
 c("source_no_negative_precipitation",a.rainfall_mm_month.ge(0).all())
 c("source_all_finite_rain",np.isfinite(a.rainfall_mm_month).all())
 c("no_future_baseline_leakage",a["rainfall_mm_month_n_ref"].max()<=30)
 c("month_specific_historical_mean",a.loc[a.year.between(1981,2010)].groupby(["fnid","month"]).rainfall_mm_month.count().min()==30)
 c("positive_or_undefined_clim_std",a["rainfall_mm_month_sd_ref"].ge(0).all())
 # Independent per month-climatology comparison to stored production data
 first=a.loc[a.fnid.eq(a.fnid.iloc[0])].copy()
 for mm in [1,4,7,10]:
  b=first.loc[first.month.eq(mm)&first.year.between(1981,2010)]
  mu=b.rainfall_mm_month.mean()
  sigma=b.rainfall_mm_month.std(ddof=1)
  stored=b.rainfall_mm_month_mean_ref.iloc[0]
  storedstd=b.rainfall_mm_month_sd_ref.iloc[0]
  c(f"independent_climatology_{mm}",abs(mu-stored)<1e-8 and abs(sigma-storedstd)<1e-8,
    {"month":mm,"observed":mu,"stored":stored,"sd_observed":sigma,"sd_stored":storedstd})
 # Independent arithmetic rolling sums for four selected districts / monthly periods, incl across new year
 sampleIDs=sorted(a.fnid.unique())[:4]
 tmp=a.loc[a.fnid.isin(sampleIDs)].sort_values(["fnid","year","month"]).copy()
 independent3=tmp.groupby("fnid").rainfall_mm_month.transform(lambda v:v.rolling(3,min_periods=3).sum())
 independent6=tmp.groupby("fnid").rainfall_mm_month.transform(lambda v:v.rolling(6,min_periods=6).sum())
 c("independent_3month_roll",bool(np.allclose(independent3,tmp.rainfall_3m_mm,equal_nan=True,atol=1e-7)))
 c("independent_6month_roll",bool(np.allclose(independent6,tmp.rainfall_6m_mm,equal_nan=True,atol=1e-7)))
 # Check months that cannot have complete 1981 reference rolling windows
 c("first_1981_two_3month_windows_missing",tmp.loc[tmp.year.eq(1981)&tmp.month.isin([1,2]),"rainfall_3m_mm"].isna().all())
 c("first_1981_five_6month_windows_missing",tmp.loc[tmp.year.eq(1981)&tmp.month.le(5),"rainfall_6m_mm"].isna().all())
 for name in ["rainfall_mm_month","rainfall_3m_mm","rainfall_6m_mm"]:
  z=a[f"{name}_z"]
  deficit=a[f"{name}_deficit_z"]
  c(f"{name}_drought_severity_nonnegative",deficit.dropna().ge(0).all())
  c(f"{name}_z_and_deficit_missing_same",z.isna().eq(deficit.isna()).all())
  c(f"{name}_no_invalid_z",np.isfinite(z.dropna()).all())
 L["summary"]={
  "n_rows":len(a),
  "districts":a.fnid.nunique(),
  "source_rain_min_mm":float(a.rainfall_mm_month.min()),
  "source_rain_max_mm":float(a.rainfall_mm_month.max()),
  "n_month_z":int(a.rainfall_mm_month_z.notna().sum()),
  "n_3mo_z":int(a.rainfall_3m_mm_z.notna().sum()),
  "n_6mo_z":int(a.rainfall_6m_mm_z.notna().sum()),
  "baseline":"1981-2010",
  "n_low_support":int(a.dry_month_low_support.sum())}
 L["status"]="PASS" if not L["errors"] else "FAIL"
except Exception as ex:
 L["status"]="FAIL";L["errors"].append(repr(ex));L["traceback"]=traceback.format_exc()[-7000:]
(Q/"anomaly_independent_numerical_qa.json").write_text(json.dumps(L,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps(L,ensure_ascii=False,indent=2)[:13000])
if L["status"]!="PASS":sys.exit(1)
