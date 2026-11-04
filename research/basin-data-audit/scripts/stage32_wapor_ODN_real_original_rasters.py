"""Stage32: real, source-verified FAO WaPOR v3 ODN Level 3 annual AETI GeoTIFF pilot.
No GIS map pretending entire L3 product footprint = irrigated rice scheme.
No secret token or credentials. Pixels and units checked against original FAO JSON/GeoTIFF.
"""
import pathlib,os,re,json,csv,hashlib,requests,datetime,traceback,sys,math
import numpy as np
import rasterio
from rasterio.windows import Window
R=pathlib.Path(__file__).resolve().parents[1]
OUT=R/"results"/"stage32_wapor_odon_real_rasters"
OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"stage32_WaPOR_OriginalRaster_Only"
TMP.mkdir(parents=True,exist_ok=True)
YEARS=[2018,2019,2020,2021,2022,2023]
BASE="https://gismgr.fao.org/DATA/WAPOR-3/MOSAICSET/L3-AETI-A/"
COL="WAPOR-3.L3-AETI-A.ODN."
SCIENCE=["FAO WaPOR Level 3 original raster 20 m Wapor V3, ODN thematic mosaic; NOT verified official service/command area polygon",
         "AETI = evapotranspiration + interception; it measures land-atmosphere water loss, not river diversion or irrigation delivery",
         "AETI annual pixel means mix rainfed/irrigated/nonagricultural land inside valid imagery, unless a true field mask exists",
         "FAO data corrected/re-released for Level 3 in 2024; original URL metadata and SHA256 are recorded for each raster",
         "Any temporal arithmetic uses only actual downloaded rasters, no fabricated values; missing years remain missing",
         "Neither raster nor source-derived mean identifies causal transboundary institution impacts"]
LOG={"status":"STARTED","run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "source_prefix":BASE,"catalog_product":"L3-AETI-A","region":"ODN","requested_years":YEARS,
     "constraints":SCIENCE,"source_inventory":[],"qa_checks":{},"failures":[]}
def check(k,c,d=None):
 LOG["qa_checks"][k]={"pass":bool(c),"details":d}
 if not c:raise AssertionError(f"{k}: {d}")
def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for z in iter(lambda:f.read(4*2**20),b""):h.update(z)
 return h.hexdigest()
