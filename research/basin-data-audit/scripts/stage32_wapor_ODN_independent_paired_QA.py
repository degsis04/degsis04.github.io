"""Independent true pixel-by-pixel FAO L3 ODN 2022/23 AETI change with immutable SHA checks.
Does not reuse primary Stage32 estimator, verifies source data and unit factor independently.
"""
import hashlib,requests,pathlib,os,json,datetime,traceback,sys,math,csv
import numpy as np,rasterio
R=pathlib.Path(__file__).resolve().parents[1];O=R/"results"/"stage32_wapor_odon_real_rasters";O.mkdir(parents=True,exist_ok=True)
T=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"wapor_paired_independent";T.mkdir(parents=True,exist_ok=True)
URL="https://gismgr.fao.org/DATA/WAPOR-3/MOSAICSET/L3-AETI-A/WAPOR-3.L3-AETI-A.ODN.{year}.tif"
SHA={2022:"79630cf7f168ad2e860b3495a7f61539d9c8fda391b8d2a6a5598abbc722d3c0",
     2023:"022b6857a1904aa6f691778943d27961defe77623a34ea4df3358fcb1bd69abf"}
EXPECTED={2022:1097.1952211894085,2023:1224.7875707628209}
LOG={"time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED","checks":{},
     "warning":"2,462,098 spatial pixels are not independent causal replicates; ODN valid-data region is not identified paddy/irrigation command polygon"}
def check(k,ok,d=None):
 LOG["checks"][k]={"pass":bool(ok),"details":d}
 if not ok:raise AssertionError(str(k)+": "+str(d))
try:
 for y in (2022,2023):
  f=T/(str(y)+".tif")
  if not f.exists():
   with requests.get(URL.format(year=y),stream=True,timeout=(35,220)) as r:
    r.raise_for_status()
    with f.open("wb") as out:
     for chunk in r.iter_content(2**20):
      if chunk:out.write(chunk)
  digest=hashlib.sha256(f.read_bytes()).hexdigest()
  check("same_original_SHA_"+str(y),digest==SHA[y],digest)
 with rasterio.open(T/"2022.tif") as a,rasterio.open(T/"2023.tif") as b:
  check("same_crs",a.crs==b.crs and str(a.crs)=="EPSG:32629")
  check("same_geo_grid",a.width==b.width and a.height==b.height and a.transform==b.transform)
  check("raster_scale_0_1",abs(a.scales[0]-0.1)<1e-15 and abs(b.scales[0]-0.1)<1e-15)
  A=a.read(1,masked=True);B=b.read(1,masked=True)
  m=(~np.ma.getmaskarray(A)) & (~np.ma.getmaskarray(B)) & np.isfinite(A.data) & np.isfinite(B.data)
  check("common_n",int(m.sum())==2462098,int(m.sum()))
  check("mask_unchanged_2years",bool(np.array_equal(np.ma.getmaskarray(A),np.ma.getmaskarray(B))))
  x=A.data[m].astype(np.float64)*a.scales[0]
  y=B.data[m].astype(np.float64)*b.scales[0]
  diff=y-x
  check("scaled_mean_reproduces_prior_2022",abs(float(x.mean())-EXPECTED[2022])<1e-9,float(x.mean()))
  check("scaled_mean_reproduces_prior_2023",abs(float(y.mean())-EXPECTED[2023])<1e-9,float(y.mean()))
  ch=100*(float(y.mean())/float(x.mean())-1)
  check("percent_independent_from_means",abs(ch-100*((float(y.sum())/float(x.sum()))-1))<1e-10,ch)
  LOG["year2022_2023"]={"source_years":[2022,2023],"unit":"mm/year scaled original FAO product",
   "full_valid_source_mask_Not_rice_polygon":True,
   "pixel_area_m2":400,"common_valid_pixels":len(diff),
   "product_valid_footprint_km2":len(diff)*400/1e6,
   "2022_mean_mm_year":float(x.mean()),"2023_mean_mm_year":float(y.mean()),
   "change_mean_mm_year":float(diff.mean()),"change_percent_on_region_mean":ch,
   "pixel_change_median_mm_year":float(np.median(diff)),
   "pixel_change_p10_mm_year":float(np.quantile(diff,.1)),
   "pixel_change_p90_mm_year":float(np.quantile(diff,.9)),
   "pixel_share_positive_change":float(np.mean(diff>0)),
   "pixel_share_negative_change":float(np.mean(diff<0)),
   "pixel_share_exactly_zero":float(np.mean(diff==0)),
   "pixel_change_std":float(np.std(diff)),
   "pixel_change_min":float(diff.min()),"pixel_change_max":float(diff.max()),
   "source_2022_SHA256":SHA[2022],"source_2023_SHA256":SHA[2023],
   "interpretation":"Actual ET+I total for valid product footprint, NOT river abstraction, NOT rice-crop-only"}
  check("diff_identity",abs(float(diff.mean())-float(y.mean())+float(x.mean()))<1e-9)
  check("proportion_sums_one",abs(LOG["year2022_2023"]["pixel_share_positive_change"]+
    LOG["year2022_2023"]["pixel_share_negative_change"]+
    LOG["year2022_2023"]["pixel_share_exactly_zero"]-1)<1e-12)
  LOG["status"]="PASS_PIXELWISE_INDEPENDENT"
except Exception as ex:
 LOG["status"]="FAILED";LOG["error"]=repr(ex);LOG["traceback"]=traceback.format_exc()[-5000:]
(O/"wapor3_ODN_2022_2023_INDEPENDENT_pixel_change_QA.json").write_text(
 json.dumps(LOG,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"status":LOG["status"],"result":LOG.get("year2022_2023"),
 "error":LOG.get("error")},ensure_ascii=False)[:4000])
sys.exit(0 if LOG["status"]=="PASS_PIXELWISE_INDEPENDENT" else 1)
