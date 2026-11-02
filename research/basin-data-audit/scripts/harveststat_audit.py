"""HarvestStat Africa v1.2 × TFDD BCU audit.
No data are invented. Input archives downloaded from pinned official public sources.
Outputs: availability, QC, administrative-to-BCU shares, conservative primary assignment.
Run: python research/basin-data-audit/scripts/harveststat_audit.py
"""
import datetime, hashlib, json, os, pathlib, platform, sys, tempfile, zipfile
from collections import Counter
import numpy as np
import pandas as pd
import geopandas as gpd
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"harveststat"; OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"harveststat_bcu_audit"; TMP.mkdir(parents=True,exist_ok=True)
REV="5b62fb5"  # release v1.2 publicly identified commit
HS_ROOT=f"https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/{REV}/public/"
SOURCES={
 "harveststat_csv":HS_ROOT+"hvstat_africa_data_v1.2.csv",
 "harveststat_boundaries":HS_ROOT+"hvstat_africa_boundary_v1.2.gpkg",
 "tfdd2024":"https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip"
}
manifest={"run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"inputs":{},"versions":{"python":platform.python_version(),"pandas":pd.__version__,"geopandas":gpd.__version__},"definitions":{
"baseline_valid":"yield > 0, area > 0, production > 0, qc_flag == 0, harvest_year present",
"spatial_fraction":"geodesic-style equal-area EPSG:6933 polygon intersection in km2 / admin polygon area; NOT irrigated/cropped share",
"dominant_assignment":"unique highest-overlap BCU, same country, share>=0.8; never replicate one harveststat row into multiple BCU",
"uncertainties":"polygon overlap is NOT farmland location; historical admin boundaries may not match historical years; institutions not yet joined"}}
def savej(name,o): (OUT/name).write_text(json.dumps(o,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf8")
def dl(key):
 url=SOURCES[key];path=TMP/pathlib.Path(url).name
 if not path.exists() or path.stat().st_size==0:
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"Academic basin data audit/0.3"}) as resp:
   resp.raise_for_status()
   with path.open("wb") as fp:
    for chunk in resp.iter_content(chunk_size=1024*1024):
     if chunk:fp.write(chunk)
 digest=hashlib.file_digest(path.open("rb"),"sha256").hexdigest()
 manifest["inputs"][key]={"url":url,"sha256":digest,"size_bytes":path.stat().st_size}
 return path
