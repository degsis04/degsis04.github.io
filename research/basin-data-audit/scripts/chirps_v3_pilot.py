"""CHIRPS v3 monthly precipitation *source validation* pilot for African TFDD BCU.

Four source GeoTIFFs = two Januarys and two Augusts. No invented values,
no yearly anomalies, no naturalized-runoff inference.
Mean precipitation: mask TFDD BCU geometry in raster CRS and compute
latitude-weighted mean of monthly raster pixels (mm/month).
CHC official: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/
DOI: https://doi.org/10.15780/G2JQ0P
"""
import datetime as dt, hashlib, json, os, pathlib, traceback, sys, zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import rasterio
from rasterio.mask import mask

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"hydromet_pilot";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"hydromet_chirps_v3";TMP.mkdir(parents=True,exist_ok=True)
TFDD="https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip"
CHC="https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/"
TFDD_SHA="379392939ea9bd306ddaf44def8dc04dee419a1a8f310268157fe16b97a87369"
MONTHS=["1985.01","1985.08","2010.01","2010.08"]
BASINS=["NGER","LKCH","VOLT","NILE","ZAMB"]
meta={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
 "status":"STARTED",
 "definition":"area-weighted monthly precipitation inside TFDD BCU, not upstream contributing catchment or river discharge",
 "variable":"CHIRPS v3 final monthly rainfall in mm/month",
 "sampling":"Only Jan/Aug 1985 and 2010 as raster/geography/unit smoke test; NOT a drought index or complete sample",
 "reference":"https://www.chc.ucsb.edu/data/chirps3",
 "source_doi":"https://doi.org/10.15780/G2JQ0P",
 "source_urls":[],"checks":[],"errors":[]}
def fetch(url):
 f=TMP/pathlib.Path(url).name
 if not f.exists():
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"HydrologicalAcademicReproducibility/1.0"}) as r:
   r.raise_for_status()
   with f.open("wb") as w:
    for c in r.iter_content(2**20):
     if c:w.write(c)
 with f.open("rb") as rd:sha=hashlib.file_digest(rd,"sha256").hexdigest()
 meta["source_urls"].append({"url":url,"sha256":sha,"bytes":f.stat().st_size})
 return f
def record_check(name,value):
 meta["checks"].append({"name":name,"pass":bool(value)})
 if not value:meta["errors"].append(name)
try:
 z=fetch(TFDD)
 record_check("TFDD source matches verified SHA-256",meta["source_urls"][-1]["sha256"]==TFDD_SHA)
 with zipfile.ZipFile(z) as arc:
  assert arc.testzip() is None
  shp=[x for x in arc.namelist() if x.endswith("BCUMaster313_20240807.shp")][0]
  arc.extractall(TMP/"tfdd")
 bcu=gpd.read_file(TMP/"tfdd"/shp)
 bcu=bcu.loc[bcu.BCODE.isin(BASINS),["BCODE","BCCODE","Basin_Name","CCODE","geometry"]].copy()
 record_check("5 named basins represented",set(bcu.BCODE)==set(BASINS))
 record_check("Unique BCU identifiers",bcu.BCCODE.is_unique)
 rows=[]
 for stamp in MONTHS:
  url=f"{CHC}chirps-v3.0.{stamp}.tif"
  file=fetch(url)
  with rasterio.open(file) as src:
   record_check(f"{stamp} single-band precipitation",src.count==1)
   record_check(f"{stamp} CRS recognized",src.crs is not None)
   record_check(f"{stamp} resolution ~0.05 degree",
                abs(src.transform.a-0.05)<.001 and abs(src.transform.e+0.05)<.001)
   record_check(f"{stamp} nonzero raster shape",src.width>0 and src.height>0)
   meta.setdefault("raster_metadata",{})[stamp]={
       "CRS":str(src.crs),"width":src.width,"height":src.height,
       "transform":tuple(src.transform),"dtype":src.dtypes[0],"nodata":src.nodata,
       "tags":src.tags(),"resolution":src.res,
       "bounds":tuple(src.bounds)}
   bb=bcu.to_crs(src.crs)
   for row in bb.itertuples(index=False):
    try:
     clipped, affine=mask(src,[row.geometry],crop=True,filled=False,all_touched=False)
     image=clipped[0]; values=np.asarray(image.data,dtype=float)
     valid=(~np.ma.getmaskarray(image))&np.isfinite(values)&(values>=0)
     n=int(valid.sum())
     if n:
      lat_center=np.array([affine.f+(r+0.5)*affine.e for r in range(values.shape[0])])
      # Equal-angular raster cells: spherical area ∝ cos(latitude), valid for this 0.05-degree grid.
      weights=np.cos(np.deg2rad(lat_center))[:,None]*valid
      mean=float(np.sum(np.where(valid,values,0)*weights)/weights.sum())
      lo=float(values[valid].min());hi=float(values[valid].max())
     else:
      mean=None;lo=None;hi=None
     rows.append({"month":stamp,"BCODE":row.BCODE,"Basin_Name":row.Basin_Name,
                  "BCCODE":row.BCCODE,"country_3letter":row.CCODE,
                  "precip_mean_mm_month":mean,"valid_pixel_centers":n,
                  "min_pixel_mm":lo,"max_pixel_mm":hi,
                  "measurement":"area-weighted CHIRPS BCU grid-cell estimate",
                  "status":"ok" if n else "no_valid_grid_cells"})
    except ValueError as e:
     rows.append({"month":stamp,"BCODE":row.BCODE,"Basin_Name":row.Basin_Name,
                  "BCCODE":row.BCCODE,"country_3letter":row.CCODE,
                  "precip_mean_mm_month":None,"valid_pixel_centers":0,
                  "min_pixel_mm":None,"max_pixel_mm":None,
                  "measurement":"not available","status":"outside raster domain: "+str(e)})
 df=pd.DataFrame(rows)
 df.to_csv(OUT/"chirps_v3_bcu_four_months.csv",index=False)
 record_check("At least one BCU/month valid",df.valid_pixel_centers.gt(0).any())
 record_check("No negative area-average rainfall",
              df.precip_mean_mm_month.dropna().ge(0).all())
 meta["n_BCU"]=bcu.BCCODE.nunique()
 meta["n_rows"]=len(df)
 meta["valid_bcu_months"]=int(df.precip_mean_mm_month.notna().sum())
 meta["status"]="COMPLETE" if not meta["errors"] else "FAILED"
except Exception as e:
 meta["errors"].append(repr(e));meta["traceback"]=traceback.format_exc();meta["status"]="FAILED"
finally:
 (OUT/"hydromet_provenance.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf8")
 print(json.dumps({k:v for k,v in meta.items() if k not in ("raster_metadata","source_urls")},ensure_ascii=False,indent=2,default=str))
if meta["status"]!="COMPLETE":raise SystemExit(1)
