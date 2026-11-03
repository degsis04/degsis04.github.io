"""Independent CHIRPS v3 physical cross-validation against original month GeoTIFFs.

A separate algorithm (rasterio.mask + direct latitude-weighted pixel average)
compares saved district/month panel from rasterize + bincount. Detects geospatial
overlap/zone-ID mistakes that simple row-count QA misses.

Tests 3 districts for each of NGER/VOLT/ZAMB in Jan 1985 and Aug 2010.
Uses pinned official HarvestStat boundary SHA-256 and checks original CHIRPS
GeoTIFF SHA-256 from production provenance.
"""
import datetime as dt,hashlib,json,os,pathlib,sys,traceback
import numpy as np,pandas as pd,geopandas as gpd,requests,rasterio
from rasterio.mask import mask

ROOT=pathlib.Path(__file__).resolve().parents[1]
CLIMATE=ROOT/"results"/"climate_panel"
QA=ROOT/"results"/"climate_validation";QA.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"chirps_independent_validation";TMP.mkdir(exist_ok=True)
HS=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_boundaries"]
SAMPLE=[(1985,1),(2010,8)]
LOG={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
 "status":"STARTED","errors":[],"samples":[],"data_source":"official CHIRPS v3 monthly Africa final",
 "reference":"https://www.chc.ucsb.edu/data/chirps3",
 "methods":{"production":"rasterize all district polygons into single zone raster + cos(lat) bincount means",
           "independent":"rasterio.mask of individual polygon with original TIFF + cos(lat) mean",
           "tolerance_mm":.005,
           "climate":"rainfall mm/month, local district footprint, not crop specific or hydrological supply"}}
def readp(file,url,sha):
 if not file.exists():
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"Independent-Hydromet-Validation/1.0"}) as r:
   r.raise_for_status()
   with file.open("wb") as f:
    for blk in r.iter_content(2**20):
     if blk:f.write(blk)
 with file.open("rb") as f:actual=hashlib.file_digest(f,"sha256").hexdigest()
 if actual!=sha:raise ValueError(f"source modified {url} {actual} vs {sha}")
 return actual
try:
 boundary=TMP/"hvstat_africa_boundary_v1.2.gpkg"
 readp(boundary,HS["url"],HS["sha256"])
 cross=pd.read_csv(ROOT/"results"/"harveststat"/"dominant_bcu_assignment.csv")
 cross=cross.loc[cross.dominant_ge_80pct & cross.BCODE.isin(["NGER","VOLT","ZAMB"]),
                  ["fnid","BCODE"]].copy()
 geo=gpd.read_file(boundary)[["fnid","geometry"]].merge(cross,on="fnid",validate="one_to_one")
 # Fixed alphabetical precommit selection, not based on rainfall or model fit.
 pick=pd.concat([g.sort_values("fnid").head(3) for _,g in geo.groupby("BCODE")])
 assert pick.fnid.nunique()==9
 panel=pd.read_csv(CLIMATE/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
                   usecols=["fnid","year","month","rainfall_mm_month","valid_grid_cell_centres"])
 month_index={}
 for shard in ["1981_1991","1992_2002","2003_2013","2014_2024"]:
  j=json.loads((CLIMATE/f"chirps_provenance_{shard}.json").read_text())
  assert j["status"]=="COMPLETE"
  for x in j["source_file_hashes"]:
   if "year" in x:month_index[(int(x["year"]),int(x["month"]))]=x
 for year,month in SAMPLE:
  src=month_index[(year,month)]
  raster=TMP/f"chirps-v3.0.{year}.{month:02}.tif"
  readp(raster,src["url"],src["sha256"])
  with rasterio.open(raster) as t:
   polygons=pick.to_crs(t.crs)
   for d in polygons.itertuples(index=False):
    ma,transform=mask(t,[d.geometry],crop=True,filled=False,all_touched=False)
    arr=np.asarray(ma[0].data,dtype=float)
    valid=(~np.ma.getmaskarray(ma[0]))&np.isfinite(arr)&(arr>=0)
    lat=transform.f+(np.arange(arr.shape[0])+.5)*transform.e
    ww=np.cos(np.deg2rad(lat))[:,None] * valid
    actual=float((np.where(valid,arr,0)*ww).sum()/ww.sum()) if ww.sum()>0 else float("nan")
    a=panel.loc[panel.fnid.eq(d.fnid)&panel.year.eq(year)&panel.month.eq(month)]
    assert len(a)==1,(d.fnid,year,month,len(a))
    estimated=float(a.rainfall_mm_month.iloc[0])
    abs_error=abs(actual-estimated)
    LOG["samples"].append({
       "year":year,"month":month,"BCODE":d.BCODE,"fnid":d.fnid,
       "direct_independent_mask_mm":actual,"previous_zone_raster_mm":estimated,
       "abs_difference_mm":abs_error,"within_tolerance":bool(abs_error<=.005),
       "direct_valid_pixels":int(valid.sum()),
       "source_month_sha256":src["sha256"]})
 discrepancies=[x for x in LOG["samples"] if not x["within_tolerance"]]
 LOG["n_independent_checks"]=len(LOG["samples"])
 LOG["discrepancies"]=len(discrepancies)
 LOG["max_abs_diff_mm"]=max(x["abs_difference_mm"] for x in LOG["samples"])
 if discrepancies:
  LOG["status"]="FAILED"
  LOG["errors"].append("Independent district raster mask differs from production zone mask; audit shared borders/overlaps")
 else:LOG["status"]="COMPLETE"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(repr(e))
 LOG["traceback"]=traceback.format_exc()[-5000:]
finally:
 (QA/"independent_chirps_raster_validation.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
 print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],
 "n":LOG.get("n_independent_checks"),"max_abs_diff_mm":LOG.get("max_abs_diff_mm"),
 "discrepancies":LOG.get("discrepancies")},ensure_ascii=False,indent=2))
if LOG["status"]!="COMPLETE":sys.exit(1)
