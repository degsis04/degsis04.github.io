"""EC JRC ASAP Crop Calendar spatial extraction and independent QA, eight countries.

Source: European Commission JRC ASAP (Dimou 2018), derived from FAO
agronomic calendar + satellite phenology; does NOT use HarvestStat
planting/harvest date labels in its construction.
- Official crop calendar GAUL1 archive, pinned SHA256
- Official ASAP GAUL1 spatial polygons, pinned SHA256
- Original HarvestStat v1.2 administrative geometry, pinned SHA256
- Independent spatial intersection, 80% threshold for a single province
Produces source-specific crop calendars & district->GAUL1 crosswalk, no
false crop-season matching or production-system equivalence claims.
"""
import datetime as dt,hashlib,io,json,os,pathlib,sys,traceback,zipfile
import numpy as np,pandas as pd,geopandas as gpd,requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"phenology_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"jrc_asap_crosswalk";TMP.mkdir(parents=True,exist_ok=True)
INV=json.loads((OUT/"jrc_asap_source_inventory.json").read_text())
H=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_boundaries"]
TARGET={"Burkina Faso":"BF","Mali":"ML","Benin":"BJ","Ghana":"GH",
        "Togo":"TG","Zimbabwe":"ZW","Zambia":"ZM","Malawi":"MW"}
CROPS=("Maize","Sorghum","Rice")
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "attribution":"EC-JRC ASAP 2018 FAO+satellite phenology calendar; World Bank 2025 mirror",
 "definition":"Source calendar is a reference growing-season window, not yearly observed onset",
 "units":"dekad index 1..36 (three approximate 10-day segments/month); not daily planting dates",
 "target":TARGET,"source_checks":[],"counts":{},"errors":[]}
def check(label,condition,details=None):
 LOG["source_checks"].append({"check":label,"pass":bool(condition),"details":details})
 if not condition:LOG["errors"].append(label)
def download(url,name,sha):
 p=TMP/name
 if not p.exists():
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"UniversityPhenologyScienceQA/1.0"}) as r:
   r.raise_for_status()
   with p.open("wb") as w:
    for chunk in r.iter_content(2**20):
     if chunk:w.write(chunk)
 with p.open("rb") as r:actual=hashlib.file_digest(r,"sha256").hexdigest()
 if actual !=sha:raise ValueError(f"SHA mismatch {name}: {actual} vs {sha}")
 LOG["source_checks"].append({"check":f"source_hash_{name}","pass":True,"details":actual})
 return p
