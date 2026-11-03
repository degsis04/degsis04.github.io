"""Source-level QA of 915 Malawi maize yield records (HarvestStat v1.2).

Independently redownload pinned original 25.3 MB CSV by SHA256 and the
published 915-row pilot output. Verify exact source fields & years.
Investigate Main/Rainfed vs Annual/All change, same-year dual categories,
severe unflagged production outliers, and compare national 2023/24 maize APES
limit as source-labelled external sanity check.

NO harmonisation of production systems. NO automatic outlier correction.
NO regressions, institutional causal claims, or inferred irrigation.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,sys,traceback
import numpy as np,pandas as pd,requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_maize_semantics_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"malawi_maize_v1";TMP.mkdir(parents=True,exist_ok=True)
H=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_csv"]
P="https://raw.githubusercontent.com/degsis04/degsis04.github.io/main/research/basin-data-audit/results/malawi_maize_calendar_sensitivity_v1/malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv"
NATIONAL_2024=2712578.0
NATIONAL_SOURCE="https://fews.net/southern-africa/malawi/food-security-outlook/october-2024"
REPORT={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "sources":{"HarvestStat":{"url":H["url"],"expected_sha256":H["sha256"],"size_bytes":H["size_bytes"]},
 "pilot_outcome":{"url":P},"official_2024_maize_APES":{"url":NATIONAL_SOURCE,"total_tonnes":NATIONAL_2024,
  "period":"2023/24 maize crop year, third-round final, Malawi national; reported in FEWS NET October 2024"}},
 "constraints":{"no_causal_conclusion":True,"no_automatic_outlier_replace":True,
  "series_break_warning":"Main Rainfed (PS) and Annual All (PS) need documentation before stitching",
  "metadata_dates":"HarvestStat months are nominal crop-calendar markers, not observed phenology",
  "national_comparison":"year/maize tonnage sanity screen, not identity matching APES/HarvestStat methods"},
 "checks":{},"errors":[]}
def chk(k,pass_,details=None):
 REPORT["checks"][k]={"pass":bool(pass_),"details":details}
 if not pass_:REPORT["errors"].append(k)
def fetch(url,name,expected_sha=None,expected_size=None):
 p=TMP/name
 if not p.exists() or (expected_size is not None and p.stat().st_size!=expected_size):
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"IndependentAcademicDataQA/1.0"}) as r:
   r.raise_for_status()
   with p.open("wb") as f:
    for chunk in r.iter_content(1<<20):
     if chunk:f.write(chunk)
 with p.open("rb") as f:sha=hashlib.file_digest(f,"sha256").hexdigest()
 if expected_sha is not None and sha !=expected_sha:
  raise RuntimeError(f"Source sha mismatch {name}: {sha} expected {expected_sha}")
 REPORT["sources"][name]={"url":url,"sha256":sha,"bytes":p.stat().st_size}
 return p
def runlen(ys):
 yy=sorted(set(map(int,ys)))
 if not yy:return 0
 best=curr=1
 for a,b in zip(yy,yy[1:]):
  curr=curr+1 if b==a+1 else 1
  best=max(best,curr)
 return best
try:
 original=fetch(H["url"],"hvstat_africa_data_v1.2.csv",H["sha256"],H["size_bytes"])
 pilot_file=fetch(P,"malawi_915_chirps_yields.csv")
 src=pd.read_csv(original,low_memory=False)
 a=pd.read_csv(pilot_file,low_memory=False)
 chk("pinned_original_all_africa_217487",len(src)==217487,len(src))
 chk("pilot_915",len(a)==915,len(a))
 chk("pilot_23_unique_districts",a.fnid.nunique()==23,a.fnid.nunique())
 chk("pilot_exact_maize_malawi",a["product"].eq("Maize").all()&a.fnid.str.startswith("MW").all())
 chk("positive_physical_data",a["yield"].gt(0).all()&a.area.gt(0).all()&a.production.gt(0).all())
 chk("pilot_qc0",a.qc_flag.eq(0).all())
 idcols=["fnid","product","season_name","crop_production_system","harvest_year"]
 chk("no_duplicate_full_agrarian_key",not a.duplicated(idcols).any())
 actual=src.loc[src.country_code.eq("MW") & src["product"].eq("Maize")].copy()
 chk("original_unique_full_keys",not actual.duplicated(idcols).any(),
     int(actual.duplicated(idcols,keep=False).sum()))
 z=a[idcols+["area","production","yield","qc_flag"]].merge(actual[idcols+[
    "area","production","yield","qc_flag","planting_year","planting_month",
    "harvest_month","admin_1","admin_2"]],on=idcols,how="left",
    validate="one_to_one",suffixes=("_p","_s"),indicator=True)
 chk("all_915_rows_are_original_HarvestStat_exact_key",z._merge.eq("both").all(),
     z._merge.value_counts().to_dict())
 field_differences={}
 for col in ["area","production","yield","qc_flag"]:
  xx=pd.to_numeric(z[col+"_p"],errors="coerce")
  yy=pd.to_numeric(z[col+"_s"],errors="coerce")
  mismatch=~np.isclose(xx,yy,rtol=1e-12,atol=1e-10,equal_nan=True)
  field_differences[col]=int(mismatch.sum())
 chk("original_915_values_byte_decimal_agree",all(v==0 for v in field_differences.values()),
     field_differences)
 chk("yield_is_production_per_area",bool(np.nanmax(np.abs(a.production/a.area-a["yield"])/a["yield"])<1e-8))
 
 types=z.groupby(["season_name","crop_production_system"]).agg(
   rows=("fnid","size"),districts=("fnid","nunique"),min_harvest_year=("harvest_year","min"),
   max_harvest_year=("harvest_year","max"),min_yield=("yield_p","min"),median_yield=("yield_p","median"),
   max_yield=("yield_p","max")).reset_index()
 types.to_csv(OUT/"source_verified_915_production_system_definition_counts.csv",index=False)
 # Metadata dates by combination; this checks only coded calendar, not
 # field-level timing. Historical categories were changed/reported in FDW.
 dates=z.groupby(["season_name","crop_production_system",
                   "planting_month","harvest_month"],dropna=False).agg(
    rows=("fnid","size"),districts=("fnid","nunique"),
    min_year=("harvest_year","min"),max_year=("harvest_year","max")).reset_index()
 dates.to_csv(OUT/"source_verified_915_nominal_calendar_field_patterns.csv",index=False)
 
 # Presence/absence and actual 2-by-system duplicate for same FNID/year:
 key=["fnid","harvest_year"]
 groups=z.groupby(key).size().rename("n_records").reset_index()
 repeated=groups.loc[groups.n_records.gt(1)]
 repeated_rows=z.merge(repeated[key],on=key,how="inner").sort_values(key+["season_name"])
 repeated_rows[["fnid","admin_1","admin_2","harvest_year","season_name",
     "crop_production_system","area_p","production_p","yield_p",
     "planting_month","harvest_month"]].to_csv(
     OUT/"simultaneous_main_rainfed_and_annual_all_same_year.csv",index=False)
 chk("only_expected_MW_source_categories",
      set(map(tuple,z[["season_name","crop_production_system"]].drop_duplicates().itertuples(index=False,name=None)))==
      {("Main","Rainfed (PS)"),("Annual","All (PS)")})
 chk("district_year_keys_no_more_than_2",groups.n_records.max()<=2,int(groups.n_records.max()))
 
 yearsumm=z.groupby(["harvest_year","season_name","crop_production_system"]).agg(
   rows=("fnid","size"),distinct_districts=("fnid","nunique"),
   total_reported_production_t=("production_p","sum"),area_ha=("area_p","sum"),
   min_yield_t_ha=("yield_p","min"),median_yield_t_ha=("yield_p","median"),
   max_yield_t_ha=("yield_p","max")).reset_index()
 yearsumm.to_csv(OUT/"maize_malawi_year_system_panel_coverage.csv",index=False)
 
 series=[]
 for (fnid,name,ps),g in z.groupby(["fnid","season_name","crop_production_system"]):
  sy=sorted(g.harvest_year.astype(int).unique())
  series.append({"fnid":fnid,"admin_1":g.admin_1.iloc[0],"admin_2":g.admin_2.iloc[0],
    "season_name":name,"crop_production_system":ps,"n_years":len(sy),
    "first_year":min(sy),"last_year":max(sy),"longest_consecutive_years":runlen(sy),
    "n_gaps_in_span":max(sy)-min(sy)+1-len(sy),
    "median_yield_t_ha":float(g.yield_p.median()),
    "max_yield_t_ha":float(g.yield_p.max())})
 summary=pd.DataFrame(series)
 summary.to_csv(OUT/"district_by_system_maize_series_quality.csv",index=False)
 
 # Pre-defined red-flag screens. Not an assertion of the *cause* of discrepancy.
 yr=z.sort_values("yield_p",ascending=False)
 # Detect multiple abnormally large observations in any of the 915, not just the known case
 flags=yr.loc[yr.yield_p.gt(10)|yr.production_p.gt(1000000)].copy()
 flags["flag_reason"]=flags.apply(lambda r:
   ("YIELD_GT10T_HA;" if r.yield_p>10 else "")+
   ("PRODUCTION_GT1M_T;" if r.production_p>1000000 else ""),axis=1)
 flags["comparison_national_2024_tonnes"]=np.where(
    flags.harvest_year.eq(2024),NATIONAL_2024,np.nan)
 flags["district_production_as_fraction_of_national_2024"]=np.where(
   flags.harvest_year.eq(2024), flags.production_p/NATIONAL_2024,np.nan)
 flags[["fnid","admin_1","admin_2","harvest_year","season_name",
 "crop_production_system","area_p","production_p","yield_p","qc_flag_p",
 "flag_reason","comparison_national_2024_tonnes",
 "district_production_as_fraction_of_national_2024"]].to_csv(
 OUT/"UNRESOLVED_quarantine_extreme_maize_observations.csv",index=False)
 
 outlier=yr.loc[yr.fnid.eq("MW2018A20104") & yr.harvest_year.eq(2024)]
 chk("suspicious_2024_observation_present",len(outlier)==1,len(outlier))
 chk("2024_district_exceeds_national_aggregate_sanity",
     outlier.production_p.iloc[0]>NATIONAL_2024,
     {"district_production_t":float(outlier.production_p.iloc[0]),
      "national_maize_t":NATIONAL_2024,
      "ratio":float(outlier.production_p.iloc[0]/NATIONAL_2024),
      "qc_flag":int(outlier.qc_flag_p.iloc[0]),
      "source_citation":NATIONAL_SOURCE})
 
 # Data-only dataset for the first eventual single-type Main/Rainfed comparison.
 main=z.loc[z.season_name.eq("Main")&z.crop_production_system.eq("Rainfed (PS)")].copy()
 annual=z.loc[z.season_name.eq("Annual")&z.crop_production_system.eq("All (PS)")].copy()
 # NEVER append Annual to Main; distinct source series and estimates.
 eligible=summary.loc[summary.season_name.eq("Main") & summary.crop_production_system.eq("Rainfed (PS)")].copy()
 eligible["length_30_or_more"]=eligible.n_years.ge(30)
 eligible["max_gap_fraction"]=eligible.n_gaps_in_span/(eligible.last_year-eligible.first_year+1)
 eligible["strict_30year_5pct_gaps"]=eligible.length_30_or_more&eligible.max_gap_fraction.le(.05)
 eligible["confirmed_same_harvest_year_semantics"]=False
 eligible["admissible_for_untreated_causal_treaty_effect"]=False
 eligible.to_csv(OUT/"main_rainfed_only_district_eligibility.csv",index=False)
 
 # Need raw full-source category inventory around 2018+ for ANY Malawi maize,
 # independent of selected districts to detect nationwide regime boundary.
 countryyear=actual.groupby(["harvest_year","season_name","crop_production_system"]).agg(
    n_rows=("fnid","size"),districts=("fnid","nunique")).reset_index()
 countryyear.to_csv(OUT/"full_source_Malawi_maize_category_by_year.csv",index=False)
 
 # Clear decision statuses for all 915 rows, outlier quarantine ON and
 # all annual vs rainfed strata remain DISTINCT.
 out=z[["fnid","admin_1","admin_2","harvest_year","season_name",
  "crop_production_system","planting_year","planting_month","harvest_month",
  "area_p","production_p","yield_p","qc_flag_p"]].copy()
 out["series_id"]=out.fnid+"::"+out.season_name+"::"+out.crop_production_system
 out["do_not_bridge_production_systems"]=True
 out["actual_irrigation_from_transboundary_water_verified"]=False
 out["phenology_JRC_vs_HS_verified"]=False
 out["external_APES_year_comparable_verified"]=False
 out["source_statistical_definition_status"]=np.where(
    out.crop_production_system.eq("Rainfed (PS)"),
    "EXPLICIT_RAINFED_LABEL_NOT_FIELD_VERIFIED",
    "ALL_PRODUCTION_SYSTEMS_NOT_RAINFED_SPECIFIC")
 out["extreme_value_quarantine"]=out.yield_p.gt(10)|out.production_p.gt(1000000)
 out["pre_regression_status"]=np.where(out.extreme_value_quarantine,
    "BLOCK_OUTLIER_UNRESOLVED",
    np.where(out.crop_production_system.eq("Rainfed (PS)"),
      "USE_ONLY_WITHIN_FIXED_MAIN_RAINFED_LABEL_CHECK_SOURCE",
      "SEPARATE_ANNUAL_ALL_NOT_COMPARABLE_TO_MAIN_RAINFED"))
 out.sort_values(["fnid","harvest_year","season_name"]).to_csv(
    OUT/"all_915_source_record_decision_audit.csv",index=False)
 
 # Summarize, including how many district/year overlapping categories
 REPORT["counts"]={
 "total_original_HS_Malawi_maize_rows":len(actual),
 "pilot_original_source_confirmed_rows":len(z),
 "pilot_unique_districts":int(z.fnid.nunique()),
 "pilot_unique_district_years":int(len(groups)),
 "pilot_duplicate_district_years_due_to_both_categories":len(repeated),
 "pilot_min_year":int(z.harvest_year.min()),
 "pilot_max_year":int(z.harvest_year.max()),
 "main_rainfed_rows":len(main),"main_rainfed_districts":int(main.fnid.nunique()),
 "annual_all_rows":len(annual),"annual_all_districts":int(annual.fnid.nunique()),
 "source_system_groups":types.to_dict("records"),
 "main_rainfed_series_ge30years":int(eligible.length_30_or_more.sum()),
 "main_rainfed_series_ge30years_gaps_le5percent":int(eligible.strict_30year_5pct_gaps.sum()),
 "suspicious_maize_rows_gt10t_ha_or_gt1million_t":len(flags),
 "quarantined_malawi_crop_year_rows":int(out.extreme_value_quarantine.sum()),
 "national_2024_t":NATIONAL_2024,
 "suspicious_2024_one_district_prod_t":float(outlier.production_p.iloc[0]),
 "suspicious_2024_one_district_ratio_national":float(outlier.production_p.iloc[0]/NATIONAL_2024),
 "overlapping_category_year_min":int(repeated.harvest_year.min()) if len(repeated) else None,
 "overlapping_category_year_max":int(repeated.harvest_year.max()) if len(repeated) else None
 }
 REPORT["status"]="PASS" if not REPORT["errors"] else "FAIL"
except Exception as e:
 REPORT["status"]="FAIL";REPORT["errors"].append(repr(e))
 REPORT["traceback"]=traceback.format_exc()[-5000:]
(OUT/"Malawi_915_primary_original_source_QA.json").write_text(
 json.dumps(REPORT,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":REPORT["status"],"errors":REPORT["errors"],
 "counts":REPORT.get("counts")},ensure_ascii=False,indent=2,default=str)[:12000])
if REPORT["status"]!="PASS":sys.exit(1)
