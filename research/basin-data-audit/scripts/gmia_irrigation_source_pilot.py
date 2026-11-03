"""FAO GMIA v5 official source & surface-water irrigation pilot.
Data circa 2005. Maps are statistical-modelled indicators at ~5' cells, not
crop-specific and NOT observed river abstraction or transboundary dependence.
 
Official map https://www.fao.org/aquastat/en/geospatial-information/global-maps-irrigated-areas/latest-version/
Siebert et al. (2013), Global Map of Irrigation Areas v5.
"""
import datetime as dt, hashlib, json, os, pathlib, traceback, zipfile
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"irrigation_pilot"
TMP=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"gmia_qa_v1"
OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
BASE="https://firebasestorage.googleapis.com/v0/b/fao-aquastat.appspot.com/o/GIS%2F"
SUFFIX="?alt=media&token="
SOURCES={
 "aei_ha":BASE+"gmia_v5_aei_ha_asc.zip"+SUFFIX+"416b27f5-fcb5-4178-ab49-1658d5c2c3ad",
 "aeisw_pct":BASE+"gmia_v5_aeisw_pct_aei_asc.zip"+SUFFIX+"38b7da06-ddfa-4500-90df-2db65e27c9a7",
 "aeigw_pct":BASE+"gmia_v5_aeigw_pct_aei_asc.zip"+SUFFIX+"ee5bd6d1-c8e2-44fd-a4cf-58d7563abbf6",
 "tfdd":"https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip"
}
EXPECTED_TFDD_SHA="379392939ea9bd306ddaf44def8dc04dee419a1a8f310268157fe16b97a87369"
BASINS=("NGER","VOLT","ZAMB")
log={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
     "source":"FAO AQUASTAT GMIA v5, c.2005 (Siebert et al. 2013)",
     "basins":BASINS,"source_files":[],"checks":{},"errors":[],
     "interpretation":{
       "area":"hectares equipped for irrigation; NOT actual annual irrigated or harvested area",
       "surface_pct":"percent of equipped area assigned to surface-water source; spatially coarse census-derived",
       "groundwater_pct":"percent of equipped area assigned to groundwater source; spatially coarse census-derived",
       "surface_water_proxy":"sum of equipped hectares × surface_percent / 100 for pixels with valid source percentage; NOT actual surface water withdrawals",
       "spatial_method":"cell-center polygon extraction on ~5-arcminute geographic raster (EPSG:4326 specified by FAO metadata; not embedded in ASCII); boundary fractions approximated; no crop-specific allocation",
       "causality":"No claim that source water originates in transboundary river; no model of river connectivity or annual water availability"}}
def qa(name, condition, detail=None):
 log["checks"][name]={"passed":bool(condition),"detail":detail}
 if not condition: log["errors"].append(name)
def download(key):
 url=SOURCES[key];f=TMP/(key+".zip")
 if not f.exists() or f.stat().st_size<1000:
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"Academic Irrigation Data QA 1.0"}) as r:
   r.raise_for_status()
   with f.open("wb") as w:
    for chunk in r.iter_content(2**20):
     if chunk:w.write(chunk)
 with f.open("rb") as stream:sha=hashlib.file_digest(stream,"sha256").hexdigest()
 log["source_files"].append({"key":key,"url":url,"sha256":sha,"bytes":f.stat().st_size})
 return f
def raster_for(key):
 f=download(key)
 with zipfile.ZipFile(f) as z:
  assert z.testzip() is None
  members=[n for n in z.namelist() if n.lower().endswith((".asc",".grd",".tif"))]
  qa("raster_zip_member_"+key,len(members)>0,{"member_names":members[:8]})
  if not members:raise RuntimeError(f"No raster found in FAO archive {key}")
  # One intended grid; otherwise explicit failure rather than silently picking any.
  if len(members)!=1:raise RuntimeError(f"Ambiguous raster files {key}: {members}")
  z.extract(members[0],TMP/key)
  path=TMP/key/members[0]
 with rasterio.open(path) as src:
  qa(key+"_grid_size",src.width==4320 and src.height==2160,
    {"width":src.width,"height":src.height,"res":src.res,"crs":str(src.crs),"nodata":src.nodata})
  qa(key+"_coordinate_domain_matches_official_geographic_grid", abs(src.bounds.left+180)<.001 and abs(src.bounds.right-180)<.001 and abs(src.bounds.top-90)<.001 and abs(src.bounds.bottom+90)<.001,{"bounds":tuple(src.bounds),"CRS_in_ASCII":str(src.crs),"assigned_CRS":"EPSG:4326 per FAO GMIA v5 documentation"})
 return path
