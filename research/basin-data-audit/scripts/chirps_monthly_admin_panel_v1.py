"""Observed CHIRPS v3 FINAL monthly rainfall at district level for 3 pilot basins.

Input:
- UCSB CHC CHIRPS v3 monthly final Africa GeoTIFFs, 0.05 degrees, mm/month
- HarvestStat Africa v1.2 administrative GeoPackage, pinned SHA256
- Audited 80%-dominant TFDD-BCU assignment, Niger/Volta/Zambezi
Outputs:
- Actual 253-district by month observational climate panel, 1981-2024 in four 11-year shards
- Source URL/SHA256 per downloaded month
- Explicit pixel-center coverage and independent arithmetic checks.

No seasonal/crop windows or attribution to river discharge are assumed.
"""
import calendar, datetime as dt,hashlib,json,os,pathlib,sys,traceback,time
import numpy as np,pandas as pd,geopandas as gpd,rasterio,requests
from rasterio.features import rasterize

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"climate_panel";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"chirps_climate_panel";TMP.mkdir(parents=True,exist_ok=True)
START=int(os.environ.get("START_YEAR","1981"))
END=int(os.environ.get("END_YEAR","1991"))
assert 1981<=START<=END<=2024
PART=f"{START}_{END}"
SOURCE="https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/"
meta=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())
bound=meta["inputs"]["harveststat_boundaries"]
BASINS=("NGER","VOLT","ZAMB")
LOG={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "part":PART,"years_inclusive":[START,END],"source_dataset":"CHIRPS v3 final monthly Africa",
 "source_url_template":SOURCE+"chirps-v3.0.YYYY.MM.tif",
 "units":"mm per calendar month, NOT mm/day; gridded estimate incorporating stations, NOT raw station observations",
 "aggregation":"EPSG:4326 raster cell-centre assignment, cos(latitude) area-approx mean for each HarvestStat admin polygon",
 "target_districts":"at least 80% of administrative polygon area in one NGER/VOLT/ZAMB BCU; no cropped-area weights",
 "modeling_limits":"district local precipitation != actual upstream river flow, canal supply or crop-specific drought; no phenology assumptions",
 "source_file_hashes":[],"checks":[],"errors":[]}
def test(name,ok,details=None):
 LOG["checks"].append({"name":name,"pass":bool(ok),"details":details})
 if not ok:LOG["errors"].append(name)
def save(): (OUT/f"chirps_provenance_{PART}.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
def getfile(url,name,expected_sha=None,expected_size=None):
 file=TMP/name
 if not file.exists() or (expected_size and file.stat().st_size!=expected_size):
  with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"OpenAcademicHydroDataAudit/1.0"}) as r:
   r.raise_for_status()
   with file.open("wb") as f:
    for chunk in r.iter_content(2**20):
     if chunk:f.write(chunk)
 with file.open("rb") as fp:sha=hashlib.file_digest(fp,"sha256").hexdigest()
 if expected_sha is not None and sha !=expected_sha:
  raise RuntimeError(f"SHA256 mismatch for {name}: {sha} vs {expected_sha}")
 LOG["source_file_hashes"].append({"url":url,"sha256":sha,"bytes":file.stat().st_size})
 return file
