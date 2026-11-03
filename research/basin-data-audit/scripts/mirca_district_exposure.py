"""Spatial screening of crop-specific irrigation within HarvestStat administrative units.
MIRCA-OS v2 source 5arcmin annual irrigated/rainfed harvested areas for 2015/2020;
TFDD-derived HarvestStat administrative assignment (>=80% same BCU).
No assumption that surface irrigation uses transboundary flow.
"""
import datetime,hashlib,json,os,pathlib,subprocess,zipfile,sys,traceback
import requests,numpy as np,pandas as pd,geopandas as gpd,rasterio
from rasterio.mask import mask
from rasterio.features import geometry_mask
from shapely.geometry import mapping

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"mirca_os"/"district_exposure";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"mirca_district";TMP.mkdir(exist_ok=True)
INDEX=json.loads((ROOT/"results"/"mirca_os"/"annual_archive_index.json").read_text())
HARVEST_META=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())
SRC=INDEX["official_catalog_metadata"]
YEARS=(2015,2020); CROPS=("Maize","Rice","Sorghum");SYS=("ir","rf");BASINS=("NGER","VOLT","ZAMB")
meta={"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"dataset":"MIRCA-OS v2 annual harvested area, original global 5arcmin grids",
      "version":"district crop exposure v0.1","status":"STARTED","errors":[],
      "units":"Harvested area in ha per raster cell; fraction of irrigated vs irrigated+rainfed harvested area",
      "note":"Administrative bounding data and MIRCA-OS are reconstructed/modelled and not field-level observed irrigation. At 5arcmin many small districts have zero pixel centers; do not infer zero cultivation without raster support.",
      "source_checks":{}}
def download(url,file,size=None):
 if not file.exists() or (size and file.stat().st_size!=size):
  with requests.get(url,stream=True,timeout=(30,300),allow_redirects=True,
      headers={"User-Agent":"University-Thesis-Open-Geodata-QA/1.0"}) as rr:
   rr.raise_for_status()
   with file.open("wb") as w:
    for chunk in rr.iter_content(1024*1024):
     if chunk:w.write(chunk)
 if size: assert file.stat().st_size==size,(file,size)
 with file.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
 return sha
