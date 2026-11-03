"""Conservative outcome-to-phenology crosswalk for reproducible thesis.
Inputs are original-source-derived, previously QA-verified HarvestStat and
independent EC-JRC ASAP crop calendar on explicitly intersected polygons.
No inference that similar crop/season labels have identical phenology.
No institutional claim; no imputation or silent replacement of rice calendar.
"""
import datetime as dt,json,pathlib,sys,traceback
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"season_outcome_crosswalk_v1"
OUT.mkdir(parents=True,exist_ok=True)
H=ROOT/"results"/"calendar_qa_v1"/"district_crop_season_metadata_consistency.csv"
J=ROOT/"results"/"phenology_v1"/"district_JRC_external_cropping_seasons.csv"
C=ROOT/"results"/"seasonal_climate_v1"/"JRC_crop_season_CHIRPS_1981_2024.csv"
Y=ROOT/"results"/"calendar_qa_v1"/"clean_3crop_district_season_year_rows.csv"
QA={"time_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
    "sources":{"harveststat_summary":str(H.relative_to(ROOT)),
        "jrc_calendar":str(J.relative_to(ROOT)),"seasonal_precip":str(C.relative_to(ROOT)),
        "actual_yield_panel":str(Y.relative_to(ROOT))},
    "definitions":{
      "statistical_stratum":"fnid x product x season_name x crop_production_system",
      "source_calendar_unit":"fnid x crop x JRC crop_name",
      "no_match":"No eligible reference seasonal calendar or contradictory production scope",
      "provisional":"Reference seasonal window tentatively linkable by labels or uniqueness; NOT confirmed agricultural season",
      "harveststat_date_metadata":"FEWS NET statistical labels, not in-situ phenology",
      "valid_institutional_yield_panel":"FALSE for all rows until crop year, irrigation source and treaty verified",
      "year":"harvest_year - original already QA-validated crop-year marker",
      "climate_variable":"CHIRPS v3 standardized calendar-derived rainfall, not river flow or treaty effect"},
    "checks":[],"errors":[]}
def chk(label,yes,details=None):
 QA["checks"].append({"name":label,"pass":bool(yes),"details":details})
 if not yes:QA["errors"].append(label)
def ps_category(s):
 s=str(s).lower()
 if "rainfed" in s or "rain-fed" in s or "pluvial" in s:return "rainfed"
 if "irrigat" in s:return "irrigated"
 if s in ("all (ps)","all","all systems"):return "all"
 if s in ("none","unspecified","nan",""):return "unclassified"
 return "other"
def jrc_system(s):
 s=str(s).lower()
 if "rainfed" in s or "rain-fed" in s:return "rainfed"
 if "irrigat" in s:return "irrigated"
 return "not_specified"
def jrc_season(s):
 s=str(s).lower()
 if "second" in s or "short rains" in s:return "Second"
 if "main" in s or "long rains" in s:return "Main"
 return "no_specific_label"
def checkcandidate(row,x,ncal):
 jps=jrc_system(x.crop_name);hsps=ps_category(row.crop_production_system)
 js=jrc_season(x.crop_name)
 hss=str(row.season_name).strip().lower()
 mismatch=(jps!="not_specified" and hsps!=jps)
 if mismatch:return "BLOCK_PRODUCTION_SCOPE_MISMATCH"
 # For annual district outcomes, never select one of several independent
 # reference seasons: annual yield may aggregate two harvests.
 if ncal>1 and hss in ("annual","yearly","all"):
  return "BLOCK_MULTIPLE_JRC_SEASONS_FOR_ANNUAL_OUTCOME"
 if ncal>1:
  if (hss=="main" and js=="Main") or (hss=="second" and js=="Second"):
   return "PROVISIONAL_EXPLICIT_LABEL"
  return "BLOCK_MULTIPLE_JRC_SEASONS_UNRESOLVED"
 # The unique JRC reference might still not be equivalent to statistical outcome.
 if js in ("Main","Second") and hss in ("main","second") and hss!=js.lower():
  return "BLOCK_SEASON_LABEL_CONFLICT"
 if hsps=="unclassified":
  return "PROVISIONAL_UNCLASSIFIED_PRODUCTION_SYSTEM"
 if hsps=="other":
  return "PROVISIONAL_OTHER_PRODUCTION_SYSTEM"
 if js in ("Main","Second") and hss==js.lower():
  return "PROVISIONAL_EXPLICIT_LABEL"
 return "PROVISIONAL_SINGLE_REFERENCE_WINDOW"
