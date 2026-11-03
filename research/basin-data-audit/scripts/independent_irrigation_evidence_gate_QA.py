"""Independent second GIS/river-source gate audit (no import of producer script).
Use direct WGS84 geographic polygon containment and different join mechanism.
Read published whole-district rice source series and actual MIRCA model
outputs again, so numeric status is never accepted merely from producer.
"""
import pathlib,json,csv,hashlib,datetime as dt,traceback,sys,os
import geopandas as gpd,pandas as pd,requests
from shapely.geometry import shape
ROOT=pathlib.Path(__file__).resolve().parents[1]
D=ROOT/"results"/"water_source_gate_v1"
J={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","errors":[],"checks":{}}
def test(n,val,detail=None):
 J["checks"][n]={"pass":bool(val),"detail":detail}
 if not val:J["errors"].append(n)
def readcsv(p):
 with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
try:
 orig=json.loads((D/"intake_scheme_spatial_evidence_gate_QA.json").read_text())
 assert orig["status"]=="COMPLETE"
 sites=readcsv(D/"three_scheme_georeferenced_documentary_evidence.csv")
 decisions=readcsv(D/"three_scheme_physical_source_gate_and_outcome_table.csv")
 points=json.loads((D/"three_scheme_LANDMARK_points_not_intake.geojson").read_text())
 assert len(sites)==len(decisions)==len(points["features"])==3
 original_sha=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_boundaries"]
 file=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"verified_boundary_second_check.gpkg"
 if not file.exists() or file.stat().st_size!=original_sha["size_bytes"]:
  with requests.get(original_sha["url"],stream=True,timeout=(30,180)) as r:
   r.raise_for_status()
   with file.open("wb") as f:
    for b in r.iter_content(2**20):
     if b:f.write(b)
 with file.open("rb") as f:h=hashlib.file_digest(f,"sha256").hexdigest()
 test("independent_original_boundary_sha",h==original_sha["sha256"],h)
 polygons=gpd.read_file(file)[["fnid","country_code","geometry"]].to_crs("EPSG:4326")
 # robust geographic intersection via separate points GeoDataFrame / spatial index
 pg=gpd.GeoDataFrame(
   [{"case":p["properties"]["case"],
     "claimed_fnid":p["properties"]["fnid"],"geometry":shape(p["geometry"])} for p in points["features"]],
   crs="EPSG:4326")
 overlay=gpd.sjoin(pg,polygons,predicate="within",how="left")
 test("independent_wgs84_sjoin_exact_three",len(overlay)==3,len(overlay))
 test("all_point_administrative_ids_reproducible",bool((overlay.claimed_fnid==overlay.fnid).all()),
      overlay[["case","claimed_fnid","fnid"]].to_dict("records"))
 test("no_point_was_published_as_real_intake",
      all(p["properties"]["note"]=="NOT_VERIFIED_INTAKE_DO_NOT_SELECT_GAUGE" for p in points["features"]))
 test("referenced_linked_river_sources_three",all("http" in s["source_url"] for s in sites))
 # Don't accept producer G2: independently inspect source category direct condition:
 with (ROOT/"results"/"rice_feasibility"/"rice_series_production_system_audit.csv").open(newline="") as f:
  series=list(csv.DictReader(f))
 model=readcsv(ROOT/"results"/"mirca_os"/"district_exposure"/"district_irrigation_crop_share_2015_2020.csv")
 comparisons=[]
 for x in decisions:
  sid=x["fnid"]
  series_i=[r for r in series if r["fnid"]==sid]
  truly_labelled=[
   r for r in series_i if "irrigat" in r["crop_production_system"].casefold()
    and "rainfed" not in r["crop_production_system"].casefold()
    and int(float(r["valid_years"]))>=8
    and int(float(r["longest_consecutive"]))>=6
  ]
  test("outcome_type_confirm_"+x["case"],
    (len(truly_labelled)>0)==(x["direct_irrigated_rice_source_series_G2"]=="True"),
    {"n_series":len(truly_labelled),"source_label":[r["crop_production_system"] for r in truly_labelled]})
  # Recompute 2020 MIRCA ratio independently by reading actual irrigated/rainfed ha
  d=[r for r in model if r["fnid"]==sid and r["crop"]=="Rice" and r["reference_year"]=="2020"]
  if len(d)!=1:raise ValueError("Missing one per district source MIRCA")
  d=d[0];ha=float(d["irrigated_ha"]);rf=float(d["rainfed_ha"]);fraction=ha/(ha+rf)
  test("MIRCA_ha_and_fraction_"+x["case"],
       abs(ha-float(x["mirca2020_irrigated_rice_ha_modelled_whole_district"]))<1e-6 and
       abs(fraction-float(x["mirca2020_irrigated_rice_share_modelled_whole_district"]))<1e-12)
  test("scheme_has_no_unverified_treaty_or_hydropost_"+x["case"],
    x["implemented_treaty_for_this_intake_G5"]=="False" and
    x["selected_intake_specific_hydropost_G6"]=="False" and
    x["actual_field_to_intake_polygon_G3"]=="False")
  comparisons.append({"case":x["case"],"fnid":sid,
   "direct_irrigated_series_count_independent":len(truly_labelled),
   "MIRCA_2020_irrigated_fraction_recomputed":fraction})
 test("Sourou_only_separately_classified_8plus_year_rice",
      [c["case"] for c in comparisons if c["direct_irrigated_series_count_independent"]>0]==["SOUROU_NIASSAN"])
 J["results"]={"cases_checked":len(sites),"independent_WGS84_spatial_join":[
   {"case":r.case,"fnid":r.fnid} for r in overlay.itertuples(index=False)],
    "independent_rice_source_and_MIRCA":comparisons,
    "no_verified_intake_or_treaty_or_hydropost":True}
 J["status"]="PASS" if not J["errors"] else "FAILED"
except Exception as ex:
 J["status"]="FAILED";J["errors"].append(repr(ex))
 J["traceback"]=traceback.format_exc()[-3800:]
(D/"independent_water_source_site_geometry_and_outcome_QA.json").write_text(
 json.dumps(J,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":J["status"],"checks":J["checks"],"errors":J["errors"],
                  "results":J.get("results")},ensure_ascii=False,indent=2,default=str)[:16000])
if J["status"]!="PASS":sys.exit(1)
