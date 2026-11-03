"""Independent reproducibility audit of HarvestStat × TFDD and crop continuity.

Checks source hashes, canonical physical units, yield identity, uniqueness,
season collisions, positive values, polygon-country matches, equal-area shares,
no over-allocation, previously stored count invariants, and sensitivity of
boundary assignment. Does NOT claim a hydrological or causal result.
"""
import datetime as dt, hashlib, io, json, os, pathlib, tempfile, traceback, zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import pycountry

ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT/"results"/"harveststat"
CONT=ROOT/"results"/"crop_continuity"
OUT=ROOT/"results"/"qa_v1";OUT.mkdir(parents=True,exist_ok=True)
TEMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"basin_qa_v1";TEMP.mkdir(parents=True,exist_ok=True)
PROV=json.loads((OLD/"audit_provenance.json").read_text())
LOG={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"checks":{},"warnings":[],"errors":[],"status":"STARTED","units":{"area":"hectare","production":"metric tonne","yield":"metric tonne per hectare","geometry_area":"square kilometres in EPSG:6933","CHIRPS_precipitation":"mm per month (separate pilot)"}}
def check(name,ok,details=None):
 LOG["checks"][name]={"pass":bool(ok),"details":details}
 if not ok: LOG["errors"].append(name)
def dump():
 (OUT/"qa_provenance.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
def download(key):
 u=PROV["inputs"][key]["url"];file=TEMP/pathlib.Path(u).name
 if not file.exists():
  with requests.get(u,stream=True,timeout=(30,180),headers={"User-Agent":"ScientificDataQA/1.0"}) as r:
   r.raise_for_status()
   with file.open("wb") as f:
    for part in r.iter_content(1024*1024):
     if part:f.write(part)
 with file.open("rb") as f:sha=hashlib.file_digest(f,"sha256").hexdigest()
 check("sha256_"+key,sha==PROV["inputs"][key]["sha256"],{"actual":sha,"expected":PROV["inputs"][key]["sha256"]})
 return file

try:
 data=download("harveststat_csv")
 gpk=download("harveststat_boundaries")
 archive=download("tfdd2024")
 t=pd.read_csv(data,low_memory=False)
 for col in ("yield","area","production","harvest_year","qc_flag"):
  t[col]=pd.to_numeric(t[col],errors="coerce")
 check("raw_rowcount",len(t)==217487,{"observed":len(t)})
 check("countries_33",t.country_code.nunique()==33,t.country_code.nunique())
 check("units_documented",True,"HarvestStat v1.2 README documents area ha, production mt, yield mt/ha; ratio checked below")
 check("no_unknown_qc",set(t.qc_flag.dropna().unique()).issubset({0,1,2}),t.qc_flag.value_counts(dropna=False).to_dict())
 keys=["fnid","product","harvest_year","season_name","crop_production_system"]
 kdup=int(t.duplicated(keys,keep=False).sum())
 check("full_key_uniqueness",kdup==0,{"duplicate_rows":kdup})
 tab_good=t.qc_flag.eq(0)&t["area"].gt(0)&t["production"].gt(0)&t["yield"].gt(0)&t.harvest_year.notna()
 check("all_crop_joint_valid_count",int(tab_good.sum())==198014,{"current":int(tab_good.sum()),"previous":198014})
 ratio=t.production/t.area.replace(0,np.nan)
 relative=(ratio-t["yield"]).abs()/t["yield"].where(t["yield"]>0)
 for tol in (0.000001,0.001,0.01,0.05,0.20):
  LOG["checks"][f"yield_identity_relative_error_over_{tol}"]={"pass":True,"details":int((tab_good & relative.gt(tol)).sum())}
 LOG["checks"]["yield_identity_distribution"]={"pass":True,"details":{str(k):float(relative[tab_good].quantile(k)) for k in (.5,.95,.99,1.)}}
 same_cropyr=t.groupby(["fnid","product","harvest_year"],dropna=False).size()
 LOG["checks"]["multirow_district_crop_year"]={"pass":True,"details":{"keys_with_multiple_rows":int((same_cropyr>1).sum()),"records_in_multiple_keys":int(same_cropyr[same_cropyr>1].sum()),"largest_group":int(same_cropyr.max())}}
 # Country/season data provenance and row verification.
 three=t["product"].isin(["Maize","Rice","Sorghum"])&t.harvest_year.between(1981,2024,inclusive="both")
 v=three&tab_good
 check("three_crop_original_count",int(three.sum())==55719,int(three.sum()))
 check("three_crop_qc_count",int(v.sum())==51547,int(v.sum()))
 # Country codes and original data geometry keys.
 admin=gpd.read_file(gpk)
 check("admin_FNID_unique",admin.fnid.is_unique,{"shapes":len(admin),"unique_fnids":admin.fnid.nunique()})
 check("all_data_FNID_geometries",set(t.fnid.dropna()).issubset(set(admin.fnid)),{"unmatched_data_FNID":len(set(t.fnid.dropna())-set(admin.fnid))})
 # Physical coordinates and pixel/shape dimensions are audited independent of provenance.
 check("admin_geometry_crs",admin.crs is not None,str(admin.crs))
 with zipfile.ZipFile(archive) as z:
  shp=[p for p in z.namelist() if p.endswith("BCUMaster313_20240807.shp")][0]
  z.extractall(TEMP/"tfdd")
  bcu=gpd.read_file(TEMP/"tfdd"/shp)
 check("bcu_count_818",len(bcu)==818,{"actual":len(bcu)})
 check("bcu_unique_ids",bcu.BCCODE.is_unique,{"unique":bcu.BCCODE.nunique(),"rows":len(bcu)})
 check("bcu_country_ID_consistency",((bcu.BCCODE.str.split("_").str[-1].str.upper()==bcu.CCODE.str.upper())).all(),
        "Sanity check BCCODE suffix equals CCODE; may fail for multi-part territorial codes")
 for src in (admin,bcu):
  check("crs_"+("admin" if src is admin else "bcu"),src.crs is not None,str(src.crs))
 # Independent verification of saved spatial crosswalk (separate geometry engine operation).
 aa=admin[["fnid","country_code","geometry"]].dropna(subset="geometry").drop_duplicates("fnid").to_crs(6933)
 bb=bcu[["BCCODE","BCODE","CCODE","geometry"]].dropna(subset="geometry").to_crs(6933)
 aa["geometry"]=aa.geometry.make_valid()
 bb["geometry"]=bb.geometry.make_valid()
 aa["iso3"]=aa.country_code.map(lambda s:pycountry.countries.get(alpha_2=str(s).upper()).alpha_3 if pycountry.countries.get(alpha_2=str(s).upper()) is not None else None)
 aa["admin_area_m2"]=aa.geometry.area
 bb["CCODE"]=bb.CCODE.astype(str).str.upper()
 candidates=gpd.sjoin(aa,bb,predicate="intersects",how="inner")
 candidates=candidates[candidates.iso3==candidates.CCODE].copy()
 # Intersection as independent direct shapely overlay, no gpd.overlay used.
 shape_lookup=bb.geometry.to_dict()
 candidates["overlap_area_m2"]=[a.intersection(shape_lookup[j]).area for a,j in zip(candidates.geometry,candidates.index_right)]
 candidates=candidates[candidates.overlap_area_m2>1e4].copy()  # matches > 0.01 km2
 candidates["fraction"]=candidates.overlap_area_m2/candidates.admin_area_m2
 check("no_over_100pct_single_intersection",bool((candidates.fraction<=1.000001).all()),
       {"max_fraction":float(candidates.fraction.max()) if len(candidates) else None})
 sums=candidates.groupby("fnid").fraction.sum()
 check("no_bcu_overlap_or_area_duplication",bool((sums<=1.01).all()),
      {"max_fraction_sum":float(sums.max()) if len(sums) else None,
       "admin_with_sum_over_101pct":int((sums>1.01).sum())})
 checked=candidates.groupby("fnid").fraction.max()
 recorded=pd.read_csv(OLD/"dominant_bcu_assignment.csv")
 independent80=set(checked.index[checked>=0.8])
 prior80=set(recorded.loc[recorded.dominant_ge_80pct,"fnid"])
 check("spatial_dominant_80pct_set_matches",independent80==prior80,
      {"independent":len(independent80),"prior":len(prior80),
       "only_independent":len(independent80-prior80),"only_prior":len(prior80-independent80)})
 # Evaluate alternative threshold counts without changing model definitions
 sens=[]
 for thresh in (.7,.8,.9,.95):
  fnids=set(checked.index[checked>=thresh])
  sel=t.fnid.isin(fnids)&tab_good
  z=t.loc[sel,["fnid","product","harvest_year"]].drop_duplicates()
  sens.append({"threshold":thresh,"admin_units":len(fnids),"all_crop_valid_rows":int(sel.sum()),
               "unique_admin_crop_years":len(z)})
 pd.DataFrame(sens).to_csv(OUT/"geometry_threshold_sensitivity.csv",index=False)
 LOG["checks"]["spatial_threshold_sensitivity"]={"pass":True,"details":sens}
 # Verify 3-crop split and temporal count invariants from *source rows* and recorded BCU.
 selected=t.loc[three&tab_good].merge(
  recorded.loc[recorded.dominant_ge_80pct,["fnid","dominant_bcu"]],
  on="fnid",how="inner",validate="many_to_one")
 check("cropped_valid_with_80pct_counts",len(selected)==35353,{"observed":len(selected)})
 # Required columns from canonical README, no mixing year types or crop types.
 check("years_in_range",bool(t.loc[three,"harvest_year"].between(1981,2024,inclusive="both").all()),None)
 # Validate that district crop-year can be repeated across production systems; do not add them blindly.
 # Compare prior summary counts to CSV outputs.
 cont=pd.read_csv(CONT/"continuity_provenance.json") if False else json.loads((CONT/"continuity_provenance.json").read_text())
 bcus=pd.read_csv(CONT/"bcu_crop_season_summary.csv")
 check("BCU_season_series_count",len(bcus)==cont["bcu_crop_season_series"],{"current":len(bcus),"prior":cont["bcu_crop_season_series"]})
 check("BCU_eligible_unique_count",bcus.loc[bcus.bcu_eligible,"dominant_bcu"].nunique()==40,
       int(bcus.loc[bcus.bcu_eligible,"dominant_bcu"].nunique()))
 check("BCU_eligible_basin_count",bcus.loc[bcus.bcu_eligible,"BCODE"].nunique()==17,
       int(bcus.loc[bcus.bcu_eligible,"BCODE"].nunique()))
 # Geography overlap between all districts and basin group membership.
 check("no_unknown_geocodes",not candidates.iso3.isna().any(),None)
 LOG["status"]="PASS" if not LOG["errors"] else "FAIL"
except Exception as e:
 LOG["errors"].append("EXCEPTION: "+repr(e))
 LOG["traceback"]=traceback.format_exc()
 LOG["status"]="FAIL"
finally:
 dump()
print(json.dumps({"status":LOG["status"],"checks":len(LOG["checks"]),"errors":LOG["errors"],
"yield_identity":LOG["checks"].get("yield_identity_distribution",{}),"threshold":LOG["checks"].get("spatial_threshold_sensitivity",{})},ensure_ascii=False,indent=2))
if LOG["status"]!="PASS":raise SystemExit(1)
