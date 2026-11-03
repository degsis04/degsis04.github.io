"""Geographic + crop-outcome evidence GATE for 3 Niger/Volta pilot irrigation schemes.

Scientific interpretation:
- This is NOT a hydrological river network topology model.
- An OSM village or dam centroid is never a verified irrigation INTAKE.
- Presence of an OSM farmland way is NOT proof it is the irrigated scheme.
- A documented source 'Niger River' is not evidence the crop yield rows
  were from that scheme; BCU membership is not river dependency.
- NO hydrological gauges are selected and no treaty effect is estimated.

Every main observation is rerun from pinned original HarvestStat v1.2
geometries; fuzzy place-name joins prohibited. Site exemplars taken from
public OSM features whose identifiers are recorded in the source register.
"""
import datetime as dt,json,pathlib,sys,traceback,os,hashlib,xml.etree.ElementTree as ET
import geopandas as gpd,pandas as pd,numpy as np,requests
from shapely.geometry import Point,Polygon,mapping
ROOT=pathlib.Path(__file__).resolve().parents[1]
RESULT=ROOT/"results"/"water_source_gate_v1";RESULT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"irrigation_intake_gate";TMP.mkdir(exist_ok=True)
H=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())
GPKG=H["inputs"]["harveststat_boundaries"]
SOURCE_REGISTER=[
{"case":"OFFICE_DU_NIGER","representative_point":"Markala diversion dam (NOT canal intake)","lat":13.68026,"lon":-6.08123,
 "osm_type":"way","osm_id":870511345,"osm_feature":"waterway=dam",
 "district_fnid":"ML2016A104","country_code":"ML","BCODE":"NGER",
 "site_point_accuracy":"OSM existing Markala dam geometry location; HEADREACH CANAL INTAKE NOT MAPPED",
 "water_source":"Niger River diverted at Markala / ~1 km upstream into feeder canal as documented in historical World Bank report",
 "water_source_evidence":"CONFIRMED_DOCUMENTARY","hydraulic_structure":"Gravity flow via headreach Canal du Sahel / Canal du Macina",
 "hydraulic_flow_risk":"Upstream Selingue national dam operations and non-irrigation withdrawals; no naturalized flow validation",
 "groundwater_or_other_sources":"scheme primary feeder river; crop fields outside Office du Niger may have other water sources",
 "source_url":"https://www.fao.org/in-action/remote-sensing-for-water-productivity/applications-and-uses/applications-catalogue/product-detail/ipon-irrigation-performance-of-office-du-niger91c04b58-9fed-47db-b874-c8e4b510228f/en",
 "additional_source_url":"https://documents1.worldbank.org/curated/en/107441468300653850/pdf/multi-page.pdf",
 "site_point_url":"https://mapcarta.com/fr/W870511345",
 "site_to_crop_outcome_confirmed":False,
 "upstream_other_country_documented":"Guinea upstream in Niger basin, but quantitative upstream contribution NOT demonstrated",
 "transboundary_rule_implementation_confirmed":False,
 "intake_coordinate_verified":False},
{"case":"MALANVILLE_RICE","representative_point":"OSM farmland site centroid, NOT confirmed pumping intake","lat":11.87688,"lon":3.37219,
 "osm_type":"way","osm_id":387457345,"osm_feature":"landuse=farmland; Malanville perimeter (unverified scheme boundary)",
 "district_fnid":"BJ2015A20705","country_code":"BJ","BCODE":"NGER",
 "site_point_accuracy":"OSM agricultural way candidate, peer-reviewed 516ha perimeter near 11°52′N 3°23′E; INTAKE NOT MAPPED",
 "water_source":"Niger River pumped into canals; groundwater boreholes ALSO cited in a separate field study; share unknown",
 "water_source_evidence":"CONFIRMED_DOCUMENTARY_MIXED_SOURCES",
 "hydraulic_structure":"Pumping river abstraction and canals, with possible parallel groundwater wells",
 "hydraulic_flow_risk":"Niger River border reach; hydrometric accessibility and local pumping schedules unknown",
 "groundwater_or_other_sources":"Boreholes documented, do not classify all 516 ha river-water-only",
 "source_url":"https://bec.uac.bj/uploads/publication/0367f163a1815fed1ebf7cc58c1cc96e.pdf",
 "additional_source_url":"https://pmc.ncbi.nlm.nih.gov/articles/PMC10714595/",
 "site_point_url":"https://mapcarta.com/fr/W387457345",
 "site_to_crop_outcome_confirmed":False,
 "upstream_other_country_documented":"Niger River has Mali/Niger upstream stretches; actual pumping-related cross-border water share unmeasured",
 "transboundary_rule_implementation_confirmed":False,
 "intake_coordinate_verified":False},
{"case":"SOUROU_NIASSAN","representative_point":"Niassan village near Sourou irrigation zone, NOT intake","lat":13.09583,"lon":-3.42530,
 "osm_type":"node","osm_id":902956256,"osm_feature":"place=village",
 "district_fnid":"BF2020A24606","country_code":"BF","BCODE":"VOLT",
 "site_point_accuracy":"OSM nearby village; irrigation perimeter and dam/inlet not accurately geocoded",
 "water_source":"Sourou river / Mouhoun (Black Volta) Leri regulated connection; variable flow direction",
 "water_source_evidence":"CONFIRMED_DOCUMENTARY_HYDRAULICALLY_COMPLEX",
 "hydraulic_structure":"Leri managed structure raises water, reversing flow seasonally in Sourou arm",
 "hydraulic_flow_risk":"River Sourou originates Mali yet Leri reverses Mouhoun↔Sourou flow; no fixed upstream country assignment",
 "groundwater_or_other_sources":"reservoir, floodplain, pumping; per-field portion undocumented",
 "source_url":"https://www.fao.org/4/x5158f/x5158f0r.htm",
 "additional_source_url":"https://www.diercke.com/content/sourou-burkina-faso-sahel-%E2%80%94-regional-self-sufficiency-farming-978-3-14-100790-9-159-4",
 "site_point_url":"https://mapcarta.com/N902956256",
 "site_to_crop_outcome_confirmed":False,
 "upstream_other_country_documented":"Sourou river rises in Mali, but managed flow reversal makes true upstream source DYNAMIC",
 "transboundary_rule_implementation_confirmed":False,
 "intake_coordinate_verified":False}
]
META={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "status":"STARTED","errors":[],"checks":{},
      "source_geometry":{"url":GPKG["url"],"expected_sha256":GPKG["sha256"],
                         "expected_size_bytes":GPKG["size_bytes"]},
      "source_site_register":"3 sites with site coordinates + independent water documents; OSM landmarks NOT intake coordinates",
      "geometry_check":"Point-in-polygon of exact FNID from pinned HarvestStat GPKG, EPSG:6933 distance from boundary",
      "criteria":{
        "G0":"Water source route directly named by documentary source",
        "G1":"Georeferenced site landmark safely inside correct HarvestStat district",
        "G2":"District has direct irrigated rice outcome stratum (source category only)",
        "G3":"Actual crop field/casier geometries linked to intake (NOT yet)",
        "G4":"Measured or demonstrable upstream transboundary volume contribution (NOT yet)",
        "G5":"Implemented transboundary governance clause controlling this withdrawal (NOT yet)",
        "G6":"Representative upstream hydrometric station for intake (NOT yet)"},
      "cautions":["Markala dam point is not canal intake; historical inlet approx 1km upstream, location may have changed",
      "OSM Malanville farmland shape is unverified as exact irrigated perimeter and may omit fields",
      "Sourou Niassan village is NOT Leri dam or any water-intake site",
      "Sourou/Mouhoun flow direction reversible: simple upstream gauge matching invalid",
      "Malanville river pumping AND groundwater reported, quantitative share unknown",
      "MIRCA modelled 5arcmin crop area 2020 not scheme polygon, not historically observed irrigated rice",
      "Direct label 'Plaine/Bas-fond irrigated (PS)' is broader than a canal scheme",
      "Hydroposts and implemented international rule effects remain blocked"],"technical_optional_sources":{}}