try:
 gpk=getfile(bound["url"],"hvstat_africa_boundary_v1.2.gpkg",
             bound["sha256"],bound["size_bytes"])
 assign=pd.read_csv(ROOT/"results"/"harveststat"/"dominant_bcu_assignment.csv")
 assign=assign.loc[assign.dominant_ge_80pct & assign.BCODE.isin(BASINS),
   ["fnid","dominant_bcu","BCODE","dominant_share"]].copy()
 assert assign.fnid.is_unique
 admin=gpd.read_file(gpk)[["fnid","country_code","geometry"]]
 admin=admin.merge(assign,on="fnid",validate="one_to_one",how="inner")
 admin=admin.sort_values("fnid").reset_index(drop=True)
 test("253_districts",len(admin)==253,len(admin))
 test("unique_zone_ids",admin.fnid.is_unique)
 test("non_null_polygon_geometries",admin.geometry.notna().all() and (~admin.geometry.is_empty).all())
 # The climate raster and polygons have no user supplied coordinate operations.
 admin_4326=admin.to_crs("EPSG:4326")
 # Raster invariant from prior 1985/2010 CHIRPS pilot.
 label=None;weight=None;denominator=None;domain=None
 session=requests.Session()
 session.headers["User-Agent"]="University-Thesis-CHIRPS-Scientific-Audit/1.0"
 zoneids=np.arange(1,len(admin)+1,dtype=np.int16)
 records=[]
 for year in range(START,END+1):
  for mo in range(1,13):
   name=f"chirps-v3.0.{year}.{mo:02d}.tif"
   url=SOURCE+name
   temp=TMP/name
   # Each runner keeps only one source raster at a time; never commit raw rasters to Git.
   with session.get(url,stream=True,timeout=(30,180)) as resp:
    resp.raise_for_status()
    with temp.open("wb") as f:
     for chunk in resp.iter_content(2**20):
      if chunk:f.write(chunk)
   with temp.open("rb") as fp:sha=hashlib.file_digest(fp,"sha256").hexdigest()
   LOG["source_file_hashes"].append({"year":year,"month":mo,"url":url,"sha256":sha,"bytes":temp.stat().st_size})
   with rasterio.open(temp) as src:
    if label is None:
     domain=(src.shape,str(src.crs),tuple(src.transform))
     test("raster_resolution_0.05",abs(src.res[0]-.05)<.00001 and abs(src.res[1]-.05)<.00001,src.res)
     test("raster_crs_4326",src.crs.to_epsg()==4326,str(src.crs))
     shapes=[(geom,int(z)) for geom,z in zip(admin_4326.geometry,zoneids)]
     label=rasterize(shapes, out_shape=src.shape, transform=src.transform,
       fill=0,dtype="int16",all_touched=False)
     # independent rasterized-area coverage, because some districts smaller than 0.05 grid
     points=np.bincount(label.ravel(),minlength=len(admin)+1)
     test("at_least_one_cell_covered_by_zone",int((points[1:]>0).sum())>0,
       {"districts_with_pixel_centres":int((points[1:]>0).sum()),"without_centres":int((points[1:]==0).sum())})
     latgrid=src.transform.f + (np.arange(src.height)+.5)*src.transform.e
     weights=np.cos(np.deg2rad(latgrid)).astype("float64")
     test("positive_cell_area_weights",bool(np.all(weights>0)))
    else:
     if (src.shape,str(src.crs),tuple(src.transform)) != domain:
      raise RuntimeError(f"Raster grid differs across monthly files: {name}")
    v=src.read(1,masked=True)
    arr=np.asarray(v.data,dtype="float64")
    valid=(label>0)&(~np.ma.getmaskarray(v))&np.isfinite(arr)&(arr>=0)
    labs=label[valid].astype("int32")
    rw=np.broadcast_to(weights[:,None],arr.shape)[valid]
    denom=np.bincount(labs,weights=rw,minlength=len(admin)+1)
    numerator=np.bincount(labs,weights=arr[valid]*rw,minlength=len(admin)+1)
    count=np.bincount(labs,minlength=len(admin)+1)
    rainfall=np.divide(numerator,denom,out=np.full(len(denom),np.nan),where=denom>0)
    if np.any(rainfall[1:][np.isfinite(rainfall[1:])]<0):
     raise ValueError("negative CHIRPS monthly rainfall in valid polygons")
    for n,rec in enumerate(admin.itertuples(index=False),start=1):
     records.append({
       "fnid":rec.fnid,"country_code":rec.country_code,
       "BCODE":rec.BCODE,"BCCODE":rec.dominant_bcu,
       "dominant_share":rec.dominant_share,
       "year":year,"month":mo,
       "rainfall_mm_month":rainfall[n] if denom[n]>0 else np.nan,
       "valid_grid_cell_centres":int(count[n]),
       "grid_status":"VALID" if count[n]>=3 else "LOW_PIXEL_SUPPORT" if count[n]>0 else "NO_VALID_PIXEL_CENTRE",
       "source":"CHIRPS v3 final monthly Africa 0.05deg"})
   temp.unlink()
  print(f"Completed CHIRPS {year}: {len(records)} district-month rows",flush=True)
 panel=pd.DataFrame.from_records(records)
 expected=len(admin)*(END-START+1)*12
 test("expected_district_month_rows",len(panel)==expected,{"actual":len(panel),"expected":expected})
 test("unique_district_month",not panel.duplicated(["fnid","year","month"]).any())
 test("all_source_months_accounted_for",len(LOG["source_file_hashes"])==1+(END-START+1)*12)
 LOG["counts"]={"rows":len(panel),"months":(END-START+1)*12,"districts":len(admin),
   "valid_rainfall":int(panel.rainfall_mm_month.notna().sum()),
   "low_pixel_support":int(panel.grid_status.eq("LOW_PIXEL_SUPPORT").sum()),
   "no_valid_cell":int(panel.grid_status.eq("NO_VALID_PIXEL_CENTRE").sum()),
   "period":PART}
 panel.to_csv(OUT/f"chirps_v3_district_monthly_{PART}.csv",index=False)
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as ex:
 LOG["status"]="FAILED"
 LOG["errors"].append(repr(ex))
 LOG["traceback"]=traceback.format_exc()[-6000:]
finally:
 save()
 print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"counts":LOG.get("counts")},
                  indent=2,ensure_ascii=False))
if LOG["status"]!="COMPLETE":sys.exit(1)
