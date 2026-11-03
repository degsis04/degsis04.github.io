"""Exploratory weather-yield association for Malawi maize, NOT treaty effects.

Pre-specified sample: HarvestStat v1.2 Malawi Maize, season Main, production
system Rainfed (PS) ONLY. Two samples: all 23 observed source districts
(n=812 rows), vs 16 districts with >=30 source years and <=5% within-span
missing years. NO Annual / All, no unflagged >10 t/ha values (those are
Annual / All anyway). No data-driven sample changes.

For each of four PREDEFINED crop calendar windows (JRC broad/core,
independent Waha broad/growth), fit log(yield) ~ precip_z + FNID FE + year FE.
Report descriptive association, standard error clustered by district and
by harvest year separately, and finite district leave-one-out diagnostics.
Not a causal effect of rainfall; no institutional variable or hydrology.
"""
import datetime as dt,json,pathlib,sys,traceback
import pandas as pd,numpy as np,statsmodels.formula.api as smf
from scipy.stats import t as student_t
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"results"
OUT=BASE/"malawi_rainfed_weather_yield_v1";OUT.mkdir(parents=True,exist_ok=True)
Y=BASE/"malawi_maize_calendar_sensitivity_v1"/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv"
ELIG=BASE/"malawi_maize_semantics_v1"/"main_rainfed_only_district_eligibility.csv"
QA_PRI=BASE/"malawi_maize_semantics_v1"/"Malawi_915_primary_original_source_QA.json"
QA_SEC=BASE/"malawi_maize_semantics_v1"/"Malawi_915_INDEPENDENT_standard_library_QA.json"
WINDOWS=["broad","core","waha_broad","waha_growth"]
R={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "sources":{"yield":str(Y.relative_to(ROOT)),"eligibility":str(ELIG.relative_to(ROOT)),
 "original_HarvestStat_QA":str(QA_PRI.relative_to(ROOT)),
 "independent_HarvestStat_QA":str(QA_SEC.relative_to(ROOT))},
 "design":{"study":"Weather and rainfed maize yield association, Malawi, one cross-border Zambezi country only",
 "source_outcome":"log(yield tonne per hectare), 1983-2020, Main and Rainfed (PS) only",
 "weather_z":"CHIRPS v3 actual district precipitation sum standardized versus each window's 1981–2010 reference",
 "prior_windows":WINDOWS,"primary_sample":"16 FNIDs selected for >=30 observed years, <=5% gaps before regression",
 "secondary_sample":"all 23 source FNIDs, sample stability",
 "main_model":"OLS log(yield) ~ window_z + categorical district FE + categorical harvest-year FE",
 "standard_errors":"district-clustered and year-clustered as separate small-sample sensitivity diagnostics",
 "core_relevance":"district rainfall / rainfed output, not upstream flow, treaty treatment or irrigated crops",
 "deliberately_no_institutions":True,
 "one_rainfall_unit":"+1 within-FNID/window standardized seasonal rainfall unit",
 "pvalue_policy":"descriptive, exploratory; district clusters only 16, p values not confirmatory"},
 "caveats":["Malawi's observed Main/Rainfed series predates Annual/All coding break.",
 "District rainfall is spatially correlated, 16 district clusters few; cluster-robust t with df=#clusters-1 exploratory.",
 "With district+year fixed effects, identification uses relative within-year district anomalies; shared national drought variation is absorbed.",
 "Year-indexed harvest may not be exact biological maize harvest year.",
 "Crop areas and yields come from harmonized FEWSNET records, not field-level repeated measurement.",
 "Rainfall/yield contemporaneous does not establish causal precipitation effect (other covarying interventions possible).",
 "Mali, Malawi, Niger/Volta institutions cannot be evaluated with a single-country rainfed maize regression.",
 "Do not select climate calendar or sample based on preferred coefficient/p-value."],
 "checks":{},"errors":[]}
def chk(name,ok,details=None):
 R["checks"][name]={"pass":bool(ok),"details":details}
 if not ok:R["errors"].append(name)
