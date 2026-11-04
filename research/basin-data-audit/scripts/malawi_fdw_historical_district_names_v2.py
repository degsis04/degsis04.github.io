"""Historical Malawi APES/FDW original names→HarvestStat districts, with strict ambiguity guards.
Raw FDW archive exact Dryad/GitHub checksum. All joins are named district+region+year+season+system,
not automatic same administrative territory or time-invariant geographies.
"""
import io, os, pathlib, hashlib, zipfile, collections, json, sys, re, traceback, datetime
import pandas as pd, numpy as np, requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_apes_fdw_source_audit_v1";OUT.mkdir(exist_ok=True,parents=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"mw_original_names_v2";TMP.mkdir(exist_ok=True,parents=True)
URL="https://github.com/HarvestStat/HarvestStat-Africa/releases/download/v1.2/doi_10_5061_dryad_vq83bk42w__v20260717.zip"
OUTER_SHA="2ff71261f39b207c0b9d5becaa9efce891cba035d80e0df0acadc7b9b190218f"
INNER_SHA="6e8128f8854f38172aea24583e537395242abafab4382441b3d53805c44b452b"
PILOT=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1"/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv"
ELIG=ROOT/"results"/"malawi_maize_semantics_v1"/"main_rainfed_only_district_eligibility.csv"
LOG={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED",
 "constraints":["no automated old-FNID to new-FNID geographic equivalence","area planted != area harvested",
  "raw FDW are not original ministry APES microdata or primary year-by-year official reports",
  "name agreement does not prove boundary equivalence; year shift only diagnostic, never applied"],
 "checks":{}}
def check(k,b,detail=None):
    LOG["checks"][k]={"pass":bool(b),"detail":detail}
    if not b:raise AssertionError(k+": "+str(detail))
def normalize(s):
    return re.sub(r"[^a-z0-9]+","",str(s).casefold()) if pd.notna(s) else ""
def near(a,b):
    return abs(float(a)-float(b))<=max(1e-7,abs(float(b))*1e-9) if pd.notna(a) and pd.notna(b) else False
