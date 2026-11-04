"""Stage 29 independent evidence: effective historical administrative transfer factors and shared outcome lineage.
Important: ratio HS/raw is an empirical *effective* ratio, not the original PBR/CBR weight matrix.
No original 1971/1998/2003 polygon/cropland raster released in pinned HarvestStat repo.
Conclude reconstructibility separately from estimates and treat source/name mappings as partial only.
"""
from pathlib import Path
import json,sys,datetime,traceback
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1]
BASE=R/"results"/"malawi_apes_fdw_source_audit_v1"
OUT=R/"results"/"stage29_admin_lineage_design_gate";OUT.mkdir(exist_ok=True,parents=True)
SOURCE=BASE/"historical_APES_FDW_vs_HarvestStat_by_district_year_unharmonized_identity.csv"
MODEL=R/"results"/"malawi_rainfed_weather_yield_v1"/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv"
LOG={"status":"STARTED","run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"checks":{},"cautions":["Effective scaled ratios are NOT original PBR/CBR transfer coefficients.",
"Sources keyed by current district name can miss inherited records from differently named old districts.",
"Same values in historical administrative units are not independent spatial evidence.",
"Source documents do not establish natural river-flow delivery or causal institution impact."]}
def ch(k,test,info=None):
 LOG["checks"][k]={"pass":bool(test),"info":info}
 if not test:raise AssertionError(k+": "+str(info))
def first_number(v):
 if pd.isna(v) or v=="":return np.nan
 z=str(v).split(" | ")[0]
 try:return float(z)
 except:return np.nan