def maxmonthgap(a,b):
 if pd.isna(a) or pd.isna(b):return np.nan
 u=abs(int(a)-int(b))
 return min(u,12-u)

try:
 h=pd.read_csv(H)
 j=pd.read_csv(J)
 y=pd.read_csv(Y,low_memory=False)
 assert set(["fnid","product","season_name","crop_production_system","n_years"]).issubset(h.columns)
 assert set(["fnid","crop","crop_name","sos_s","eos_e"]).issubset(j.columns)
 assert set(["fnid","product","season_name","crop_production_system","harvest_year","yield"]).issubset(y.columns)
 assert not h.duplicated(["fnid","product","season_name","crop_production_system"]).any()
 assert not j.duplicated(["fnid","crop","crop_name"]).any()
 assert not y.duplicated(["fnid","product","season_name","crop_production_system","harvest_year"]).any()
 covered=set(j.fnid.unique())
 hv=h.loc[h.fnid.isin(covered)&h["product"].isin(["Maize","Sorghum","Rice"])].copy()
 chk("geographic_district_159",j.fnid.nunique()==159,int(j.fnid.nunique()))
 chk("calendar_338",len(j)==338,len(j))
 chk("HS_strata_in_mapped_districts_726",len(hv)==726,len(hv))
 chk("actual_observed_source_rows_have_provenance",len(y)>1000,len(y))
 checklist=[]
 selected=[]
 for hr in hv.itertuples(index=False):
  cases=j.loc[j.fnid.eq(hr.fnid)&j.crop.eq(hr.product)].copy()
  if cases.empty:
   selected.append({"fnid":hr.fnid,"BCODE":hr.BCODE,"country_code":hr.country_code,
     "product":hr.product,"season_name":hr.season_name,
     "crop_production_system":hr.crop_production_system,"n_valid":hr.n_valid,
     "n_years":hr.n_years,"longest_consecutive":hr.longest_consecutive,
     "n_jrc_seasons_for_crop":0,"jrc_crop_season":None,
     "crosswalk_status":"BLOCK_NO_JRC_CROP_CALENDAR","provisional_eligible":False,
     "actual_phenology_verified":False,"institutional_regime_linkage_verified":False,
     "region":None,"jrc_jrc_to_harveststat_modal_harvest_month_circular_gap":None})
   continue
  n=len(cases)
  candidates=[]
  for cand in cases.itertuples(index=False):
   status=checkcandidate(hr,cand,n)
   comparison=maxmonthgap(hr.modal_harvest_month,(int(cand.eos_e)-1)//3+1)
   record={"fnid":hr.fnid,"BCODE":hr.BCODE,"country_code":hr.country_code,
     "product":hr.product,"season_name":hr.season_name,
     "crop_production_system":hr.crop_production_system,
     "n_valid":hr.n_valid,"n_years":hr.n_years,
     "longest_consecutive":hr.longest_consecutive,
     "n_jrc_seasons_for_crop":n,"jrc_crop_season":cand.crop_name,
     "jrc_region":cand.name1_shr,"asap1_id":cand.asap1_id,
     "source_jrc_overlap_fraction":cand.frac_district,
     "jrc_source_system":jrc_system(cand.crop_name),
     "jrc_source_season_label":jrc_season(cand.crop_name),
     "HS_production_system_class":ps_category(hr.crop_production_system),
     "HS_statistical_harvest_month":hr.modal_harvest_month,
     "JRC_reference_harvest_end_month":(int(cand.eos_e)-1)//3+1,
     "month_code_gap_diagnostic_not_validation":comparison,
     "crosswalk_status":status,
     "provisional_eligible":status.startswith("PROVISIONAL_"),
     "actual_phenology_verified":False,
     "institutional_regime_linkage_verified":False}
   checklist.append(record)
   candidates.append(record)
  usable=[p for p in candidates if p["provisional_eligible"]]
  if len(usable)==1:
   selected.append(usable[0])
  elif len(usable)>1:
   # no arbitrary selection if two equally plausible crop seasons
   q=dict(candidates[0]);q.update(jrc_crop_season=None,
     crosswalk_status="BLOCK_MULTIPLE_ELIGIBLE_SEASONS",
     provisional_eligible=False)
   selected.append(q)
  else:
   q=dict(candidates[0]);q.update(jrc_crop_season=None,
     crosswalk_status=(candidates[0]["crosswalk_status"] if len(candidates)==1
              else "BLOCK_NO_DEFENSIBLE_JRC_SEASON"),
     provisional_eligible=False)
   selected.append(q)
 sel=pd.DataFrame(selected);cand=pd.DataFrame(checklist)
 assert not sel.duplicated(["fnid","product","season_name","crop_production_system"]).any()
 assert len(sel)==len(hv)
 assert not sel.loc[~sel.provisional_eligible,"jrc_crop_season"].notna().any()
 assert not sel.actual_phenology_verified.any()
 cand.sort_values(["country_code","fnid","product","season_name","crop_production_system","jrc_crop_season"]).to_csv(
   OUT/"all_harveststat_to_jrc_candidate_tests.csv",index=False)
 sel.sort_values(["country_code","fnid","product","season_name","crop_production_system"]).to_csv(
   OUT/"one_row_per_outcome_stratum_decision.csv",index=False)
 out_jrc=j.merge(hv[["fnid","product"]].drop_duplicates(),
   left_on=["fnid","crop"],right_on=["fnid","product"],how="left",indicator=True)
 missing=out_jrc.loc[out_jrc._merge.eq("left_only")].drop(columns=["_merge"])
 missing.to_csv(OUT/"jrc_seasons_without_harveststat_crop.csv",index=False)
 chk("JRC_count_without_HS_crop_15",len(missing)==15,len(missing))
 accepted=sel.loc[sel.provisional_eligible].copy()
 assert not accepted.duplicated(["fnid","product","season_name","crop_production_system"]).any()

 # Strictly one climate reference season per eligible HarvestStat source stratum
 keys=["fnid","product","season_name","crop_production_system"]
 assign=accepted[keys+["jrc_crop_season","crosswalk_status",
                       "n_jrc_seasons_for_crop","HS_statistical_harvest_month",
                       "JRC_reference_harvest_end_month","month_code_gap_diagnostic_not_validation"]]
 outcome=y.merge(assign,on=keys,how="inner",validate="many_to_one")
 chk("outcome_rows_still_unique",not outcome.duplicated(keys+["harvest_year"]).any(),len(outcome))
 qcvals=outcome.qc_flag.astype(float)
 chk("HarvestStat_QC0_observed_rows_only",bool(qcvals.eq(0).all()))
 chk("physical_yield_positive",outcome["yield"].gt(0).all())
 season=pd.read_csv(C,usecols=[
   "fnid","jrc_crop_season","harvest_year","window",
   "precip_total_mm","seasonal_precip_z","seasonal_deficit_z",
   "window_data_status","from_year","from_month","to_year","to_month",
   "calendar_months_included"],low_memory=False)
 chk("climate_wide_unique",not season.duplicated(["fnid","jrc_crop_season","harvest_year","window"]).any())
 wide=season.pivot(index=["fnid","jrc_crop_season","harvest_year"],columns="window",
                   values=["precip_total_mm","seasonal_precip_z","seasonal_deficit_z",
                           "window_data_status","calendar_months_included"])
 wide.columns=["_".join(map(str,q)) for q in wide.columns]
 wide=wide.reset_index()
 matched=outcome.merge(wide,on=["fnid","jrc_crop_season","harvest_year"],
                       how="left",validate="many_to_one",indicator=True)
 chk("no_outcome_duplication_by_calendar",len(matched)==len(outcome),
     {"actual":len(matched),"source":len(outcome)})
 chk("no_missing_climate_year_for_1981_2024",matched._merge.eq("both").all(),
     matched._merge.value_counts().to_dict())
 matched["crosswalk_phenology_status"]="PROVISIONAL_ONLY_NOT_FIELD_VERIFIED"
 matched["institutional_causal_status"]="NOT_IDENTIFIED_NO_TREATMENT_OR_INTAKE_LINK"
 matched.drop(columns=["_merge"]).to_csv(
   OUT/"EXPLORATORY_not_causal_HarvestStat_x_JRC_x_CHIRPS_yield_weather.csv",index=False)
 g=sel.groupby(["country_code","product","crosswalk_status"],dropna=False).agg(
    strata=("fnid","size"),districts=("fnid","nunique"),
    valid_source_crop_year_rows=("n_valid","sum")).reset_index()
 g.to_csv(OUT/"country_crop_crosswalk_decisions.csv",index=False)
 QA["counts"]={
  "jrc_districts":int(j.fnid.nunique()),"jrc_source_assignments":len(j),
  "HS_strata_with_JRC_geographic_coverage":len(hv),
  "HS_strata_with_eligible_JRC_reference":len(accepted),
  "HS_strata_blocked":int((~sel.provisional_eligible).sum()),
  "HS_strata_by_status":sel.crosswalk_status.value_counts().to_dict(),
  "country_status":sel.groupby(["country_code","crosswalk_status"]).size().reset_index(name="n").to_dict("records"),
  "source_jrc_records_with_no_HS_crop":len(missing),
  "candidate_pair_tests":len(cand),
  "observed_qc0_yield_rows_provisionally_linked":len(outcome),
  "actual_yield_x_weather_rows":len(matched),
  "yield_rows_with_core_weather_z":int(pd.to_numeric(matched["seasonal_precip_z_core"],errors="coerce").notna().sum()),
  "yield_rows_with_broad_weather_z":int(pd.to_numeric(matched["seasonal_precip_z_broad"],errors="coerce").notna().sum()),
  "observed_yield_aggregate_not_irrigated_specific":int(
      matched.crop_production_system.fillna("").eq("All (PS)").sum()),
  "actual_crop_season_fully_field_verified":0,
  "implemented_transboundary_institutions_verified":0}
 QA["warnings"]=[
  "PROVISIONAL means reference crop season is not validated as the source's actual yield observation season",
  "All (PS) aggregate yield cannot be interpreted as irrigated-specific; none is not Rainfed or Irrigated",
  "Non-unique JRC seasons never multiplied outcome rows; no missing JRC rice imputed",
  "HarvestStat calendar metadata cannot validate plant phenology according to authors",
  "Historical JRC seasons treated as fixed over 1981-2024, potentially wrong after variety/technology shifts",
  "Climate values are local admin rainfall, not upstream river flow, irrigation intake supply, or treaty treatment",
  "No model coefficients were fitted and no causal estimates may be inferred from this screening"]
 QA["status"]="COMPLETE" if not QA["errors"] else "FAILED"
except Exception as e:
 QA["status"]="FAILED";QA["errors"].append(repr(e))
 QA["traceback"]=traceback.format_exc()[-5500:]
(OUT/"crosswalk_provenance_and_decision_summary.json").write_text(
 json.dumps(QA,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":QA["status"],"errors":QA["errors"],
                  "counts":QA.get("counts")},ensure_ascii=False,indent=2,default=str)[:15000])
if QA["status"]!="COMPLETE":sys.exit(1)