try:
    p=TMP/"original_bundle.zip"
    with requests.get(URL,stream=True,timeout=(30,210),headers={"User-Agent":"ThesisOriginalDistrictCropSourceQA/1.0"}) as r:
        r.raise_for_status()
        with p.open("wb") as f:
            for c in r.iter_content(2**20):
                if c:f.write(c)
    check("outer_sha256",hashlib.sha256(p.read_bytes()).hexdigest()==OUTER_SHA)
    with zipfile.ZipFile(p) as zz:
        check("outer_crc",zz.testzip() is None)
        rawzip=zz.read("fdw_raw_data_v1.2.zip")
    check("raw_sha256",hashlib.sha256(rawzip).hexdigest()==INNER_SHA)
    with zipfile.ZipFile(io.BytesIO(rawzip)) as zz:
        check("inner_crc",zz.testzip() is None)
        raw=pd.read_csv(io.BytesIO(zz.read("adm_crop_data_raw_MW.csv")),low_memory=False)
    src=pd.read_csv(PILOT)
    elig=pd.read_csv(ELIG)[["fnid","admin_1","admin_2"]]
    check("pilot_915",len(src)==915)
    check("23_district_labels",len(elig)==23 and elig.fnid.is_unique)
    src=src.merge(elig,on="fnid",validate="many_to_one")
    check("all_pilot_23_labels",src.admin_2.notna().all())
    src["district_key"]=src.admin_2.map(normalize)
    src["region_key"]=src.admin_1.map(normalize)
    check("district_name_no_dup_across_current_fnid",not src[["fnid","district_key","region_key"]].drop_duplicates().duplicated(["district_key","region_key"]).any())
    raw=raw.loc[raw["product"].eq("Maize Grain (White)")].copy()
    raw["year"]=pd.to_datetime(raw.period_date,errors="coerce").dt.year
    raw["region_key"]=raw.admin_1.map(normalize)
    raw["district_key"]=raw.admin_2.map(normalize)
    raw["value_num"]=pd.to_numeric(raw.value,errors="coerce")
    check("all_maize_years_present",raw.year.notna().all())
    check("district_labels_present",raw.district_key.str.len().gt(0).all())
    rk=["region_key","district_key","year","season_name","crop_production_system"]
    lookup={k:g for k,g in raw.groupby(rk,dropna=False)}
    countrysets=raw.groupby(["region_key","district_key"]).agg(
      variants=("admin_2",lambda a:" | ".join(sorted(set(map(str,a))))),
      fnids=("fnid",lambda a:" | ".join(sorted(set(map(str,a))))),
      n_distinct_source_ids=("fnid","nunique"),
      first_year=("year","min"),last_year=("year","max"),rows=("value_num","size")).reset_index()
    countrysets.to_csv(OUT/"historical_FDW_district_names_Fnid_versions.csv",index=False)
    LOG["name_crosswalk"]={"source_district_region_pairs":len(countrysets),
      "pairs_with_multiple_source_fnids":int(countrysets.n_distinct_source_ids.gt(1).sum())}
    comparison=[]
    for x in src.itertuples(index=False,name=None):
        pass
    # Iterate as dictionaries to handle reserved "yield" source column
    for x in src.to_dict("records"):
        key=(x["region_key"],x["district_key"],int(x["harvest_year"]),x["season_name"],x["crop_production_system"])
        g=lookup.get(key)
        r={"fnid_harmonized":x["fnid"],"district":x["admin_2"],"region":x["admin_1"],"district_norm":x["district_key"],
           "harvest_year":int(x["harvest_year"]),"season_name":x["season_name"],"system":x["crop_production_system"],
           "hs_area_ha":float(x["area"]),"hs_production_t":float(x["production"]),"hs_yield":float(x["yield"]),
           "n_raw_records":len(g) if g is not None else 0}
        if g is None:
            r["source_raw_fnids"]=r["source_docs"]=r["source_publications"]=r["source_periods"]=""
        else:
            r["source_raw_fnids"]=" | ".join(sorted(set(g.fnid.dropna().astype(str))))
            r["source_docs"]=" | ".join(sorted(set(g.source_document.dropna().astype(str))))
            r["source_publications"]=" | ".join(sorted(set(g.publication_name.dropna().astype(str))))
            r["source_periods"]=" | ".join(sorted(set(g.season_year.dropna().astype(str))))
        for rawname,tag,target in [
          ("Area Planted","area_planted",x["area"]),
          ("Area Harvested","area_harvested",x["area"]),
          ("Quantity Produced","production",x["production"]),
          ("Yield","yield",x["yield"])]:
            cand=g.loc[g.indicator.eq(rawname)] if g is not None else pd.DataFrame(columns=raw.columns)
            vals=cand.value_num.dropna().values
            r["n_"+tag]=len(vals)
            r[tag+"_same"]=sum(near(v,target) for v in vals)
            r[tag+"_source_values"]=" | ".join(format(float(v),".12g") for v in vals[:8])
            r[tag+"_source_statuses"]=" | ".join(sorted(set(cand.status.dropna().astype(str))))
        r["has_raw_key"]=r["n_raw_records"]>0
        r["area_planted_exact"]=r["area_planted_same"]>0
        r["area_harvested_exact"]=r["area_harvested_same"]>0
        r["production_exact"]=r["production_same"]>0
        r["reported_yield_exact"]=r["yield_same"]>0
        r["area_prod_agree"]=r["area_planted_exact"] and r["production_exact"]
        r["all_three_reported_agree"]=r["area_prod_agree"] and r["reported_yield_exact"]
        r["at_least_one_source_key_ambiguous"]=bool(g is not None and
          (g.loc[g.indicator.eq("Area Planted"),"value_num"].dropna().nunique()>1 or
          g.loc[g.indicator.eq("Quantity Produced"),"value_num"].dropna().nunique()>1 or
          g.fnid.nunique()>1))
        r["raw_same_identifier"]=bool(g is not None and set(g.fnid.dropna().astype(str))=={x["fnid"]})
        comparison.append(r)
    out=pd.DataFrame(comparison)
    out.to_csv(OUT/"historical_APES_FDW_vs_HarvestStat_by_district_year_unharmonized_identity.csv",index=False)
    def agg(d):
        return {"n":len(d),"keys_found":int(d.has_raw_key.sum()),"area_planted_equal":int(d.area_planted_exact.sum()),
          "area_harvested_equal":int(d.area_harvested_exact.sum()),"production_equal":int(d.production_exact.sum()),
          "reported_yield_equal":int(d.reported_yield_exact.sum()),"area_and_production_exact":int(d.area_prod_agree.sum()),
          "three_exact":int(d.all_three_reported_agree.sum()),
          "found_but_old_fnid":int((d.has_raw_key & ~d.raw_same_identifier).sum()),
          "multiple_possible_numeric_sources":int(d.at_least_one_source_key_ambiguous.sum())}
    LOG["summary_915"]=agg(out)
    LOG["by_system"]={f"{sn}/{ps}":agg(v) for (sn,ps),v in out.groupby(["season_name","system"])}
    byyr=out.groupby(["season_name","system","harvest_year"]).agg(
       hs_rows=("fnid_harmonized","size"),found=("has_raw_key","sum"),
       area_planted_exact=("area_planted_exact","sum"),production_exact=("production_exact","sum"),
       reported_yield_exact=("reported_yield_exact","sum"),three_exact=("all_three_reported_agree","sum"),
       old_fnid=("raw_same_identifier",lambda a:int((~a).sum()))).reset_index()
    byyr.to_csv(OUT/"historical_FDW_match_by_year_name_based.csv",index=False)
    LOG["by_year_1983_1999"] = byyr.loc[byyr.harvest_year.le(1999)].to_dict("records")
    LOG["by_year_2000_2020"] = byyr.loc[byyr.harvest_year.ge(2000)].to_dict("records")
    # Flag actual observed yield label vs computed; know when source status Not Available
    # and no reported yield but area+prod match.
    out["source_yield_computed_only"]=out.area_prod_agree & ~out.reported_yield_exact
    LOG["yield_status"]={"derived_computed_only_count":int(out.source_yield_computed_only.sum()),
      "source_yield_reported_equal":int(out.reported_yield_exact.sum())}
    LOG["raw_name_unmatched_district_examples"]=out.loc[~out.has_raw_key,
          ["fnid_harmonized","district","harvest_year","season_name","system"]].head(20).to_dict("records")
    check("915_names_audited",len(out)==915)
    check("all_matched_raw_values_exact_area_prod_only_when_true",
       bool((out.area_prod_agree<=out.has_raw_key).all()))
    LOG["status"]="PASS_UNVERIFIED_HISTORICAL_GEOGRAPHY"
except Exception as e:
    LOG["status"]="FAILED";LOG["error"]=repr(e);LOG["traceback"]=traceback.format_exc()[-3500:]
(OUT/"historical_FDW_name_based_QA.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in LOG.items() if k in ("status","summary_915","by_system","name_crosswalk","error")},ensure_ascii=False)[:6500])
sys.exit(0 if LOG["status"]=="PASS_UNVERIFIED_HISTORICAL_GEOGRAPHY" else 1)
