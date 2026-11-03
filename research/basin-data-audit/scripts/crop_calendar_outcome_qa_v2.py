"""HarvestStat Africa v1.2 independent crop-calendar and crop-system QA.

DO NOT use planting/harvest month as observed phenology. Per official HarvestStat
README they are statistical season-identification metadata. This audit checks
physical plausibility of date coding and within/between-country metadata
consistency. No rainfall-to-outcome regression, no invented or merged seasons.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import traceback
import numpy as np
import pandas as pd
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"calendar_qa_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"harveststat_calendar_audit";TMP.mkdir(exist_ok=True)
source=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_csv"]
PAGES={
"official_codebook":"https://github.com/HarvestStat/HarvestStat-Africa/releases/tag/v1.2",
"source_warning":"https://github.com/HarvestStat/HarvestStat-Africa/blob/main/README.md",
"citation":"https://doi.org/10.5061/dryad.vq83bk42w"}
TARGET=("Maize","Sorghum","Rice")
LOG={"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
     "sources":PAGES,"actual_data_url":source["url"],"expected_sha256":source["sha256"],
     "semantic_warning":"Planting/harvest months are NOT field-observed phenological dates. Harmonization must use external agronomic calendars.",
     "checks":{},"errors":[]}
def test(name,ok,detail=None):
 LOG["checks"][name]={"pass":bool(ok),"detail":detail}
 if not ok:LOG["errors"].append(name)
def save(): (OUT/"calendar_qa_provenance.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False,default=str)+"\n")
def longest(a):
 a=sorted(set(int(x) for x in a if pd.notna(x)))
 if not a:return 0
 n=best=1
 for x,y in zip(a,a[1:]):
  n=n+1 if y==x+1 else 1;best=max(best,n)
 return best
def cls(s):
 s=str(s).lower()
 if "rainfed" in s or "rain-fed" in s or "pluvial" in s:return "rainfed_explicit"
 if "irrigat" in s:return "irrigated_explicit_broad"
 if "all" in s:return "all_production_systems"
 if s in ("none","unspecified","nan",""):return "unclassified"
 return "other_unverified"
try:
 f=TMP/"hvstat_africa_data_v1.2.csv"
 if not f.exists() or f.stat().st_size != source["size_bytes"]:
  with requests.get(source["url"],timeout=(30,180),stream=True,
                    headers={"User-Agent":"Independent-Academic-Calendar-QA/1.0"}) as r:
   r.raise_for_status()
   with f.open("wb") as w:
    for block in r.iter_content(2**20):
     if block:w.write(block)
 with f.open("rb") as stream:hashval=hashlib.file_digest(stream,"sha256").hexdigest()
 test("pinned_data_source",hashval==source["sha256"],hashval)
 raw=pd.read_csv(f,low_memory=False)
 for col in ["yield","area","production","qc_flag","planting_month","harvest_month","planting_year","harvest_year"]:
  raw[col]=pd.to_numeric(raw[col],errors="coerce")
 test("217487_original_records",len(raw)==217487,len(raw))
 raw=raw.loc[raw["product"].isin(TARGET)&raw.harvest_year.between(1981,2024)].copy()
 raw["season_name"]=raw["season_name"].fillna("UNSPECIFIED")
 raw["crop_production_system"]=raw["crop_production_system"].fillna("UNSPECIFIED")
 raw["ps_class"]=raw["crop_production_system"].map(cls)
 raw["source_valid"]=raw.qc_flag.eq(0)&raw["yield"].gt(0)&raw["area"].gt(0)&raw["production"].gt(0)
 test("original_3_crop_count",len(raw)==55719,len(raw))
 test("original_three_crop_qc",int(raw.source_valid.sum())==51547,int(raw.source_valid.sum()))
 
 cross=pd.read_csv(ROOT/"results"/"harveststat"/"dominant_bcu_assignment.csv")
 cross=cross.loc[cross.dominant_ge_80pct,["fnid","dominant_bcu","BCODE","dominant_share"]]
 assert not cross.fnid.duplicated().any()
 raw=raw.merge(cross,on="fnid",how="inner",validate="many_to_one")
 test("source_three_crop_post_bcu_qc",int(raw.source_valid.sum())==35353,int(raw.source_valid.sum()))
 raw=raw.loc[raw.source_valid].copy()
 raw["valid_planting_month"]=raw.planting_month.between(1,12,inclusive="both")
 raw["valid_harvest_month"]=raw.harvest_month.between(1,12,inclusive="both")
 raw["valid_planting_year"]=raw.planting_year.between(1900,2030,inclusive="both")
 raw["complete_time_fields"]=raw.valid_planting_month&raw.valid_harvest_month&raw.valid_planting_year
 raw["crop_duration_months"]=(12*(raw.harvest_year-raw.planting_year)
                         +raw.harvest_month-raw.planting_month)
 raw["duration_in_0_to_24_months"]=(raw.complete_time_fields&
                          raw.crop_duration_months.between(0,24,inclusive="both"))
 raw["planting_after_harvest"]=(raw.complete_time_fields&raw.crop_duration_months.lt(0))
 raw["duration_over_18_months"]=(raw.complete_time_fields&raw.crop_duration_months.gt(18))
 raw["crosses_year"]=raw.complete_time_fields&raw.planting_year.lt(raw.harvest_year)
 LOG["raw_qa"]={
  "valid_crop_rows_with_bcu":len(raw),"complete_calendar_metadata":int(raw.complete_time_fields.sum()),
  "missing_calendar_metadata":int((~raw.complete_time_fields).sum()),
  "planting_after_harvest":int(raw.planting_after_harvest.sum()),
  "duration_gt18_months":int(raw.duration_over_18_months.sum()),
  "crop_duration_gt24_months":int((raw.complete_time_fields&raw.crop_duration_months.gt(24)).sum()),
  "duration_0_24_months":int(raw.duration_in_0_to_24_months.sum()),
  "harvest_year_different_from_plant_year":int(raw.crosses_year.sum()),
  "production_system_counts":raw.ps_class.value_counts().to_dict(),
  "distinct_districts":raw.fnid.nunique(),
  "min_year":int(raw.harvest_year.min()),"max_year":int(raw.harvest_year.max())}
 
 keys=["fnid","country_code","dominant_bcu","BCODE","product","season_name","crop_production_system"]
 keys_without_country=["fnid","product","season_name","crop_production_system","harvest_year"]
 test("unique_full_panel_key",not raw.duplicated(keys_without_country).any(),
      {"duplicate_rows":int(raw.duplicated(keys_without_country,keep=False).sum())})
 # First-pass recoding of each district crop × season × system without combining labels.
 raw["metadata_duration_flag"]=np.select(
   [~raw.complete_time_fields,raw.planting_after_harvest,raw.duration_over_18_months],
   ["MISSING_MONTH_OR_PLANT_YEAR","PLANTING_AFTER_HARVEST","DURATION_GT18M"],
   default="REASONABLE_METADATA_NOT_OBSERVED_PHENOLOGY")
 raw["yield_t_ha_recomputed"]=raw.production/raw.area
 err=(raw["yield"]-raw.yield_t_ha_recomputed).abs()/raw["yield"]
 LOG["yield_check"]={"max_relative_error":float(err.max()),
                     "n_relative_error_gt_1pct":int(err.gt(.01).sum())}
 test("yield_arithmetic",float(err.max())<1e-8,LOG["yield_check"])
 keep=["fnid","country_code","dominant_bcu","BCODE","product","season_name",
  "crop_production_system","ps_class","planting_year","planting_month",
  "harvest_year","harvest_month","crop_duration_months","metadata_duration_flag",
  "yield","area","production","qc_flag","dominant_share"]
 raw.loc[:,keep].sort_values(["BCODE","fnid","product","harvest_year"]).to_csv(
   OUT/"clean_3crop_district_season_year_rows.csv",index=False)
 
 summaries=[]
 for k,g in raw.groupby(keys,dropna=False):
  years=sorted(set(g.harvest_year.astype(int)))
  time=g.loc[g.complete_time_fields]
  months=(time.groupby(["planting_month","harvest_month"],dropna=False)
                .size().sort_values(ascending=False))
  distinct_month_pairs=len(months)
  modal=months.index[0] if distinct_month_pairs else (np.nan,np.nan)
  modal_share=float(months.iloc[0]/len(g)) if distinct_month_pairs else 0
  summaries.append(dict(zip(keys,k),n_valid=len(g),n_years=len(years),
    longest_consecutive=longest(years),start_year=min(years),end_year=max(years),
    fractional_year_gaps=1-len(years)/(max(years)-min(years)+1),
    n_distinct_month_pairs=distinct_month_pairs,
    modal_planting_month=modal[0],modal_harvest_month=modal[1],
    fraction_rows_with_modal_month_pair=modal_share,
    fraction_calendar_complete=float(g.complete_time_fields.mean()),
    fraction_calendar_coded_inconsistent=float((g.planting_after_harvest|g.duration_over_18_months).mean()),
    ps_class=g.ps_class.iloc[0]))
 ds=pd.DataFrame(summaries)
 ds.to_csv(OUT/"district_crop_season_metadata_consistency.csv",index=False)
 
 # BCU-country-level calendar patterns and whether 'Main' means consistent dates.
 countrykeys=["BCODE","dominant_bcu","country_code","product","season_name","crop_production_system"]
 group=[]
 for k,g in raw.groupby(countrykeys,dropna=False):
  m=g.loc[g.complete_time_fields].groupby(["planting_month","harvest_month"]).size().sort_values(ascending=False)
  modal=m.index[0] if len(m) else (np.nan,np.nan)
  group.append(dict(zip(countrykeys,k),records=len(g),districts=g.fnid.nunique(),
     distinct_years=g.harvest_year.nunique(),first=int(g.harvest_year.min()),last=int(g.harvest_year.max()),
     ps_class=g.ps_class.iloc[0],
     modal_planting_month=modal[0],modal_harvest_month=modal[1],
     modal_month_pair_share=(float(m.iloc[0]/len(g)) if len(m) else 0),
     n_month_pairs=len(m),pct_calendar_complete=float(g.complete_time_fields.mean()),
     pct_inconsistent_metadata=float((g.planting_after_harvest|g.duration_over_18_months).mean())))
 groups=pd.DataFrame(group)
 groups.to_csv(OUT/"bcu_country_crop_season_month_patterns.csv",index=False)
 
 # Cross-check metadata for previously shortlisted label-level pairs, not physical equivalence.
 prior=pd.read_csv(ROOT/"results"/"design_gate_v1"/"cross_country_system_year_pairs.csv")
 cand=prior.loc[prior.stronger_label_match_candidate].copy()
 pmap=groups.set_index(["BCODE","dominant_bcu","country_code","product","season_name","crop_production_system"])
 comparisons=[]
 for r in cand.itertuples(index=False):
  aa=(r.BCODE,r.bcu_a,r.country_a,r.product,r.season_a,r.system_a)
  bb=(r.BCODE,r.bcu_b,r.country_b,r.product,r.season_b,r.system_b)
  if aa not in pmap.index or bb not in pmap.index:
   comparisons.append({"BCODE":r.BCODE,"crop":r.product,"missing_metadata_pair":True})
   continue
  x,y=pmap.loc[aa],pmap.loc[bb]
  both_complete=float(min(x.pct_calendar_complete,y.pct_calendar_complete))
  comparable=(pd.notna(x.modal_planting_month)&pd.notna(y.modal_planting_month)&
   x.modal_planting_month==y.modal_planting_month and x.modal_harvest_month==y.modal_harvest_month)
  comparisons.append({
   "BCODE":r.BCODE,"crop":r.product,"country_a":r.country_a,"country_b":r.country_b,
   "bcu_a":r.bcu_a,"bcu_b":r.bcu_b,
   "seasons":r.season_a,"production_label":r.system_a,
   "common_harvest_years":r.overlapping_harvest_years,
   "n_month_codes_country_a":int(x.n_month_pairs),
   "n_month_codes_country_b":int(y.n_month_pairs),
   "modal_plant_month_a":x.modal_planting_month,"modal_harvest_month_a":x.modal_harvest_month,
   "modal_plant_month_b":y.modal_planting_month,"modal_harvest_month_b":y.modal_harvest_month,
   "share_same_modal_month_pair_within_country_a":x.modal_month_pair_share,
   "share_same_modal_month_pair_within_country_b":y.modal_month_pair_share,
   "same_modal_month_code_not_physical_calendar":bool(comparable),
   "min_calendar_record_completeness":both_complete,
   "physical_phenological_comparability_verified":False})
 cp=pd.DataFrame(comparisons)
 cp.to_csv(OUT/"cross_country_month_metadata_diagnostic.csv",index=False)
 LOG["pair_audit"]={"previously_22_same_label_pairs":len(cand),
    "pair_rows_in_diagnostic":len(cp),
    "same_month_code":int(cp.same_modal_month_code_not_physical_calendar.sum()) if len(cp) else 0,
    "physical_phenology_confirmed":0}
 test("same_label_pair_count_22",len(cand)==22,len(cand))
 test("one_row_per_compared_pair",len(cp)==len(cand),len(cp))
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as ex:
 LOG["status"]="FAILED";LOG["exception"]=repr(ex)
 LOG["traceback"]=traceback.format_exc()[-6000:]
finally:
 save()
 print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"raw_qa":LOG.get("raw_qa"),
                  "pairs":LOG.get("pair_audit"),"exception":LOG.get("exception")},
                  indent=2,ensure_ascii=False))
if LOG["status"]!="COMPLETE":sys.exit(1)
