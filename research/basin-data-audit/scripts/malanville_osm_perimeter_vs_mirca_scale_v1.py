"""Malanville candidate irrigated perimeter: source-pin actual OSM way geometry.

A mapped 'landuse=farmland' way labelled 'Périmètre de Malanville' is NOT
confirmed to be the 516 ha full irrigation scheme from peer-reviewed studies.
Compute independently its polygon area and overlap with original HarvestStat
district, and compare against 5 arc-minute MIRCA grid cell physical size.

No source claim that individual polygon fields use Niger river water is made.
"""
import pathlib,os,traceback,json,datetime as dt,hashlib,xml.etree.ElementTree as ET
import requests,geopandas as gpd,numpy as np,pandas as pd
from shapely.geometry import Polygon,Point,mapping
from pyproj import Geod
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/"results"/"water_source_gate_v1";OUT.mkdir(parents=True,exist_ok=True)
META={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),
 "status":"STARTED","errors":[],"checks":{},
 "source":"https://api.openstreetmap.org/api/0.6/way/387457345/full",
 "osm_ref":"way 387457345, Périmètre de Malanville (OSM farmland polygon), volunteer-mapped",
 "method":"OSM XML node geometry → polygon; within HarvestStat original district via EPSG:6933; cell area via WGS84 geodetic 5arcmin",
 "caveats":["OSM farmland footprint NOT a government-confirmed irrigated-rice command area",
 "Area comparison with 516ha from literature is diagnostic only; differences do not prove either source false",
 "A 5 arcmin MIRCA pixel may be much larger than an individual 516ha irrigated perimeter; no direct crop pixel-to-scheme mapping",
 "Precise canal intake/pump site is not established by this OSM way"]}
def ck(k,v,more=None):
 META["checks"][k]={"pass":bool(v),"detail":more}
 if not v:META["errors"].append(k)
try:
 u=META["source"]
 r=requests.get(u,timeout=(30,80),headers={"User-Agent":"AcademicResearchGISQA/1.0"})
 r.raise_for_status();raw=r.content
 META["OSM_XML_SHA256"]=hashlib.sha256(raw).hexdigest();META["OSM_XML_bytes"]=len(raw)
 doc=ET.fromstring(raw)
 ways=[w for w in doc.findall("way") if w.attrib["id"]=="387457345"]
 ck("exact_OSM_target_way",len(ways)==1,len(ways))
 way=ways[0]
 nds=[n.attrib.get("ref") for n in way.findall("nd")]
 nodes={n.attrib["id"]:(float(n.attrib["lon"]),float(n.attrib["lat"])) for n in doc.findall("node")}
 ck("all_way_nodes_in_OSM_full_response",all(n in nodes for n in nds),{"way_nodes":len(nds),"retrieved_nodes":len(nodes)})
 coords=[nodes[n] for n in nds]
 if coords[0]!=coords[-1]: coords.append(coords[0])
 poly=Polygon(coords)
 ck("OSM_site_polygon_geometrically_valid",poly.is_valid and not poly.is_empty,
    {"valid":poly.is_valid,"nodes":len(coords)})
 tags={t.attrib["k"]:t.attrib["v"] for t in way.findall("tag")}
 ck("OSM_area_tag_is_farmland",tags.get("landuse")=="farmland",tags)
 h=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())
 gsrc=h["inputs"]["harveststat_boundaries"]
 tfile=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"water_gate_admin_orig.gpkg"
 if not tfile.exists() or tfile.stat().st_size!=gsrc["size_bytes"]:
  with requests.get(gsrc["url"],stream=True,timeout=(30,180)) as rr:
   rr.raise_for_status()
   with tfile.open("wb") as f:
    for b in rr.iter_content(2**20):
     if b:f.write(b)
 with tfile.open("rb") as f:sha=hashlib.file_digest(f,"sha256").hexdigest()
 ck("same_pinned_HarvestStat_geometries",sha==gsrc["sha256"],sha)
 admin=gpd.read_file(tfile)
 fnid="BJ2015A20705"
 district=admin.loc[admin.fnid.eq(fnid)].to_crs("EPSG:6933")
 site=gpd.GeoSeries([poly],crs="EPSG:4326").to_crs("EPSG:6933").iloc[0]
 share=float(site.intersection(district.geometry.iloc[0]).area/site.area)
 ck("OSM_site_center_in_malanville_district",district.geometry.iloc[0].covers(site.representative_point()))
 ck("OSM_site_fraction_in_expected_admin_at_least_95percent",share>=.95,share)
 geod=Geod(ellps="WGS84")
 lats=[y for x,y in coords];lons=[x for x,y in coords]
 geom_area,_=geod.polygon_area_perimeter(lons,lats)
 footprint_ha=abs(geom_area)/10000
 lat=float(poly.centroid.y);lon=float(poly.centroid.x)
 # rectangular 5' grid cell (radius 2.5') centered on original feature,
 # not exact source raster grid alignment; valid area-order comparison.
 step=1/12
 corners_lon=[lon-step/2,lon+step/2,lon+step/2,lon-step/2,lon-step/2]
 corners_lat=[lat-step/2,lat-step/2,lat+step/2,lat+step/2,lat-step/2]
 cellarea,_=geod.polygon_area_perimeter(corners_lon,corners_lat)
 cell_area_ha=abs(cellarea)/10000
 META["results"]={
 "osm_tags":tags,"OSM_way_version":way.attrib.get("version"),
 "OSM_way_last_modified":way.attrib.get("timestamp"),
 "mapped_OSM_farmland_polygon_area_ha":footprint_ha,
 "literature_2015_irrigation_scheme_area_ha":516.0,
 "OSM_area_as_fraction_of_reported_literature_area":footprint_ha/516.0,
 "fraction_of_OSM_polygon_inside_BJ2015A20705":share,
 "representative_coord_lon":lon,"representative_coord_lat":lat,
 "approx_MIRCA_5arcmin_cell_area_ha_at_site_latitude":cell_area_ha,
 "literature_516ha_scheme_as_fraction_of_one_5arcmin_cell":516/cell_area_ha,
 "OSM_farmland_polygon_as_fraction_of_one_5arcmin_cell":footprint_ha/cell_area_ha}
 output={"type":"FeatureCollection",
  "name":"Malanville OSM FARMLAND boundary candidate, not authenticated irrigation parcel",
  "features":[{"type":"Feature","geometry":mapping(poly),
    "properties":{"osm_id":"way/387457345","fnid":fnid,"landuse":tags.get("landuse"),
       "data_quality":"VOLUNTEER_MAPPED_CANDIDATE_NOT_VERIFIED_IRRIGATED_PERIMETER",
       "source":u,"footprint_ha_geodetic":footprint_ha}}]}
 (OUT/"Malanville_OSM_cropland_boundary_UNVERIFIED_candidate.geojson").write_text(
  json.dumps(output,ensure_ascii=False,indent=2)+"\n")
 META["status"]="COMPLETE" if not META["errors"] else "FAILED"
except Exception as ex:
 META["status"]="FAILED";META["errors"].append(repr(ex))
 META["traceback"]=traceback.format_exc()[-3500:]
(OUT/"Malanville_OSM_footprint_and_MIRCA_pixel_resolution_QA.json").write_text(json.dumps(
 META,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":META["status"],"errors":META["errors"],
                  "checks":META["checks"],"results":META.get("results")},ensure_ascii=False,indent=2,default=str)[:14000])
if META["status"]!="COMPLETE":raise SystemExit(1)