try:
 aei=raster_for("aei_ha")
 surface=raster_for("aeisw_pct")
 ground=raster_for("aeigw_pct")
 shapes_zip=download("tfdd")
 qa("tfdd_source_sha",log["source_files"][-1]["sha256"]==EXPECTED_TFDD_SHA)
 with zipfile.ZipFile(shapes_zip) as z:
  assert z.testzip() is None
  p=next(n for n in z.namelist() if n.endswith("BCUMaster313_20240807.shp"))
  z.extractall(TMP/"tfdd")
 shp=TMP/"tfdd"/p
 bcu=gpd.read_file(shp)
 bcu=bcu.loc[bcu.BCODE.isin(BASINS),["BCODE","BCCODE","Basin_Name","CCODE","geometry"]].copy()
 qa("three_basins_loaded",set(bcu.BCODE)==set(BASINS),sorted(bcu.BCODE.unique()))
 rows=[]
 with rasterio.open(aei) as fa, rasterio.open(surface) as fs, rasterio.open(ground) as fg:
  qa("same_raster_shape",fa.shape==fs.shape==fg.shape,
     [fa.shape,fs.shape,fg.shape])
  qa("same_raster_geotransform",fa.transform==fs.transform==fg.transform)
  qa("same_raster_crs",fa.crs==fs.crs==fg.crs,{"note":"Arc/Info ASCII grid has no embedded CRS; official FAO metadata specifies geographic coordinates in decimal degrees"})
  projected=bcu.to_crs("EPSG:4326") # Explicit: FAO official GMIA v5 geographic grid, 5 arcminutes
  for ent in projected.itertuples(index=False):
   av,_=mask(fa,[ent.geometry],crop=True,filled=False,all_touched=False)
   sv,_=mask(fs,[ent.geometry],crop=True,filled=False,all_touched=False)
   gv,_=mask(fg,[ent.geometry],crop=True,filled=False,all_touched=False)
   a=np.ma.asarray(av[0],dtype=float)
   s=np.ma.asarray(sv[0],dtype=float)
   g=np.ma.asarray(gv[0],dtype=float)
   valid_a=(~np.ma.getmaskarray(a)) & np.isfinite(a.data) & (a.data>0)
   valid_s=(~np.ma.getmaskarray(s)) & np.isfinite(s.data) & (s.data>=0)&(s.data<=100)
   valid_g=(~np.ma.getmaskarray(g)) & np.isfinite(g.data) & (g.data>=0)&(g.data<=100)
   common=valid_a & valid_s & valid_g
   surface_eligible=valid_a & valid_s
   ground_eligible=valid_a & valid_g
   total_aei=float(a.data[valid_a].sum())
   known_s=float(a.data[surface_eligible].sum())
   known_g=float(a.data[ground_eligible].sum())
   s_ha=float((a.data[surface_eligible]*s.data[surface_eligible]/100).sum())
   g_ha=float((a.data[ground_eligible]*g.data[ground_eligible]/100).sum())
   if common.any():
    max_two=float((s.data[common]+g.data[common]).max())
   else: max_two=None
   rows.append({"BCODE":ent.BCODE,"BCCODE":ent.BCCODE,"Basin_Name":ent.Basin_Name,
      "CCODE":ent.CCODE,"aei_ha_estimate_approx_2005":total_aei,
      "surface_source_ha_proxy":s_ha,"groundwater_source_ha_proxy":g_ha,
      "equipped_ha_with_surface_pct":known_s,"equipped_ha_with_groundwater_pct":known_g,
      "fraction_aei_with_known_surface_pct":known_s/total_aei if total_aei else None,
      "surface_source_share_within_known_aei":s_ha/known_s if known_s else None,
      "groundwater_source_share_within_known_aei":g_ha/known_g if known_g else None,
      "n_cells_equipped":int(valid_a.sum()),
      "n_cells_surface_pct_known":int(surface_eligible.sum()),
      "n_cells_ground_pct_known":int(ground_eligible.sum()),
      "max_sum_sw_gw_pct_in_common_cells":max_two})
  out=pd.DataFrame(rows)
  out.to_csv(OUT/"gmia_v5_surface_groundwater_3basins_bcu.csv",index=False)
  qa("all_equipped_ha_nonnegative",(out.aei_ha_estimate_approx_2005>=0).all())
  qa("proxy_surface_not_greater_than_equipped",
     (out.surface_source_ha_proxy<=out.aei_ha_estimate_approx_2005+1e-5).all())
  qa("proxy_ground_not_greater_than_equipped",
     (out.groundwater_source_ha_proxy<=out.aei_ha_estimate_approx_2005+1e-5).all())
  log["n_bcu"]=len(out)
  log["n_bcu_with_irrigation_area"]=int((out.aei_ha_estimate_approx_2005>0).sum())
  log["equipped_ha_in_3basin_BCU_total"]=float(out.aei_ha_estimate_approx_2005.sum())
  log["known_surface_source_coverage_ratio"]=float(out.equipped_ha_with_surface_pct.sum()/out.aei_ha_estimate_approx_2005.sum()) if out.aei_ha_estimate_approx_2005.sum() else None
  log["status"]="COMPLETE" if not log["errors"] else "FAILED"
except Exception as e:
 log["status"]="FAILED";log["errors"].append(repr(e));log["traceback"]=traceback.format_exc()
finally:
 (OUT/"gmia_provenance.json").write_text(json.dumps(log,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf8")
 print(json.dumps({"status":log["status"],"errors":log["errors"],
                   "checks":log["checks"],"n_bcu":log.get("n_bcu")},ensure_ascii=False,indent=2,default=str))
if log["status"]!="COMPLETE":raise SystemExit(1)