try:
 assert json.loads(QA_PRI.read_text())["status"]=="PASS"
 assert json.loads(QA_SEC.read_text())["status"]=="PASS"
 a=pd.read_csv(Y,low_memory=False); e=pd.read_csv(ELIG)
 chk("original_915_rows",len(a)==915,len(a))
 chk("original_strata_main_rainfed_812",len(a.loc[(a.season_name=="Main")&(a.crop_production_system=="Rainfed (PS)")])==812)
 elig=e.loc[e.strict_30year_5pct_gaps.eq(True)].fnid.unique().tolist()
 chk("prior_years_eligible_16_districts",len(elig)==16,elig)
 sub=a.loc[(a["product"]=="Maize")&(a.season_name=="Main")&
           (a.crop_production_system=="Rainfed (PS)")].copy()
 chk("all_sub_qc0_and_plausible",sub.qc_flag.eq(0).all() and
     sub["yield"].between(.01,10).all(),{"n":len(sub),"min":float(sub["yield"].min()),"max":float(sub["yield"].max())})
 chk("source_MW_maize_1983_2020",sub.harvest_year.min()==1983 and sub.harvest_year.max()==2020)
 chk("no_duplicated_outcome_key",not sub.duplicated(["fnid","harvest_year"]).any())
 chk("rainfall_all_four_completely_observed",sub[WINDOWS].notna().all().all())
 sub["log_yield"]=np.log(sub["yield"])
 sub["in_primary_16"]=sub.fnid.isin(elig)
 sub["reporting_category"]="Main | Rainfed (PS)"
 sub["phenology_field_verified"]=False
 sub["institutional_causal_effect_inferred"]=False
 sub["rainfall_hydrology_verified"]=False
 cols=["fnid","harvest_year","jrc_region","yield","area","production","log_yield",
       "in_primary_16"]+WINDOWS
 sub[cols].sort_values(["fnid","harvest_year"]).to_csv(
   OUT/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv",index=False)
 
 rows=[];delete=[]
 for cohort,panel in [("strict16",sub.loc[sub.in_primary_16].copy()),("all23",sub.copy())]:
  for window in WINDOWS:
   data=panel.copy()
   # In statsmodels formula, use the same *unnamed* regressor, eliminating
   # chance of accidentally swapping different window names in output.
   data["shock_z"]=data[window]
   fm=smf.ols("log_yield ~ shock_z + C(fnid) + C(harvest_year)",data=data)
   base=fm.fit()
   d=base.get_robustcov_results(cov_type="cluster",groups=data["fnid"],use_correction=True)
   y=base.get_robustcov_results(cov_type="cluster",groups=data["harvest_year"],use_correction=True)
   idx=list(base.params.index).index("shock_z")
   beta=float(base.params["shock_z"])
   std_d=float(d.bse[idx]);std_y=float(y.bse[idx])
   # Finite-cluster p approximations: separate, no overclaim of nominal coverage.
   G=data.fnid.nunique();T=data.harvest_year.nunique()
   pdist=float(2*student_t.sf(abs(beta/std_d),df=G-1)) if std_d>0 else None
   pyear=float(2*student_t.sf(abs(beta/std_y),df=T-1)) if std_y>0 else None
   r={"sample":cohort,"window":window,"n_rows":len(data),
      "n_fnids":G,"n_harvest_years":T,"min_harvest_year":int(data.harvest_year.min()),
      "max_harvest_year":int(data.harvest_year.max()),
      "beta_log_yield_per_plus_1_z":beta,
      "exp_beta_minus_one_pct":100*float(np.expm1(beta)),
      "district_cluster_se":std_d,"year_cluster_se":std_y,
      "t_cluster_district_dfGminus1_p_EXPLORATORY":pdist,
      "t_cluster_year_dfTminus1_p_EXPLORATORY":pyear,
      "r2_including_all_FE":float(base.rsquared),
      "condition_number":float(base.condition_number),
      "nonlinear_causality_not_claimed":True}
   rows.append(r)
   if cohort=="strict16":
    for drop in sorted(data.fnid.unique()):
     db=data.loc[data.fnid.ne(drop)].copy()
     result=smf.ols("log_yield ~ shock_z + C(fnid) + C(harvest_year)",data=db).fit()
     delete.append({"window":window,"dropped_fnid":drop,"n_remaining_districts":db.fnid.nunique(),
       "n_remaining_rows":len(db),"beta_with_one_district_removed":float(result.params["shock_z"]),
       "full_sample_beta":beta})
 summary=pd.DataFrame(rows)
 chk("all_8_pre_registered_two_way_FE_models",len(summary)==8,len(summary))
 chk("all_source_outcome_rows_represented",len(sub)==812)
 chk("strict16_has_sufficient_obs",sub.in_primary_16.sum()>=400,int(sub.in_primary_16.sum()))
 chk("leave_one_out_16x4_models",len(delete)==64,len(delete))
 chk("models_estimates_finite",np.isfinite(summary["beta_log_yield_per_plus_1_z"]).all())
 summary.to_csv(OUT/"malawi_rainfed_maize_weather_yield_8_FE_models_EXPLORATORY.csv",index=False)
 deletes=pd.DataFrame(delete)
 deletes.to_csv(OUT/"strict16_4climates_leave_one_district_out.csv",index=False)
 grouped=[]
 for win,g in deletes.groupby("window"):
  full=g.full_sample_beta.iloc[0]
  grouped.append({"window":win,"full_16_beta":float(full),
   "min_leave_one_district_beta":float(g.beta_with_one_district_removed.min()),
   "max_leave_one_district_beta":float(g.beta_with_one_district_removed.max()),
   "same_sign_all_16_deletions":bool((np.sign(g.beta_with_one_district_removed)==np.sign(full)).all())})
 leave=pd.DataFrame(grouped)
 leave.to_csv(OUT/"strict16_stability_to_district_omission.csv",index=False)
 # Within model check: 1984-2000 vs 2001-2020 may change coefficients,
 # but focus is sample-definition sensitivity, not fishing.
 periods=[]
 for label,sl in [("early_1983_2000",sub.loc[sub.in_primary_16&sub.harvest_year.le(2000)]),
                 ("late_2001_2020",sub.loc[sub.in_primary_16&sub.harvest_year.ge(2001)])]:
  for win in WINDOWS:
   dat=sl.assign(shock_z=sl[win])
   if dat.fnid.nunique()<10 or dat.harvest_year.nunique()<10:continue
   model=smf.ols("log_yield ~ shock_z + C(fnid)+C(harvest_year)",data=dat).fit()
   periods.append({"period":label,"window":win,"n_rows":len(dat),"districts":dat.fnid.nunique(),
    "years":dat.harvest_year.nunique(),"beta":float(model.params["shock_z"])})
 pd.DataFrame(periods).to_csv(OUT/"strict16_early_late_descriptive_FE_sensitivity.csv",index=False)
 R["counts"]={
  "original_outcome_915":len(a),"eligible_rainfed_main_812":len(sub),
  "strict_16_rows":int(sub.in_primary_16.sum()),
  "strict_16_districts":len(elig),
  "all23_districts":sub.fnid.nunique(),
  "FE_specs_2cohorts_x_4windows":len(summary),
  "leave_one_district_out_specs":len(delete),
  "period_sensitive_specs":len(periods),
  "model_coefficients":summary.to_dict("records"),
  "district_omission_range":leave.to_dict("records"),
  "period_associations":periods}
 R["status"]="COMPLETE" if not R["errors"] else "FAILED"
except Exception as e:
 R["status"]="FAILED";R["errors"].append(repr(e))
 R["traceback"]=traceback.format_exc()[-5000:]
(OUT/"malawi_rainfed_maize_exploratory_model_QA.json").write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":R["status"],"errors":R["errors"],"counts":R.get("counts")},ensure_ascii=False,indent=2,default=str)[:20000])
if R["status"]!="COMPLETE":sys.exit(1)