def csv(name,frame):frame.to_csv(OUT/name,index=False)
try:
 data_path=dl("harveststat_csv")
 boundary_path=dl("harveststat_boundaries")
 tfdd_path=dl("tfdd2024")
 with zipfile.ZipFile(tfdd_path) as z:
  assert z.testzip() is None
  files=[x for x in z.namelist() if pathlib.PurePosixPath(x).name.startswith("BCUMaster313_20240807.")]
  assert any(x.lower().endswith(".shp") for x in files),files
  z.extractall(TMP/"tfdd",members=files)
 shp=list((TMP/"tfdd").rglob("BCUMaster313_20240807.shp"))[0]
 tab=pd.read_csv(data_path,low_memory=False)
 expected={"fnid","country","country_code","product","harvest_year","qc_flag","area","production","yield"}
 assert expected<=set(tab.columns),f"Missing HarvestStat fields: {expected-set(tab.columns)}"
 for c in ("harvest_year","qc_flag","yield","area","production"):
  tab[c]=pd.to_numeric(tab[c],errors="coerce")
 tab["has_yield"]=tab["yield"].notna()&(tab["yield"]>0)
 tab["has_area"]=tab["area"].notna()&(tab["area"]>0)
 tab["has_production"]=tab["production"].notna()&(tab["production"]>0)
 tab["qc_ok"]=tab["qc_flag"].eq(0)
 tab["joint_valid"]=tab["has_yield"] & tab["has_area"] & tab["has_production"] & tab["qc_ok"] & tab["harvest_year"].notna()
 tab["production_over_area"]=tab["production"]/tab["area"].replace(0,np.nan)
 tab["rel_disagreement"]=abs(tab["production_over_area"]-tab["yield"])/tab["yield"].where(tab["yield"]>0)
 manifest["harveststat"]={
  "total_rows":int(len(tab)),
  "countries":int(tab.country_code.nunique()),"admin_fnid":int(tab.fnid.nunique()),
  "crops":int(tab["product"].nunique()),"observed_years":int(tab.harvest_year.nunique()),
  "year_min":str(tab.harvest_year.min()),"year_max":str(tab.harvest_year.max()),
  "positive_yield_rows":int(tab.has_yield.sum()),
  "positive_area_rows":int(tab.has_area.sum()),
  "positive_production_rows":int(tab.has_production.sum()),
  "joint_valid_rows":int(tab.joint_valid.sum()),
  "missing_harvest_year":int(tab.harvest_year.isna().sum()),
  "qc_counts":{str(k):int(v) for k,v in tab.qc_flag.fillna(-999).value_counts().items()},
  "ratio_mismatch_20pct_flag":int((tab.joint_valid & (tab.rel_disagreement>0.20)).sum()),
  "duplicate_fnid_crop_season_year":None
 }
 keys=["fnid","product","season_name","harvest_year","crop_production_system"]
 keys=[x for x in keys if x in tab.columns]
 manifest["harveststat"]["duplicate_fnid_crop_season_year"]=int(tab.duplicated(keys,keep=False).sum())
 country=tab.groupby(["country_code","country"],dropna=False).agg(
  rows=("fnid","size"),admin_units=("fnid","nunique"),crops=("product","nunique"),
  first_year=("harvest_year","min"),last_year=("harvest_year","max"),
  yield_valid=("has_yield","sum"),area_valid=("has_area","sum"),
  production_valid=("has_production","sum"),joint_valid=("joint_valid","sum"),qc_ok=("qc_ok","sum")).reset_index()
 csv("country_coverage.csv",country)
 crops=tab.groupby(["country_code","product","harvest_year"],dropna=False).agg(
  rows=("fnid","size"),admin_units=("fnid","nunique"),valid_units=("joint_valid","sum"),
  positive_yield=("has_yield","sum"),positive_area=("has_area","sum"),positive_production=("has_production","sum"),
  qc_ok=("qc_ok","sum")).reset_index()
 csv("country_crop_year_coverage.csv",crops)
 qct=tab.groupby(["country_code","qc_flag"],dropna=False).size().rename("rows").reset_index()
 csv("country_qc_counts.csv",qct)
 admin=gpd.read_file(boundary_path)
 bcu=gpd.read_file(shp)
 assert "fnid" in admin.columns and "BCCODE" in bcu.columns and "CCODE" in bcu.columns
 assert admin.crs is not None and bcu.crs is not None,(admin.crs,bcu.crs)
 assert admin.fnid.notna().all()
 # Geographic coverage is based on ADMINISTRATIVE area only, not observed planted locations.
 admin=admin[["fnid","country_code","geometry"]].dropna(subset=["geometry"]).copy()
 admin=admin.drop_duplicates(subset="fnid")
 bcu=bcu[["BCCODE","BCODE","Basin_Name","CCODE","geometry"]].dropna(subset=["geometry"]).copy()
 admin=admin.to_crs(6933);bcu=bcu.to_crs(6933)
 admin["geometry"]=admin.geometry.make_valid()
 bcu["geometry"]=bcu.geometry.make_valid()
 admin["admin_km2"]=admin.geometry.area/1e6
 import pycountry
 def iso3(x):
  try:return pycountry.countries.get(alpha_2=str(x).upper()).alpha_3
  except:return None
 admin["iso3"]=admin.country_code.apply(iso3)
 # Check country identification before assigning BCU IDs.
 bcu["CCODE"]=bcu["CCODE"].astype(str).str.upper()
 unknown=admin[admin.iso3.isna()]
 manifest["spatial"]={"admin_geometries":int(len(admin)),"bcu_geometries":int(len(bcu)),
  "country_codes_unmatched":sorted(unknown.country_code.dropna().unique().tolist())}
 admin2=admin[admin.iso3.notna()].copy()
 overlaps=[]
 # Run country-wise to prevent unrelated border-touching polygons from dominating.
 for code,aa in admin2.groupby("iso3"):
  bb=bcu[bcu.CCODE==code]
  if bb.empty:continue
  joined=gpd.overlay(aa[["fnid","country_code","admin_km2","geometry"]],
                    bb[["BCCODE","BCODE","Basin_Name","geometry"]],how="intersection",keep_geom_type=True)
  if joined.empty:continue
  joined["overlap_km2"]=joined.geometry.area/1e6
  joined["admin_area_fraction"]=(joined.overlap_km2/joined.admin_km2).clip(upper=1)
  joined=joined[joined.overlap_km2>0.01]
  if len(joined):overlaps.append(pd.DataFrame(joined.drop(columns="geometry")))
 if overlaps:
  cross=pd.concat(overlaps,ignore_index=True)
  cross=cross.sort_values(["fnid","admin_area_fraction","BCCODE"],ascending=[True,False,True])
 else:
  cross=pd.DataFrame(columns=["fnid","country_code","admin_km2","BCCODE","BCODE","Basin_Name","overlap_km2","admin_area_fraction"])
 csv("admin_bcu_fraction_crosswalk.csv",cross)
 chosen=cross.drop_duplicates("fnid").copy()
 chosen=chosen.rename(columns={"admin_area_fraction":"dominant_share","BCCODE":"dominant_bcu"})
 chosen["dominant_ge_80pct"]=chosen["dominant_share"]>=0.8
 # This map assigns each district to at most 1 BCU. Reject weak assignments in model dataset.
 assigned=chosen[["fnid","dominant_bcu","dominant_share","dominant_ge_80pct","Basin_Name","BCODE"]]
 csv("dominant_bcu_assignment.csv",assigned)
 by_admin=tab.groupby("fnid").agg(rows=("fnid","size"),joint_valid_rows=("joint_valid","sum"),first_year=("harvest_year","min"),last_year=("harvest_year","max"),n_crops=("product","nunique")).reset_index()
 coverage=by_admin.merge(assigned,on="fnid",how="left",validate="one_to_one")
 csv("admin_coverage_and_assignment.csv",coverage)
 good=tab.loc[tab.joint_valid,["fnid","country_code","product","harvest_year"]].merge(
   assigned.loc[assigned.dominant_ge_80pct,["fnid","dominant_bcu"]],
   on="fnid",how="inner",validate="many_to_one")
 candidate=good.groupby(["dominant_bcu","country_code","product"]).agg(
  valid_admin_crop_year_rows=("fnid","size"),unique_admin=("fnid","nunique"),
  distinct_years=("harvest_year","nunique"),
  first_year=("harvest_year","min"),last_year=("harvest_year","max")).reset_index()
 csv("bcu_crop_observed_years.csv",candidate)
 manifest["spatial"].update({
 "administrative_units_intersecting_bcu":int(cross.fnid.nunique()),
 "with_dominant_bcu":int(len(chosen)),
 "dominant_share_ge_80pct":int(chosen.dominant_ge_80pct.sum()),
 "admin_units_ambiguous_or_not_in_bcu":int(len(admin)-chosen.dominant_ge_80pct.sum()),
 "bcu_with_at_least_one_valid_admin_crop_year":int(candidate.dominant_bcu.nunique()),
 "distinct_bcu_with_any_polygon_overlap":int(cross.BCCODE.nunique()),
 "valid_fnid_crop_year_rows_assigned_80pct":int(len(good))
 })
 manifest["status"]="COMPLETE"
except Exception as e:
 import traceback
 manifest["status"]="FAILED";manifest["error"]=repr(e);manifest["traceback"]=traceback.format_exc()
finally:savej("audit_provenance.json",manifest)
print(json.dumps({k:v for k,v in manifest.items() if k not in ("inputs",)},ensure_ascii=False,indent=2))
if manifest["status"]!="COMPLETE":sys.exit(1)