def writecsv(name,rows,cols=None):
 if not rows:return
 if not cols:cols=list(rows[0])
 with (OUT/name).open("w",encoding="utf8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows)
def get(url):
 try:
  z=requests.get(url,timeout=(30,60),headers={"User-Agent":"PublicFAOWaPORThesisStage32/1.0"})
  return z
 except Exception as e:
  return e
def stream_download(url,target):
 if target.exists():return
 with requests.get(url,timeout=(30,270),stream=True,headers={"User-Agent":"PublicFAOWaPOR-ODN-ScientificQA/1.0"}) as r:
  if r.status_code!=200:raise RuntimeError(f"DATA http {r.status_code}: {url}")
  ctype=r.headers.get("content-type","")
  length=r.headers.get("Content-Length")
  size=0
  with target.open("wb") as f:
   for part in r.iter_content(2**20):
    if part:f.write(part);size+=len(part)
  if length and int(length)!=size:raise IOError(f"partial transfer {length} vs {size}")
  if size<50000:raise IOError(f"too small for actual TIFF: {size} {ctype}")
def blocks(src):
 for _,win in src.block_windows(1):
  vals=src.read(1,window=win,masked=True)
  yield win,vals
try:
 inventory=[]
 geodata={}
 for year in YEARS:
  prefix=COL+str(year)
  metaurl=BASE+prefix+".json"
  tifurl=BASE+prefix+".tif"
  row={"year":year,"source_json_url":metaurl,"source_tif_url":tifurl,
       "temporal_kind":"annual","Wapor_level":3,"nominal_ground_resolution_m":20,
       "raw_raster_downloaded":False,"status":"UNTESTED"}
  res=get(metaurl)
  if isinstance(res,Exception):
   row["metadata_error"]=str(res)[:280]
  else:
   row["metadata_http_status"]=res.status_code
   if res.status_code==200:
    b=res.content
    row["metadata_sha256"]=hashlib.sha256(b).hexdigest()
    row["metadata_bytes"]=len(b)
    try:
     j=res.json()
     row["json_metadata_keys"]=" | ".join(sorted(j)) if isinstance(j,dict) else repr(type(j))
     with (OUT/f"faometa_L3_ODN_AETI_A_{year}.json").open("w",encoding="utf8") as f:
      json.dump(j,f,indent=2,ensure_ascii=False)
     # Never assume "scale" = 0.1 from base-level docs; examine source tags separately.
     row["json_units_context"]=repr(j)[:1600]
    except Exception as e:row["metadata_json_decode_error"]=repr(e)
  tif=TMP/(prefix+".tif")
  try:
   stream_download(tifurl,tif)
   check("tiff_header_"+str(year),tif.open("rb").read(4) in
         (b"II*\x00",b"MM\x00*",b"II+\x00",b"MM\x00+"))
   row["source_tif_sha256"]=sha(tif)
   row["file_bytes"]=tif.stat().st_size
   row["raw_raster_downloaded"]=True
   with rasterio.open(tif) as ds:
    row.update({"crs":str(ds.crs),"width_pixels":ds.width,"height_pixels":ds.height,
        "res_x":ds.res[0],"res_y":ds.res[1],"nodata":ds.nodata,
        "tags":json.dumps(ds.tags(),ensure_ascii=False)[:2000],
        "band_tags":json.dumps(ds.tags(1),ensure_ascii=False)[:2000],
        "rasterio_scales":repr(ds.scales),
        "rasterio_units":repr(ds.units),"rasterio_offsets":repr(ds.offsets),
        "bounds_west":ds.bounds.left,"bounds_south":ds.bounds.bottom,
        "bounds_east":ds.bounds.right,"bounds_north":ds.bounds.top,
        "transform":repr(tuple(ds.transform)),
        "raster_image_pixel_area_m2":abs(ds.transform.a*ds.transform.e-ds.transform.b*ds.transform.d)})
    check("raster_has_crs_"+str(year),ds.crs is not None)
    check("raster_single_band_"+str(year),ds.count==1)
    check("raster_valid_resolution_"+str(year),0<ds.res[0]<=100 and 0<ds.res[1]<=100,ds.res)
    check("raster_mali_support_latlon_"+str(year),
          ds.crs is not None and ds.width>0 and ds.height>0)
    row["pixels_total"]=ds.width*ds.height
    sumraw=0.0;sqraw=0.0;nvalid=0;nzero=0;nneg=0;nonfinite=0;vmin=math.inf;vmax=-math.inf
    for window,v in blocks(ds):
     vals=v.compressed()
     if len(vals)==0:continue
     nonfinite+=int(np.count_nonzero(~np.isfinite(vals)))
     vals=vals[np.isfinite(vals)]
     if len(vals)==0:continue
     z=vals.astype(np.float64,copy=False)
     nvalid+=len(z);sumraw+=float(z.sum());sqraw+=float(np.dot(z,z))
     nzero+=int(np.count_nonzero(z==0));nneg+=int(np.count_nonzero(z<0))
     vmin=min(vmin,float(z.min()));vmax=max(vmax,float(z.max()))
    check("valid_numeric_pixels_"+str(year),nvalid>300 and nonfinite==0)
    row.update({"valid_pixels":nvalid,"valid_fraction":nvalid/(ds.width*ds.height),
       "nodata_count":ds.width*ds.height-nvalid,
       "raw_min":vmin,"raw_max":vmax,"raw_mean":sumraw/nvalid,
       "raw_std":math.sqrt(max(0,sqraw/nvalid-(sumraw/nvalid)**2)),
       "zero_raw_pixels":nzero,"negative_raw_pixels":nneg})
    check("physically_positive_AETI_raster_"+str(year),nneg==0,(nneg,vmin))
    row["status"]="REAL_TIFF_STATS_PASS"
   geodata[year]=row
  except Exception as e:
   row["status"]="TIFF_UNAVAILABLE"
   row["tiff_error"]=repr(e)
   LOG["failures"].append({"year":year,"message":repr(e),"type":"raster_download_or_decode"})
  inventory.append(row)
  LOG["source_inventory"].append({"year":year,"status":row["status"],
       "file_sha256":row.get("source_tif_sha256"),"bytes":row.get("file_bytes"),
       "error":row.get("tiff_error")})
 writecsv("wapor3_ODN_2018_2023_L3_AETI_A_REAL_original_raster_inventory.csv",inventory)
 pass_years=[int(z["year"]) for z in inventory if z["status"]=="REAL_TIFF_STATS_PASS"]
 LOG["actual_downloaded_years"]=pass_years
 if len(pass_years)>=2:
  # The common mask is exact pixel-to-pixel overlap only if all grids are identical.
  refs=[z for z in inventory if z["status"]=="REAL_TIFF_STATS_PASS"]
  base=refs[0]
  grid_equal=all(z["crs"]==base["crs"] and z["width_pixels"]==base["width_pixels"] and
     z["height_pixels"]==base["height_pixels"] and z["transform"]==base["transform"] for z in refs)
  LOG["same_spatial_grid_all_available_years"]=grid_equal
  if grid_equal:
   stats=[]
   with rasterio.open(TMP/(COL+str(base["year"])+".tif")) as ds0:
    # Common *valid* footprint, not a verified rice field mask.
    ss={int(z["year"]):{"sum":0.,"sum2":0.,"n":0} for z in refs}
    opened={int(z["year"]):rasterio.open(TMP/(COL+str(z["year"])+".tif")) for z in refs}
    try:
     for _,w in ds0.block_windows(1):
      arrays={y:src.read(1,window=w,masked=True) for y,src in opened.items()}
      mask=np.ones((int(w.height),int(w.width)),dtype=bool)
      for v in arrays.values():mask &= ~np.ma.getmaskarray(v) & np.isfinite(v.data)
      nn=int(mask.sum())
      if not nn:continue
      for y,v in arrays.items():
       zz=v.data[mask].astype(np.float64,copy=False)
       stat=ss[y];stat["n"]+=nn;stat["sum"]+=float(zz.sum());stat["sum2"]+=float(zz@zz)
    finally:
     for x in opened.values():x.close()
    nvals={v["n"] for v in ss.values()}
    check("all_years_identical_common_valid_sample",len(nvals)==1 and next(iter(nvals))>200)
    for y,v in ss.items():
     stats.append({"year":y,"common_valid_pixels":v["n"],
         "original_raw_pixel_mean":v["sum"]/v["n"],
         "original_raw_pixel_std":math.sqrt(max(0,v["sum2"]/v["n"]-(v["sum"]/v["n"])**2)),
         "units":"RAW FAO file values until publisher scaling and metadata verified",
         "pixel_mask":"intersection of ORIGINAL valid rasters for ALL downloaded years, not cropland mask"})
    writecsv("wapor3_ODN_common_valid_raster_footprint_2018_2023.csv",stats)
    LOG["common_valid_pixels"]=next(iter(nvals))
    LOG["n_raster_comparable_years"]=len(stats)
  else:LOG["common_mask_blocker"]="SOURCE GRIDS DIFFER: do not compare raw means or infer L3 spatial support."
 LOG["status"]="REAL_RASTER_STATS_PASS" if len(pass_years)>=2 else "NO_REAL_RASTER_STATISTICS"
except Exception as e:
 LOG["status"]="FAILED";LOG["error"]=repr(e);LOG["traceback"]=traceback.format_exc()[-5000:]
(OUT/"stage32_wapor_ODN_original_download_and_QA.json").write_text(
 json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
print(json.dumps({"status":LOG["status"],"years":LOG.get("actual_downloaded_years"),
  "common_pixel_count":LOG.get("common_valid_pixels"),
  "failures":LOG["failures"],"error":LOG.get("error")},ensure_ascii=False)[:6000])
sys.exit(0 if LOG["status"]=="REAL_RASTER_STATS_PASS" else 1)