try:
 src=pd.read_csv(SOURCE)
 mo=pd.read_csv(MODEL)
 ch("915_crosswalk",len(src)==915)
 ch("812_main",len(mo)==812)
 ch("no_source_duplicate",not src.duplicated(["fnid_harmonized","harvest_year","season_name","system"]).any())
 ch("model_unique",not mo.duplicated(["fnid","harvest_year"]).any())
 main=src.loc[(src.season_name=="Main")&(src["system"]=="Rainfed (PS)")].copy()
 check=main.merge(mo[["fnid","harvest_year","in_primary_16","log_yield","broad","core","waha_broad","waha_growth"]],
     left_on=["fnid_harmonized","harvest_year"],right_on=["fnid","harvest_year"],how="inner",validate="one_to_one")
 ch("all_812_matched_to_model",len(check)==812)
 core=check.loc[check.in_primary_16].copy()
 ch("strict_16_count",len(core)==584 and core.fnid.nunique()==16)
 for z in (check,core):
  z["raw_area_planted"]=z.area_planted_source_values.apply(first_number)
  z["raw_prod"]=z.production_source_values.apply(first_number)
  z["effective_area_factor"]=z.hs_area_ha/z.raw_area_planted
  z["effective_prod_factor"]=z.hs_production_t/z.raw_prod
  z["ratio_disagreement"]=abs(z.effective_area_factor-z.effective_prod_factor)
  z["is_shared_scalar"]=z.has_raw_key & (~z.area_prod_agree) & z.reported_yield_exact & z.ratio_disagreement.le(1e-8)
  z["is_complex_or_changing_yield"]=z.has_raw_key & (~z.reported_yield_exact)
  z["no_same_named_old_record"]=~z.has_raw_key
  z["status_source"] = np.select(
     [z.no_same_named_old_record,z.is_complex_or_changing_yield,z.is_shared_scalar,
      z.area_prod_agree&z.reported_yield_exact,z.area_prod_agree&~z.reported_yield_exact],
     ["NO_DIRECT_OLD_SOURCE","COMPOSITE_OR_CHANGED_YIELD","SCALAR_AREA_PRODUCTION",
      "DIRECT_AREA_PRODUCTION_YIELD","DERIVED_YIELD_FROM_SOURCE_AREA_PROD"],default="OTHER")
  z["old_Fnid_generation"]=z.source_raw_fnids.fillna("").str.extract(r"(MW\d{4})A",expand=False)
  z["ratio_inferred_not_original_PBR_CBR"]=True
 def publish(z,name):
  keys=["fnid","district","region","harvest_year","source_raw_fnids","source_docs","source_publications",
  "hs_yield","hs_area_ha","hs_production_t","raw_area_planted","raw_prod","in_primary_16",
  "status_source","old_Fnid_generation","effective_area_factor","effective_prod_factor",
  "ratio_disagreement","reported_yield_exact","area_prod_agree","ratio_inferred_not_original_PBR_CBR"]
  z[keys].to_csv(OUT/name,index=False)
 publish(check,"malawi_812_inferred_effective_admin_transfer_scalars_NOT_original_weights.csv")
 publish(core,"malawi_584_strict16_inferred_effective_admin_transfer_scalars_NOT_original_weights.csv")
 def cat_counts(z):
  return {str(k):int(v) for k,v in z.status_source.value_counts().to_dict().items()}
 LOG["all812_classes"]=cat_counts(check)
 LOG["strict584_classes"]=cat_counts(core)
 scalar=check[check.status_source=="SCALAR_AREA_PRODUCTION"]
 ch("scalar_per_observation_area_production_factor_agree",bool(scalar.ratio_disagreement.le(1e-8).all()),
   float(scalar.ratio_disagreement.max()) if len(scalar) else None)
 ratios=core.loc[core.status_source=="SCALAR_AREA_PRODUCTION"].copy()
 groups=ratios.groupby(["district","old_Fnid_generation"]).agg(
    years=("harvest_year","nunique"),first_year=("harvest_year","min"),last_year=("harvest_year","max"),
    min_scaler=("effective_area_factor","min"),median_scaler=("effective_area_factor","median"),
    max_scaler=("effective_area_factor","max"),max_ratio_disagreement=("ratio_disagreement","max")).reset_index()
 groups["scale_span"]=groups.max_scaler-groups.min_scaler
 groups.to_csv(OUT/"strict16_effective_scalars_by_district_boundary_generation.csv",index=False)
 LOG["strict16_inferred_scalars_groups"]=len(groups)
 LOG["strict16_max_area_prod_diff"]=float(ratios.ratio_disagreement.max()) if len(ratios) else None
 LOG["strict16_long_period_factor_ranges"]=groups.sort_values("years",ascending=False).head(20).to_dict("records")
 byyear=core.groupby(["harvest_year","status_source"]).size().unstack(fill_value=0)
 byyear.to_csv(OUT/"strict16_source_lineage_status_by_year.csv")
 bydistrict=core.groupby(["district","status_source"]).size().unstack(fill_value=0)
 bydistrict.to_csv(OUT/"strict16_source_lineage_status_by_district.csv")
 # Separate most serious issue: same historical raw source FNID mapped to several modern districts
 valid=core.loc[core.has_raw_key].copy()
 ancestry=valid.groupby(["harvest_year","source_raw_fnids"]).agg(
    modern_districts=("fnid","nunique"),names=("district",lambda x:" | ".join(sorted(set(x)))),
    raw_yield_values=("hs_yield",lambda x:" | ".join(format(v,".12g") for v in sorted(set(x))))).reset_index()
 shared=ancestry.loc[ancestry.modern_districts>1]
 shared.to_csv(OUT/"strict16_direct_same_old_FNID_multiple_modern_units.csv",index=False)
 LOG["strict16_same_observed_old_Fnid_duplicate_years"]=len(shared)
 # Pairwise identical yield trajectories: potential shared ancestor, not guaranteed.
 wide=core.pivot(index="harvest_year",columns="fnid",values="hs_yield")
 pairs=[]
 keys=list(wide.columns)
 for i,aa in enumerate(keys):
  for bb in keys[i+1:]:
   x=wide[aa];y=wide[bb];mask=x.notna()&y.notna()
   n=int(mask.sum())
   if n<4:continue
   both=sorted(x.index[mask])
   matches=[int(t) for t in both if np.isclose(float(x.loc[t]),float(y.loc[t]),rtol=1e-12,atol=1e-12)]
   runs=[];run=[]
   for yy in matches:
    if run and yy!=run[-1]+1:
     runs.append(run);run=[]
    run.append(yy)
   if run:runs.append(run)
   longest=max((len(s) for s in runs),default=0)
   if longest>=3 or len(matches)>=5:
    pairs.append({"fnid1":aa,"fnid2":bb,"overlap_years":n,"exact_same_year_yield_n":len(matches),
       "max_consecutive_same_yield_years":longest,"first_same_year":min(matches),"last_same_year":max(matches),
       "possible_reused_geographical_source_not_proof":True})
 pd.DataFrame(pairs,columns=["fnid1","fnid2","overlap_years","exact_same_year_yield_n",
  "max_consecutive_same_yield_years","first_same_year","last_same_year",
  "possible_reused_geographical_source_not_proof"]).to_csv(
   OUT/"strict16_pairwise_identical_historical_yield_traces_QA.csv",index=False)
 LOG["strict16_possible_identical_yield_pairs"]=pairs
 # Traceability flags for all 16 districts & decision label
 district_year=core.groupby("fnid").agg(
  n=("harvest_year","size"),first_year=("harvest_year","min"),last_year=("harvest_year","max"),
  direct_yield=("reported_yield_exact","sum"),direct_area_prod=("area_prod_agree","sum"),
  changed_or_composed_yield=("is_complex_or_changing_yield","sum"),
  source_absent=("no_same_named_old_record","sum"),scalar_transfer=("is_shared_scalar","sum")).reset_index()
 district_year["risk_rank"]=np.select(
  [district_year.changed_or_composed_yield.gt(0)|district_year.source_absent.gt(0),
   district_year.scalar_transfer.gt(0)],
  ["HIGH_SOURCE_RECONSTRUCTED","MODERATE_AREA_PROD_TRANSFORMED"],default="LOW_MATCHING_ORIGINAL_VALUES")
 district_year.to_csv(OUT/"strict16_critical_district_decision_table.csv",index=False)
 LOG["strict16_risk_levels"]={k:int(v) for k,v in district_year.risk_rank.value_counts().to_dict().items()}
 ch("no_fabricated_original_link_ratio",bool(check.ratio_inferred_not_original_PBR_CBR.all()))
 ch("all_584_classes",int(sum(LOG["strict584_classes"].values()))==584)
 ch("all_812_classes",int(sum(LOG["all812_classes"].values()))==812)
 LOG["original_weights_reproducible_from_public_repo"]="NO — old boundary shape files and 2015 hybrid cropland raster referenced in notebook/tools are not committed in pinned repo; inferred effective ratios differ from original PBR/CBR link matrix"
 LOG["status"]="PASS_EFFECTIVE_SCALARS_ONLY"
except Exception as ex:
 LOG["status"]="FAILED";LOG["exception"]=repr(ex);LOG["traceback"]=traceback.format_exc()[-5500:]
(OUT/"stage29_administrative_transfer_QA.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False,default=str)+"\n")
print(json.dumps({k:v for k,v in LOG.items() if k in
 ["status","strict584_classes","all812_classes","strict16_risk_levels","strict16_same_observed_old_Fnid_duplicate_years",
  "strict16_possible_identical_yield_pairs","exception"]},ensure_ascii=False)[:7000])
sys.exit(0 if LOG["status"]=="PASS_EFFECTIVE_SCALARS_ONLY" else 1)
