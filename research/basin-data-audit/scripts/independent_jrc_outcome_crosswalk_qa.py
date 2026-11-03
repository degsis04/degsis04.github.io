"""Independent QA of JRC->HarvestStat decisions and experimental weather-outcome joins.
Recompute every rule and key from saved raw-like audit input, without relying
on same producer's selection logic. No statistical/causal inference.
"""
import datetime as dt,json,pathlib,sys,traceback
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/"results"/"season_outcome_crosswalk_v1"
L={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
   "checks":{},"errors":[]}
def chk(key,condition,extra=None):
 L["checks"][key]={"pass":bool(condition),"details":extra}
 if not condition:L["errors"].append(key)
try:
 source=pd.read_csv(ROOT/"results"/"calendar_qa_v1"/"district_crop_season_metadata_consistency.csv")
 cals=pd.read_csv(ROOT/"results"/"phenology_v1"/"district_JRC_external_cropping_seasons.csv")
 raw=pd.read_csv(ROOT/"results"/"calendar_qa_v1"/"clean_3crop_district_season_year_rows.csv",low_memory=False)
 panel=pd.read_csv(D/"EXPLORATORY_not_causal_HarvestStat_x_JRC_x_CHIRPS_yield_weather.csv",low_memory=False)
 sel=pd.read_csv(D/"one_row_per_outcome_stratum_decision.csv")
 meta=json.loads((D/"crosswalk_provenance_and_decision_summary.json").read_text())
 keys=["fnid","product","season_name","crop_production_system"]
 source=source.loc[source.fnid.isin(cals.fnid.unique())].copy()
 chk("original_726_strata",len(source)==726,{"found":len(source)})
 chk("all_strata_present_once",source[keys].sort_values(keys).reset_index(drop=True).equals(
     sel[keys].sort_values(keys).reset_index(drop=True)))
 chk("selected_unique",not sel.duplicated(keys).any())
 chk("provisional_plus_blocked_726",len(sel.loc[sel.provisional_eligible])+len(sel.loc[~sel.provisional_eligible])==726)
 chk("JRC_source_338",len(cals)==338)
 chk("no_unverified_physical_season",not sel.actual_phenology_verified.fillna(False).any())
 chk("none_verified_institutions",not sel.institutional_regime_linkage_verified.fillna(False).any())
 chk("missing_BF_rice_never_auto_imputed",
   sel.loc[sel.country_code.eq("BF")&sel["product"].eq("Rice"),
           "crosswalk_status"].eq("BLOCK_NO_JRC_CROP_CALENDAR").all(),
   {"n":int((sel.country_code.eq("BF")&sel["product"].eq("Rice")).sum())})
 chk("Mali_rainfed_JRC_not_matched_to_aggregate_Rice",
     sel.loc[sel.country_code.eq("ML")&sel["product"].eq("Rice"),
          "crosswalk_status"].eq("BLOCK_PRODUCTION_SCOPE_MISMATCH").all())
 chk("Zambia_none_PS_explicitly_flagged",
    sel.loc[sel.country_code.eq("ZM")&sel.provisional_eligible,"crosswalk_status"].eq(
        "PROVISIONAL_UNCLASSIFIED_PRODUCTION_SYSTEM").all())
 chk("selected_source_keys_unique",not panel.duplicated(keys+["harvest_year"]).any(),
     {"rows":len(panel)})
 chk("qc0_only",panel.qc_flag.eq(0).all())
 chk("no_false_crosswalk_ready",panel.crosswalk_phenology_status.eq(
     "PROVISIONAL_ONLY_NOT_FIELD_VERIFIED").all())
 chk("actual_yield_positive",panel["yield"].gt(0).all())
 yratio=panel["production"]/panel["area"]
 relative=(yratio-panel["yield"]).abs()/panel["yield"]
 chk("recomputed_yield_relative_error_lt1e8",bool(relative.max()<1e-8),
   {"max_abs_relative_error":float(relative.max())})
 # Independent raw source row count per eligible source stratum, NOT assuming
 # that rows in same district/JRC season are independent observations.
 eligible=sel.loc[sel.provisional_eligible,keys].copy()
 raw_sub=raw.merge(eligible,on=keys,validate="many_to_one",how="inner")
 chk("expected_yield_rows_equal_raw_source_selection",len(raw_sub)==len(panel),
    {"raw":len(raw_sub),"joined":len(panel)})
 chk("year_keys_equal_source",set(map(tuple,raw_sub[keys+["harvest_year"]].itertuples(index=False,name=None)))==
                             set(map(tuple,panel[keys+["harvest_year"]].itertuples(index=False,name=None))))
 # Do not confuse CHIRPS 'mean 1981-2010' as fitted crop-specific SPI.
 for field in ["seasonal_precip_z_core","seasonal_precip_z_broad"]:
  z=pd.to_numeric(panel[field],errors="coerce")
  chk("only_finite_"+field,np.isfinite(z.dropna()).all())
 
 cals_uniq=cals.groupby(["fnid","crop"]).crop_name.nunique()
 provisional=sel.loc[sel.provisional_eligible].copy()
 # Independently verify chosen seasons belong to same crop and region.
 assigned=provisional[["fnid","product","jrc_crop_season"]].drop_duplicates()
 reference=cals[["fnid","crop","crop_name"]].rename(columns={
  "crop":"product","crop_name":"jrc_crop_season"})
 test=assigned.merge(reference,on=["fnid","product","jrc_crop_season"],how="left",
                     validate="many_to_one",indicator=True)
 chk("all_assigned_reference_seasons_actually_exist",test._merge.eq("both").all())
 chk("unmatched_outcome_never_received_season",
    sel.loc[~sel.provisional_eligible,"jrc_crop_season"].isna().all())
 L["counts"]={
  "source_HS_strata":len(source),"source_JRC_windows":len(cals),
  "provisional_strata":len(provisional),"blocked_strata":int((~sel.provisional_eligible).sum()),
  "provisionally_linked_yield_year_rows":len(panel),
  "correct_QC0_yield_weather_year_rows_core":int(panel.seasonal_precip_z_core.notna().sum()),
  "countries":int(provisional.country_code.nunique()),
  "croplist":provisional.groupby("product").agg(strata=("fnid","size"),
                      districts=("fnid","nunique")).to_dict("index"),
  "basins_with_any_provisional":int(provisional.BCODE.nunique()),
  "unclear_other_or_none_production_strata":int(provisional.crosswalk_status.isin(
    ["PROVISIONAL_UNCLASSIFIED_PRODUCTION_SYSTEM","PROVISIONAL_OTHER_PRODUCTION_SYSTEM"]).sum())}
 L["status"]="PASS" if not L["errors"] else "FAILED"
except Exception as e:
 L["status"]="FAILED";L["errors"].append(repr(e));L["traceback"]=traceback.format_exc()[-4500:]
(D/"independent_crosswalk_quality_checks.json").write_text(
 json.dumps(L,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":L["status"],"errors":L["errors"],"counts":L.get("counts")},ensure_ascii=False,indent=2)[:10000])
if L["status"]!="PASS":sys.exit(1)