def check(k,b,detail=None):
 META["checks"][k]={"pass":bool(b),"details":detail}
 if not b:META["errors"].append(k)
def save():
 (RESULT/"intake_scheme_spatial_evidence_gate_QA.json").write_text(
  json.dumps(META,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
def download(src,path):
 if not path.exists() or path.stat().st_size!=src["size_bytes"]:
  with requests.get(src["url"],stream=True,timeout=(30,210),headers={"User-Agent":"GraduateThesisOpenGIS/1.0"}) as r:
   r.raise_for_status()
   with path.open("wb") as f:
    for b in r.iter_content(2**20):
     if b:f.write(b)
 with path.open("rb") as f:actual=hashlib.file_digest(f,"sha256").hexdigest()
 if actual!=src["sha256"]:raise AssertionError(f"Original geometry sha mismatch: {actual}")
 return actual

try:
 gp=TMP/"harveststat_admin_1.2.gpkg"
 sh=download(GPKG,gp)
 check("original_HarvestStat_geometries_sha256",sh==GPKG["sha256"],sh)
 admin=gpd.read_file(gp)[["fnid","country_code","geometry"]]
 check("original_districts_unique",admin.fnid.is_unique)
 admin=admin.loc[admin.fnid.isin([s["district_fnid"] for s in SOURCE_REGISTER])]
 check("all_three_expected_source_districts_found",len(admin)==3,admin.fnid.to_list())
 admin_6933=admin.to_crs("EPSG:6933")
 records=[]
 for src in SOURCE_REGISTER:
  p=gpd.GeoSeries([Point(src["lon"],src["lat"])],crs="EPSG:4326").to_crs("EPSG:6933").iloc[0]
  inside=admin_6933.loc[admin_6933.geometry.covers(p)]
  x=admin_6933.loc[admin_6933.fnid.eq(src["district_fnid"])]
  exact=bool(len(x)==1 and x.geometry.iloc[0].covers(p))
  distance=float(x.geometry.iloc[0].boundary.distance(p)/1000) if len(x)==1 else None
  row={**src,"actual_containing_fnid":";".join(inside.fnid.to_list()),
       "matches_expected_fnid":exact,
       "distance_to_district_boundary_km_planar":distance,
       "landmark_point_not_intake":True}
  records.append(row)
  check("GIS_site_within_"+src["case"],exact,
        {"inside":inside.fnid.to_list(),"expected":src["district_fnid"],
         "distance_to_boundary_km":distance})
  assert len(inside)<=1,("ambiguous_point_on_admin_boundary",src["case"])
 R=pd.DataFrame(records)
 # Join independently audited HarvestStat category series and MIRCA 2020
 y=pd.read_csv(ROOT/"results"/"rice_feasibility"/"rice_series_production_system_audit.csv")
 irr=pd.read_csv(ROOT/"results"/"mirca_os"/"district_exposure"/"district_irrigation_crop_share_2015_2020.csv")
 out=[]
 for s in R.itertuples(index=False):
  a=y.loc[y.fnid.eq(s.district_fnid)]
  v=irr.loc[irr.fnid.eq(s.district_fnid)&irr.crop.eq("Rice")&irr.reference_year.eq(2020)]
  assert len(v)==1,(s.case,len(v))
  direct=a.loc[a.irrigated_series_8y_6consecutive.eq(True)]
  longagg=a.loc[a.outcome_system_class.eq("aggregate_or_unclassified") & a.valid_years.ge(10)]
  stats=v.iloc[0]
  out.append({"case":s.case,"fnid":s.district_fnid,"country_code":s.country_code,"BCODE":s.BCODE,
   "source_point_within_expected_district":s.matches_expected_fnid,
   "local_source_G0":True,
   "landmark_in_district_G1":s.matches_expected_fnid,
   "direct_irrigated_rice_source_series_G2":len(direct)>0,
   "actual_field_to_intake_polygon_G3":False,
   "measured_upstream_transboundary_flow_G4":False,
   "implemented_treaty_for_this_intake_G5":False,
   "selected_intake_specific_hydropost_G6":False,
   "n_direct_irrigated_source_strata":len(direct),
   "direct_irrigated_yrs_max":int(direct.valid_years.max()) if len(direct) else 0,
   "n_long_aggregate_or_unknown_rice_strata":len(longagg),
   "long_aggregate_max_years":int(longagg.valid_years.max()) if len(longagg) else 0,
   "mirca2020_irrigated_rice_ha_modelled_whole_district":float(stats.irrigated_ha),
   "mirca2020_irrigated_rice_share_modelled_whole_district":float(stats.fraction_irrigated),
   "mirca2020_grid_centres_in_district":int(stats.grid_centres_inside_district),
   "scientific_prohibition":"NO_DISCHARGE_SHOCK_OR_CAUSAL_INSTITUTION_ESTIMATE_WITHOUT_G3_G4_G5",
   "research_use":"FIELD_AND_INTAKE_GIS_PRIORITY" if s.case=="OFFICE_DU_NIGER"
    else "COMPACT_RIVER_PUMPING_BOUNDARY_PRIORITY" if s.case=="MALANVILLE_RICE"
    else "SHORT_IRRIGATED_OUTCOME_BUT_FLOW_DIRECTION_SENSITIVITY"})
 gates=pd.DataFrame(out)
 check("sources_three_and_rice_outcome_distinct",len(gates)==3,{"cases":gates.case.to_list()})
 check("only_Sourou_explicit_irrigated_HS_rice",gates.loc[gates.direct_irrigated_rice_source_series_G2,"case"].to_list()==["SOUROU_NIASSAN"])
 check("none_has_intake_field_link_or_river_volume_or_treaty",not gates[[
   "actual_field_to_intake_polygon_G3","measured_upstream_transboundary_flow_G4",
   "implemented_treaty_for_this_intake_G5","selected_intake_specific_hydropost_G6"]].any().any())
 check("MIRCA_rice_not_conflated_with_observed_scheme",all(
  x!="MIRCA" for x in gates.scientific_prohibition))
 R.to_csv(RESULT/"three_scheme_georeferenced_documentary_evidence.csv",index=False)
 gates.to_csv(RESULT/"three_scheme_physical_source_gate_and_outcome_table.csv",index=False)
 gj={"type":"FeatureCollection","name":"Scheme landmarks NOT verified intake",
  "features":[{"type":"Feature","geometry":mapping(Point(s.lon,s.lat)),
   "properties":{"case":s.case,"site_type":s.representative_point,
    "note":"NOT_VERIFIED_INTAKE_DO_NOT_SELECT_GAUGE","fnid":s.district_fnid,
    "river":s.water_source,"source_url":s.source_url}} for s in R.itertuples(index=False)]}
 (RESULT/"three_scheme_LANDMARK_points_not_intake.geojson").write_text(
  json.dumps(gj,ensure_ascii=False,indent=2)+"\n")
 META["counts"]={
  "scheme_candidates":3,"site_points_verified_in_expected_admin":int(R.matches_expected_fnid.sum()),
  "documented_local_source_links":len(gates),
  "site_landmarks_not_intake_coordinates":int(R.landmark_point_not_intake.sum()),
  "source_verified_direct_irrigated_rice_strata_in_geocoded_admin":int(gates.direct_irrigated_rice_source_series_G2.sum()),
  "field_to_intake_GIS_confirmed":0,
  "transboundary_flow_volume_at_intake_confirmed":0,
  "international_allocation_implementation_confirmed":0,
  "gauge_suitability_confirmed":0,
  "source_outcome_gate":gates.to_dict("records")}
 META["status"]="COMPLETE" if not META["errors"] else "FAILED"
except Exception as e:
 META["status"]="FAILED";META["errors"].append(repr(e))
 META["traceback"]=traceback.format_exc()[-5000:]
save()
print(json.dumps({"status":META["status"],"errors":META["errors"],
                  "counts":META.get("counts"),"checks":META["checks"]},ensure_ascii=False,indent=2,default=str)[:18000])
if META["status"]!="COMPLETE":sys.exit(1)