def dump():
 (OUT/"district_exposure_provenance.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2,default=str)+"\n")
try:
 archive=TMP/"annual_5arcmin_v2.rar"
 hash_=download(SRC["url"],archive,SRC["size"])
 meta["source_checks"]["archive_sha256_matches_verified"]=(hash_==INDEX["sha256"])
 assert meta["source_checks"]["archive_sha256_matches_verified"]
 gpkg=TMP/"hvstat_africa_boundary_v1.2.gpkg"
 source=HARVEST_META["inputs"]["harveststat_boundaries"]
 sh=download(source["url"],gpkg,source["size_bytes"])
 meta["source_checks"]["HarvestStat_boundaries_sha256_matches_verified"]=(sh==source["sha256"])
 assert meta["source_checks"]["HarvestStat_boundaries_sha256_matches_verified"]
 
 members=[x["path"] for x in INDEX["raster_members"]]
 selected={}
 for year in YEARS:
  for crop in CROPS:
   for s in SYS:
    candidate=[n for n in members if n.endswith(f"/5-arcminute/MIRCA-OS_{crop}_{year}_{s}_v2.tif")]
    assert len(candidate)==1,(year,crop,s,candidate)
    selected[(year,crop,s)]=candidate[0]
 assert len(selected)==12
 cmd=["7z","x","-y",f"-o{TMP/'files'}",str(archive),*selected.values()]
 r=subprocess.run(cmd,text=True,capture_output=True,timeout=400)
 if r.returncode: raise RuntimeError(f"7z error {r.returncode}: {r.stderr[-1000:]} {r.stdout[-500:]}")
 
 assignments=pd.read_csv(ROOT/"results"/"harveststat"/"dominant_bcu_assignment.csv")
 chosen=assignments.loc[assignments.dominant_ge_80pct & assignments.BCODE.isin(BASINS),
  ["fnid","dominant_bcu","BCODE","dominant_share"]].copy()
 assert chosen.fnid.is_unique
 admin=gpd.read_file(gpkg)
 assert admin.fnid.is_unique
 admin=admin[["fnid","country_code","geometry"]].merge(chosen,on="fnid",how="inner",validate="one_to_one")
 assert not admin.empty
 meta["n_administrative_districts"]=len(admin)
 meta["districts_by_basin"]={str(k):int(v) for k,v in admin.groupby("BCODE").size().items()}
 
 # produce long simple cell-centre overlays, no fractional reconstruction.
 table=[]
 for (year,crop,system),f in selected.items():
  with rasterio.open(TMP/"files"/f) as src:
   assert src.crs is not None
   assert abs(src.res[0]-1/12)<.00001 and abs(src.res[1]-1/12)<.00001
   aa=admin.to_crs(src.crs)
   for ent in aa.itertuples(index=False):
    m,transform=mask(src,[ent.geometry],crop=True,filled=False,all_touched=False)
    a=np.asarray(m[0].data,dtype=float)
    geom_support=geometry_mask([mapping(ent.geometry)],out_shape=a.shape,transform=transform,
                     all_touched=False,invert=True)
    positive=geom_support & (~np.ma.getmaskarray(m[0])) & np.isfinite(a)&(a>0)
    total=float(a[positive].sum()) if positive.any() else 0
    table.append({"fnid":ent.fnid,"country_code":ent.country_code,"BCODE":ent.BCODE,
      "dominant_bcu":ent.dominant_bcu,"dominant_share":ent.dominant_share,
      "crop":crop,"reference_year":year,"system":system,
      "harvested_area_ha":total,"grid_cell_centres_inside_district":int(geom_support.sum()),
      "cells_with_positive_crop":int(positive.sum())})
 long=pd.DataFrame(table)
 keys=["fnid","country_code","BCODE","dominant_bcu","dominant_share","crop","reference_year"]
 ir=long.loc[long.system.eq("ir")].drop(columns="system").rename(columns={
  "harvested_area_ha":"irrigated_ha",
  "grid_cell_centres_inside_district":"grid_centres_inside_district",
  "cells_with_positive_crop":"ir_positive_cells"})
 rf=long.loc[long.system.eq("rf")][keys+["harvested_area_ha","cells_with_positive_crop"]].rename(columns={
  "harvested_area_ha":"rainfed_ha","cells_with_positive_crop":"rf_positive_cells"})
 panel=ir.merge(rf,on=keys,how="inner",validate="one_to_one")
 panel["crop_total_ha"]=panel.irrigated_ha+panel.rainfed_ha
 panel["fraction_irrigated"]=np.where(panel.crop_total_ha.gt(0),panel.irrigated_ha/panel.crop_total_ha,np.nan)
 panel["has_raster_support"]=panel.grid_centres_inside_district.gt(0)
 panel["crop_exposure_status"]=np.select([
     ~panel.has_raster_support,
     panel.has_raster_support & panel.crop_total_ha.eq(0),
     panel.has_raster_support & panel.crop_total_ha.gt(0)],
     ["NO_GRID_CENTER","NO_CROP_IN_SOURCE_MAP","POSITIVE_CROP_ESTIMATE"],
     default="ERROR")
 assert panel.fraction_irrigated.dropna().between(0,1).all()
 assert len(panel)==len(admin)*len(CROPS)*len(YEARS)
 panel.sort_values(["BCODE","dominant_bcu","fnid","crop","reference_year"]).to_csv(OUT/"district_irrigation_crop_share_2015_2020.csv",index=False)
 # Basin summary based on only the selected admin districts; no sample-wide extrapolation.
 agg=panel.groupby(["BCODE","crop","reference_year"],dropna=False).agg(
    n_districts=("fnid","nunique"),
    n_with_crop=("crop_total_ha",lambda s:int((s>0).sum())),
    n_without_pixel_centres=("has_raster_support",lambda s:int((~s).sum())),
    summed_irrigated_ha_selected_districts=("irrigated_ha","sum"),
    summed_rainfed_ha_selected_districts=("rainfed_ha","sum")).reset_index()
 agg["irrigated_harvested_fraction_selected_districts"]=agg.summed_irrigated_ha_selected_districts/(
    agg.summed_irrigated_ha_selected_districts+agg.summed_rainfed_ha_selected_districts).replace(0,np.nan)
 agg.to_csv(OUT/"selected_district_basin_crop_summary.csv",index=False)
 meta.update({"n_panel_rows":len(panel),"n_positive_crop_panel":int(panel.crop_total_ha.gt(0).sum()),
  "n_missing_pixel_support_panel":int((~panel.has_raster_support).sum()),
  "n_positive_irrigated_panel":int(panel.irrigated_ha.gt(0).sum()),
  "source_checks":meta["source_checks"],
  "status":"COMPLETE"})
except Exception as e:
 meta["status"]="FAILED";meta["errors"].append(str(e)[:400]);meta["traceback"]=traceback.format_exc()[-3000:]
finally:dump()
print(json.dumps({k:v for k,v in meta.items() if k not in ("source_checks","note")},ensure_ascii=False,indent=2))
if meta["status"]!="COMPLETE":sys.exit(1)
