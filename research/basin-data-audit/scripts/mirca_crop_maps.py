"""MIRCA-OS v2 (March 2026) annual irrigated/rainfed harvested area maps.

Input: EXACT published HydroShare 284MB RAR, verified by MD5 catalog checksum
and SHA256 source inventory. Selected: Maize/Rice/Sorghum × 5 time slices
(2000/05/10/15/20) × ir/rf at 5-arcminute grid = 30 GeoTIFFs.
Output: reproducible BCU-level harvested-area estimates and 3 data-derived PNG maps.

DO NOT interpret area as hectares equipped for irrigation, actual surface-water
abstraction, or observed area for intermediate years.
BCU geographic summaries assign full raster-cell value by pixel center
(no fractional edge-cell area); boundary sensitivity remains a limitation.
"""
import datetime,hashlib,json,os,pathlib,re,subprocess,sys,traceback,zipfile
import requests,numpy as np,pandas as pd,geopandas as gpd,rasterio
from rasterio.mask import mask
from rasterio.plot import plotting_extent
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from shapely.ops import unary_union

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"mirca_os"/"crop_maps"
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"mirca_v2_selected";TMP.mkdir(parents=True,exist_ok=True)
OUT.mkdir(parents=True,exist_ok=True)
INDEX=ROOT/"results"/"mirca_os"/"annual_archive_index.json"
R="e4582ca0042148338bb5e0148b749ed6"
YEARS=(2000,2005,2010,2015,2020)
CROPS=("Maize","Rice","Sorghum")
SYSTEMS=("ir","rf")
BASINS=("NGER","VOLT","ZAMB")
TFDD="https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip"
TFDD_CORRECT="https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip"
EXPECTED_TFDD_SHA="379392939ea9bd306ddaf44def8dc04dee419a1a8f310268157fe16b97a87369"

LOG={"run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "product":"MIRCA-OS v2 annual harvested area maps, March 2026",
     "source":"https://www.hydroshare.org/resource/"+R+"/",
     "script_version":"1.0",
     "source_files":[],"checks":{},"errors":[],"status":"STARTED",
     "units":"hectares HARVESTED per 5-arcminute grid cell (not %; verified against dataset README)",
     "description":"3 crops x 5 modeled reference-year snapshots x irrigation/rainfed x 25 TFDD BCU",
     "geospatial_method":"pixel-centre in polygon, sum annual harvested area in ha without area weighting; no fractional boundary correction; all_touched=False",
     "source_limitations":"MIRCA maps are statistically downscaled; not measured field polygons, not evidence of transboundary source, not annual observations between 5-year snapshots."}
def test(name,yes,details=None):
 LOG["checks"][name]={"passed":bool(yes),"details":details}
 if not yes:LOG["errors"].append(name)
