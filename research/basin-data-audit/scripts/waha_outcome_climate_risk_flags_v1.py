"""Transfer INDEPENDENT field-reported JRC-calendar disagreement to eligible
HarvestStat strata as ANALYSIS-RISK FLAGS, never automatic truth labels.

Only Mali/Malawi explicit region-name matches. Risk flags never modify the
8,642 source outcome rows or the climate values. No personal survey rows.
"""
import datetime as dt,json,pathlib,sys,traceback,re,unicodedata
import pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/"results"/"field_phenology_v1"
S=ROOT/"results"/"season_outcome_crosswalk_v1"/"one_row_per_outcome_stratum_decision.csv"
Y=ROOT/"results"/"season_outcome_crosswalk_v1"/"EXPLORATORY_not_causal_HarvestStat_x_JRC_x_CHIRPS_yield_weather.csv"
Q={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","errors":[],
   "interpretation":"Heuristic MONTH-agreement risk flags for fixed JRC windows only. Not a field validation of HarvestStat season.",
   "thresholds":{"HIGH_DISAGREEMENT":"Either sow/harvest JRC month coverage <0.50",
                 "MODERATE_DISAGREEMENT":"Either coverage <0.70 while neither <0.50",
                 "RELATIVELY_HIGH_MONTH_AGREEMENT":"Both coverages >=0.70",
                 "NO_SURVEY_CROP_REGION_MATCH":"No comparable region-crop survey table; do not infer quality"},
   "warnings":["Unweighted field records, not nationally representative crop-area shares",
    "Mali planting YEAR missing; not annual phenology validation",
    "JRC broad window includes all months up to end of harvest; a mismatch in harvest dates may or may not change core growing-season rainfall.",
    "Coverage <50% is an exploratory caution, not a statistical test/rejection of JRC",
    "Do not automatically exclude or declare any HarvestStat observations confirmed."]}
def norm(v):
 if pd.isna(v):return ""
 return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",str(v)).encode("ascii","ignore").decode().casefold())
try:
 q=json.loads((D/"waha_jrc_region_agreement_QA.json").read_text())
 assert q["status"]=="COMPLETE"
 fr=pd.read_csv(D/"waha_vs_jrc_Mali_Malawi_admin1_month_agreement.csv")
 fr=fr.loc[fr.status.eq("MATCH_ADMIN1_CROP_MONTH_REFERENCE_ONLY")].copy()
 fr["country_code"]=fr.country.map({"Mali":"ML","Malawi":"MW"})
 fr["key_region"]=fr.JRC_admin1.map(norm)
 assert len(fr)==20
 assert not fr.duplicated(["country_code","key_region","crop"]).any()
 a=pd.read_csv(S)
 a=a.loc[a.provisional_eligible].copy()
 a["key_region"]=a.jrc_region.map(norm)
 a=a.rename(columns={"product":"crop"})
 renamefields=["country_code","key_region","crop","survey_sowing_fraction_in_JRC_months",
              "survey_harvest_fraction_in_JRC_months","survey_n_valid_sowing",
              "survey_n_valid_harvest_begin","JRC_admin1","survey_sowing_modal_month",
              "survey_harvest_modal_month","JRC_sowing_months","JRC_harvest_months"]
 risk=a.merge(fr[renamefields],on=["country_code","key_region","crop"],
              how="left",validate="many_to_one",indicator=True)
 assert len(risk)==len(a)
 def classify(r):
  if pd.isna(r.survey_sowing_fraction_in_JRC_months):return "NO_SURVEY_CROP_REGION_MATCH"
  if min(r.survey_sowing_fraction_in_JRC_months,r.survey_harvest_fraction_in_JRC_months)<.50:return "HIGH_DISAGREEMENT"
  if min(r.survey_sowing_fraction_in_JRC_months,r.survey_harvest_fraction_in_JRC_months)<.70:return "MODERATE_DISAGREEMENT"
  return "RELATIVELY_HIGH_MONTH_AGREEMENT"
 risk["field_survey_JRC_month_agreement_flag"]=risk.apply(classify,axis=1)
 risk["crop_season_validated"]=False
 risk["institutional_effect_estimable"]=False
 risk["risk_does_not_change_original_series"]=True
 x=risk.drop(columns=["_merge"]).copy()
 x.to_csv(D/"waha_field_evidence_flags_for_provisional_HarvestStat_strata.csv",index=False)
 y=pd.read_csv(Y,low_memory=False,usecols=["fnid","product","season_name","crop_production_system","harvest_year"])
 x["product"]=x["crop"]
 keys=["fnid","product","season_name","crop_production_system"]
 yy=y.merge(x[keys+["field_survey_JRC_month_agreement_flag"]],
          on=keys,how="left",validate="many_to_one")
 if yy.field_survey_JRC_month_agreement_flag.isna().any():
  raise ValueError("A selected yield row has lost its crosswalk risk classification")
 if len(yy)!=8642:raise ValueError(f"Expected original 8642 rows, got {len(yy)}")
 tab=(yy.groupby("field_survey_JRC_month_agreement_flag")
      .agg(harveststat_rows=("harvest_year","size"),
           distinct_crop_series=("fnid","nunique")).reset_index())
 tab.to_csv(D/"harveststat_observed_yield_rows_by_field_JRC_risk.csv",index=False)
 Q["counts"]={"source_reference_regions_crop_matches":len(fr),
  "provisional_HarvestStat_strata":len(x),
  "with_independent_field_month_comparison":int((x.field_survey_JRC_month_agreement_flag!="NO_SURVEY_CROP_REGION_MATCH").sum()),
  "strata_risk_counts":x.field_survey_JRC_month_agreement_flag.value_counts().to_dict(),
  "yield_rows_risk_counts":yy.field_survey_JRC_month_agreement_flag.value_counts().to_dict(),
  "n_yield_rows_unchanged":len(yy),
  "n_bcu_independent_institutions_confirmed":0,
  "n_outcome_strata_crop_pheno_validated":0,
  "strata_by_country_crop_risk":x.loc[x.country_code.isin(["ML","MW"])].groupby(
    ["country_code","crop","field_survey_JRC_month_agreement_flag"]).size().reset_index(name="n").to_dict("records")}
 Q["status"]="COMPLETE"
except Exception as e:
 Q["status"]="FAILED";Q["errors"].append(repr(e))
 Q["traceback"]=traceback.format_exc()[-3500:]
(D/"waha_outcome_season_risk_QA.json").write_text(json.dumps(Q,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":Q["status"],"errors":Q["errors"],"counts":Q.get("counts")},ensure_ascii=False,indent=2,default=str)[:16000])
if Q["status"]!="COMPLETE":sys.exit(1)