try:
 s=INV["sources"]["jrc_gaul1_original"]
 src=download(s["url"],"jrc_crop_calendar_gaul1.zip",s["sha256"])
 with zipfile.ZipFile(src) as z:
  name=next(n for n in z.namelist() if n.endswith("crop_calendar_gaul1.csv"))
  raw=pd.read_csv(io.BytesIO(z.read(name)),sep=None,engine="python")
  note=next(n for n in z.namelist() if n.endswith("crop_calendar_gaul1_notes.txt"))
  (OUT/"jrc_gaul1_source_notes.txt").write_text(z.read(note).decode("cp1252",errors="replace"))
 raw["crop"]=raw.crop_name.astype(str).str.extract(r"^(Maize|Sorghum|Rice)\b",expand=False)
 sample=raw.loc[raw.name0_shr.isin(TARGET)&raw.crop.notna()].copy()
 for col in ("sos_s","sos_e","eos_s","eos_e"):
  sample[col]=pd.to_numeric(sample[col],errors="coerce")
  check(f"all_{col}_in_1_36",bool(sample[col].between(1,36).all()))
 check("valid_source_calendar_uniqueness",
       bool(not sample.duplicated(["asap1_id","crop_name"]).any()),
       int(sample.duplicated(["asap1_id","crop_name"],keep=False).sum()))
 sample["likely_year_crossing"]=(sample.eos_e<sample.sos_s)
 sample["phenology_source"]="JRC_ASAP_GAUL1_Fao_plus_remote_sensing"
 sample["annual_historical_onset_observed"]=False
 sample.to_csv(OUT/"jrc_asap_8countries_subnational_crop_dekads.csv",index=False)
 LOG["counts"]["subnational_crop_rows"]=len(sample)
 LOG["counts"]["coverage_by_country_crop"]=sample.groupby(["name0_shr","crop"]).size().reset_index(name="rows").to_dict("records")
 
 nat=INV["sources"]["jrc_gaul0_worldbank"]
 natp=download(nat["url"],"jrc_crop_calendar_gaul0.csv",nat["sha256"])
 natdf=pd.read_csv(natp,sep=None,engine="python",encoding="utf-8-sig")
 natdf["crop"]=natdf.crop_name.astype(str).str.extract(r"^(Maize|Sorghum|Rice)\b",expand=False)
 natdf=natdf.loc[natdf.name0_shr.isin(TARGET)&natdf.crop.notna()].copy()
 natdf["source"]="JRC_ASAP_GAUL0_national_reference_not_subnational"
 natdf.to_csv(OUT/"jrc_asap_8countries_national_crop_dekads.csv",index=False)
 LOG["counts"]["national_crop_rows"]=len(natdf)
 LOG["counts"]["national_by_country_crop"]=natdf.groupby(["name0_shr","crop"]).size().reset_index(name="rows").to_dict("records")
 
 z=INV["sources"]["jrc_gaul1_shapes"]
 geop=download(z["url"],"jrc_gaul1_asap_v05.zip",z["sha256"])
 with zipfile.ZipFile(geop) as arc:
  assert arc.testzip() is None
  shp=next(n for n in arc.namelist() if n.endswith("gaul1_asap.shp"))
  arc.extractall(TMP/"source_shape")
 geometry=gpd.read_file(TMP/"source_shape"/shp)
 LOG["shape_columns"]=list(geometry.columns)
 check("source_polygons_have_CRS",geometry.crs is not None,str(geometry.crs))
 check("has_asap1_id",("asap1_id" in geometry.columns),list(geometry.columns))
 if "asap1_id" not in geometry.columns:raise RuntimeError("Could not find ASAP1 ID; cannot join")
 geometry["asap1_id"]=pd.to_numeric(geometry.asap1_id,errors="coerce").astype("Int64")
 if geometry.asap1_id.duplicated().any():
  # if one ASAP ID split into multiple geometries, dissolve; but record it
  LOG["counts"]["source_duplicate_geo_ids"]=int(geometry.asap1_id.duplicated().sum())
  geometry=geometry.dissolve(by="asap1_id",as_index=False)
 else:LOG["counts"]["source_duplicate_geo_ids"]=0
 missing=set(sample.asap1_id.astype(int))-set(geometry.asap1_id.dropna().astype(int))
 check("all_source_crop_regions_have_polygon",not missing,sorted(missing)[:15])
 
 matched=geometry.loc[geometry.asap1_id.isin(sample.asap1_id.unique()),["asap1_id","geometry"]].copy()
 matched["geometry"]=matched.geometry.make_valid()
 matched=matched.to_crs("EPSG:6933")
 matched["source_poly_area_m2"]=matched.geometry.area
 harvest=download(H["url"],"HarvestStat_Africa_boundaries.gpkg",H["sha256"])
 admin=gpd.read_file(harvest)
 assert admin.fnid.is_unique
 assert "country_code" in admin.columns
 dominant=pd.read_csv(ROOT/"results"/"harveststat"/"dominant_bcu_assignment.csv")
 dominant=dominant.loc[dominant.dominant_ge_80pct & dominant.BCODE.isin(["NGER","VOLT","ZAMB"]),
                        ["fnid","BCODE","dominant_bcu"]]
 assert dominant.fnid.is_unique
 admin=admin[["fnid","country_code","geometry"]].merge(dominant,on="fnid",how="inner",validate="one_to_one")
 check("original_253_pilot_admin_districts",len(admin)==253,len(admin))
 admin=admin.to_crs("EPSG:6933")
 admin["geometry"]=admin.geometry.make_valid()
 admin["area_m2"]=admin.geometry.area
 # Spatial intersection within same country comes from calendars, not guessed source ID suffixes
 matched=matched.merge(sample[["asap1_id","name0_shr"]].drop_duplicates(),
                       on="asap1_id",validate="one_to_one")
 matched["country2"]=matched.name0_shr.map(TARGET)
 candidates=gpd.sjoin(admin,matched,predicate="intersects",how="inner")
 candidates=candidates.loc[candidates.country_code.eq(candidates.country2)].copy()
 lookup=matched.geometry.to_dict()
 candidates["overlap_m2"]=[a.intersection(lookup[j]).area
                           for a,j in zip(candidates.geometry,candidates.index_right)]
 candidates=candidates.loc[candidates.overlap_m2>1e4].copy()
 candidates["frac_district"]=candidates.overlap_m2/candidates.area_m2
 check("single_overlap_fraction_below_1",candidates.frac_district.le(1.00001).all(),
       {"max":float(candidates.frac_district.max()) if len(candidates) else None})
 x=candidates.groupby("fnid").frac_district.sum()
 check("no_large_source_polygon_overlap",x.le(1.02).all(),
       {"max":float(x.max()) if len(x) else None,
        "n_source_geom_sum_over102pct":int((x>1.02).sum())})
 candidates[["fnid","BCODE","dominant_bcu","country_code","asap1_id","name0_shr","frac_district","overlap_m2"]].to_csv(
   OUT/"harveststat_district_to_JRC_ASAP_gaul1_all_intersections.csv",index=False)
 
 order=candidates.sort_values(["fnid","frac_district"],ascending=[True,False])
 best=order.drop_duplicates("fnid").copy()
 best["jrc_mapping_ge80"]=best.frac_district.ge(.8)
 best["jrc_mapping_ge70"]=best.frac_district.ge(.7)
 best["jrc_mapping_ge90"]=best.frac_district.ge(.9)
 best[["fnid","BCODE","dominant_bcu","country_code","asap1_id","name0_shr","frac_district",
       "jrc_mapping_ge70","jrc_mapping_ge80","jrc_mapping_ge90"]].to_csv(
       OUT/"district_to_JRC_ASAP_gaul1_dominant_source.csv",index=False)
 LOG["counts"]["admin_with_any_JRC_cropping_calendar_polygon"]=int(best.fnid.nunique())
 LOG["counts"]["admin_ge80_JRC_province"]=int(best.jrc_mapping_ge80.sum())
 LOG["counts"]["admin_ge70_JRC_province"]=int(best.jrc_mapping_ge70.sum())
 LOG["counts"]["admin_ge90_JRC_province"]=int(best.jrc_mapping_ge90.sum())
 # Strict crop-specific calendar matches: no "national" fallback, no guessing season
 confirmed=best.loc[best.jrc_mapping_ge80,["fnid","BCODE","dominant_bcu","country_code",
                    "asap1_id","name0_shr","frac_district"]].merge(
  sample,on=["asap1_id","name0_shr"],how="inner",validate="many_to_many")
 confirmed.to_csv(OUT/"district_JRC_external_cropping_seasons.csv",index=False)
 LOG["counts"]["district_crop_season_calendar_rows"]=len(confirmed)
 LOG["counts"]["district_count_with_maize"]=int(confirmed.loc[confirmed.crop=="Maize","fnid"].nunique())
 LOG["counts"]["district_count_with_sorghum"]=int(confirmed.loc[confirmed.crop=="Sorghum","fnid"].nunique())
 LOG["counts"]["district_count_with_rice"]=int(confirmed.loc[confirmed.crop=="Rice","fnid"].nunique())
 LOG["counts"]["by_pilot_basin_crop"]=confirmed.groupby(["BCODE","crop"]).fnid.nunique().reset_index(name="districts").to_dict("records")
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(str(e)[:500]);LOG["traceback"]=traceback.format_exc()[-3500:]
(OUT/"jrc_spatial_crosswalk_provenance.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False,default=str)+"\n")
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"counts":LOG["counts"]},ensure_ascii=False,indent=2)[:10000])
if LOG["status"]!="COMPLETE":sys.exit(1)