def save():
 (OUT/"mirca_crop_map_provenance.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
def download(url,path,expected_size=None):
 if not path.exists() or (expected_size and path.stat().st_size!=expected_size):
  with requests.get(url,stream=True,timeout=(30,300),headers={"User-Agent":"ThesisDataAudit-MIRCA-OS/1.0"},allow_redirects=True) as r:
   r.raise_for_status()
   with path.open("wb") as f:
    for chunk in r.iter_content(2**20):
     if chunk:f.write(chunk)
 if expected_size: assert path.stat().st_size==expected_size,("unexpected size",path.stat().st_size,expected_size)
 with path.open("rb") as h:sha=hashlib.file_digest(h,"sha256").hexdigest()
 LOG["source_files"].append({"url":url,"bytes":path.stat().st_size,"sha256":sha})
 return path,sha
try:
 index=json.loads(INDEX.read_text())
 assert index["status"]=="COMPLETE" and index["md5_matches_catalog"],"Published source archive index not verified"
 archive_url=index["official_catalog_metadata"]["url"]
 arc,sha=download(archive_url,TMP/"Annual Harvested Area Grids.rar",index["official_catalog_metadata"]["size"])
 test("archive_sha_matches_verified_prior_inventory",sha==index["sha256"],{"sha256":sha})
 with arc.open("rb") as f:md5=hashlib.file_digest(f,"md5").hexdigest()
 test("archive_md5_matches_official_catalog",md5==index["md5"],{"md5":md5})
 real_members=[m["path"] for m in index["raster_members"]]
 selected={}
 for y in YEARS:
  for c in CROPS:
   for sysname in SYSTEMS:
    suffix=f"/5-arcminute/MIRCA-OS_{c}_{y}_{sysname}_v2.tif"
    match=[n for n in real_members if n.endswith(suffix)]
    assert len(match)==1,(suffix,match)
    selected[(y,c,sysname)]=match[0]
 test("exactly_30_source_geotiffs",len(selected)==30,len(selected))
 targetdir=TMP/"selected"
 cmd=["7z","x","-y",f"-o{targetdir}",str(arc),*selected.values()]
 proc=subprocess.run(cmd,capture_output=True,text=True,timeout=420)
 if proc.returncode:
  LOG["7z_error"]={"code":proc.returncode,"stdout":proc.stdout[-1500:],"stderr":proc.stderr[-1500:]}
  raise RuntimeError("7z selective extraction failed")
 for fn in selected.values():
  assert (targetdir/fn).is_file(),f"missing extracted map {fn}"
 LOG["source_selected_members"]=[{"year":y,"crop":c,"system":s,"path":path,
       "size":(targetdir/path).stat().st_size} for (y,c,s),path in selected.items()]
 
 tfdd, tfsha=download(TFDD_CORRECT,TMP/"TFDDSpatialDatabase_20240807.zip",67965338)
 test("TFDD_SHA_2024",tfsha==EXPECTED_TFDD_SHA,{"sha":tfsha})
 with zipfile.ZipFile(tfdd) as z:
  assert z.testzip() is None
  shp=next(p for p in z.namelist() if p.endswith("BCUMaster313_20240807.shp"))
  z.extractall(TMP/"tfdd")
 bcu=gpd.read_file(TMP/"tfdd"/shp)
 bcu=bcu.loc[bcu.BCODE.isin(BASINS),["BCODE","BCCODE","Basin_Name","CCODE","geometry"]].copy()
 test("BCU_count_25",len(bcu)==25,len(bcu))
 test("BCU_unique_IDs",bcu.BCCODE.is_unique,len(bcu))
 
 arrvals={}
 raster_meta=[]
 # For every source crop×year×system, sum actual geotiff cell values in relevant basin fragments.
 for (y,c,sysname),n in selected.items():
  with rasterio.open(targetdir/n) as src:
   test(f"raster_{y}_{c}_{sysname}_CRS",src.crs is not None,
        {"crs":str(src.crs),"units":src.units[0] if src.units else None})
   test(f"raster_{y}_{c}_{sysname}_grid_resolution",abs(src.res[0]-1/12)<1e-5 and abs(src.res[1]-1/12)<1e-5,
        {"res":src.res,"grid_shape":src.shape})
   raster_meta.append({"year":y,"crop":c,"system":sysname,"crs":str(src.crs),
                       "resolution":src.res,"width":src.width,"height":src.height,
                       "nodata":src.nodata,"band_unit_tag":src.units[0] if src.units else None,
                       "dtype":src.dtypes[0],"bounds":tuple(src.bounds)})
   bb=bcu.to_crs(src.crs)
   for row in bb.itertuples(index=False):
    ma,transform=mask(src,[row.geometry],crop=True,all_touched=False,filled=False)
    pixels=np.ma.asarray(ma[0],dtype=float)
    vals=np.asarray(pixels.data,dtype=float)
    valid=~np.ma.getmaskarray(pixels) & np.isfinite(vals) & (vals>=0)
    positive=valid & (vals>0)
    ha=float(vals[positive].sum()) if positive.any() else 0
    arrvals[(row.BCODE,row.BCCODE,row.CCODE,c,y,sysname)]={
      "crop_harvested_ha":ha,"n_positive_cells":int(positive.sum()),"n_valid_cells":int(valid.sum()),
      "max_ha_in_cell":float(vals[positive].max()) if positive.any() else 0}
 
 rows=[]
 for basin in BASINS:
  for bcu_id in sorted(bcu.loc[bcu.BCODE==basin,"BCCODE"]):
   code=str(bcu.loc[bcu.BCCODE==bcu_id,"CCODE"].iloc[0])
   for c in CROPS:
    for y in YEARS:
     a=arrvals[(basin,bcu_id,code,c,y,"ir")]
     rf=arrvals[(basin,bcu_id,code,c,y,"rf")]
     total=a["crop_harvested_ha"]+rf["crop_harvested_ha"]
     rows.append({"BCODE":basin,"BCCODE":bcu_id,"CCODE":code,
        "crop":c,"reference_year":y,
        "irrigated_harvested_ha":a["crop_harvested_ha"],
        "rainfed_harvested_ha":rf["crop_harvested_ha"],
        "total_harvested_ha":total,
        "irrigated_harvested_fraction":(a["crop_harvested_ha"]/total) if total>0 else None,
        "ir_positive_grid_cells":a["n_positive_cells"],
        "rf_positive_grid_cells":rf["n_positive_cells"],
        "is_annual_observation":False,
        "source":"MIRCA-OS v2 March 2026"})
 summary=pd.DataFrame(rows).sort_values(["BCODE","BCCODE","crop","reference_year"])
 summary.to_csv(OUT/"bcu_crop_irrigated_rainfed_2000_2020.csv",index=False)
 test("375_BCU_crop_reference_year_rows",len(summary)==375,len(summary))
 test("all_nonnegative_harvested_area",summary[["irrigated_harvested_ha","rainfed_harvested_ha"]].ge(0).all().all())
 test("irrigated_share_within_0_1",summary.irrigated_harvested_fraction.dropna().between(0,1).all())
 LOG["n_irrigated_positive_crop_BCU_years"]=int(summary.irrigated_harvested_ha.gt(0).sum())
 LOG["n_BCU_with_any_irrigated_crop_in_2020"]=int(summary.loc[summary.reference_year.eq(2020)&summary.irrigated_harvested_ha.gt(0),"BCCODE"].nunique())
 LOG["n_reference_year_rows"]=len(summary)
 LOG["raster_metadata"]=raster_meta
 
 # Scientific data-derived panels. Consistent crop-specific log-color scale across basins/years.
 map_files=[]
 shapes_4326=bcu.to_crs("EPSG:4326")
 for crop in CROPS:
  collected=[]
  for yy in (2000,2020):
   with rasterio.open(targetdir/selected[(yy,crop,"ir")]) as src:
    for basin in BASINS:
     geom=unary_union(shapes_4326.loc[shapes_4326.BCODE==basin,"geometry"].to_list())
     clip,trans=mask(src,[geom],crop=True,all_touched=False,filled=False)
     a=np.asarray(clip[0].data,dtype=float)
     positive=(~np.ma.getmaskarray(clip[0])) & np.isfinite(a) & (a>0)
     vals=np.where(positive,a,np.nan)
     extent=(trans.c,trans.c+trans.a*vals.shape[1],trans.f+trans.e*vals.shape[0],trans.f)
     collected.append((yy,basin,vals,extent))
  positives=np.concatenate([d[np.isfinite(d)] for y,b,d,e in collected if np.isfinite(d).any()])
  vmax=max(2,float(np.quantile(positives,.99))) if len(positives) else 2
  fig,axs=plt.subplots(3,2,figsize=(13,11),constrained_layout=True)
  for i,basin in enumerate(BASINS):
   for k,year in enumerate((2000,2020)):
    ax=axs[i,k]
    _,_,img,extent=next(r for r in collected if r[0]==year and r[1]==basin)
    im=ax.imshow(img,extent=extent,origin="upper",interpolation="nearest",
                 cmap="viridis",norm=LogNorm(vmin=1,vmax=vmax),aspect="auto")
    shapes_4326.loc[shapes_4326.BCODE==basin].boundary.plot(ax=ax,color="#444444",linewidth=.55)
    ax.set_title(f"{basin} • {crop} • irrigated • {year}",fontsize=10)
    ax.set_xlabel("Longitude");ax.set_ylabel("Latitude")
  fig.colorbar(im,ax=axs,location="right",fraction=.025,pad=.02,label="Harvested area (ha / 5-arcmin grid cell; log scale)")
  fig.suptitle("MIRCA-OS v2 (2026) — irrigated harvested areas, 2000 vs 2020",fontsize=12)
  png=OUT/f"map_{crop.lower()}_irrigated_2000_2020.png"
  fig.savefig(png,dpi=140,bbox_inches="tight")
  plt.close(fig)
  map_files.append(png.name)
 LOG["maps_created"]=map_files
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(repr(e));LOG["traceback"]=traceback.format_exc()
finally:
 save()
 print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],
                   "n_rows":LOG.get("n_reference_year_rows"),
                   "positive_ir_BCU":LOG.get("n_BCU_with_any_irrigated_crop_in_2020"),
                   "maps_created":LOG.get("maps_created")},ensure_ascii=False,indent=2))
if LOG["status"]!="COMPLETE":sys.exit(1)
