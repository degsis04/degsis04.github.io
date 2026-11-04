"""OSM-only preliminary candidate lookup around Di commune, NOT verified MCC as-built pump GIS.
Strictly tag-limited and bounded; failure never mistaken for absence of seven pumps.
"""
import requests,pathlib,json,datetime,sys,traceback,math,hashlib
R=pathlib.Path(__file__).resolve().parents[1];O=R/"results"/"stage32_sourou_real_hydrology";O.mkdir(parents=True,exist_ok=True)
LAT=13.169;LON=-3.415;RADIUS=22000
# Di commune rough administrative locator. NOT the actual canal intake location.
QUERY=f'''[out:json][timeout:38];
(
 nwr(around:{RADIUS},{LAT},{LON})["man_made"~"^(pumping_station|pump)$"];
 nwr(around:{RADIUS},{LAT},{LON})["building"~"^(pump_house|pumping_station)$"];
 nwr(around:{RADIUS},{LAT},{LON})["waterway"="canal"]["name"];
);
out center tags;'''
ENDPOINTS=["https://overpass.kumi.systems/api/interpreter","https://overpass-api.de/api/interpreter"]
LOG={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED","scope":{
 "di_commune_locator_lat":LAT,"lon":LON,"source":"openadmindata.org Di commune BF610301",
 "radius_km":22,"not_actual_di_scheme_boundary":True},
 "sources":ENDPOINTS,"cautions":[
 "OSM search is crowdsourced and may miss pumps not mapped; zero results does not prove absence",
 "OSM tagging near Di does not establish identity with MCC seven 2014 as-built pumps",
 "No latlon of pumping station may be asserted to be verified by primary engineering records",
 "Official SCET design includes GIS but unpublished asbuilt spatial source"] }
try:
 for endpoint in ENDPOINTS:
  try:
   resp=requests.post(endpoint,data={"data":QUERY},timeout=(15,60),
     headers={"User-Agent":"AcademicTransboundaryWaterDiMCCCandidateSourceAudit/1.0"})
   LOG.setdefault("attempts",[]).append({"endpoint":endpoint,"status_code":resp.status_code,"size":len(resp.content)})
   if resp.status_code!=200:continue
   ob=resp.json(); elements=ob.get("elements",[])
   if not isinstance(elements,list):continue
   features=[];nonpoint=0
   for e in elements:
    typ=e.get("type","");loc=e if typ=="node" else e.get("center",{})
    lat=loc.get("lat");lon=loc.get("lon")
    if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)):
     nonpoint+=1;continue
    features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
      "properties":{"osm_type":typ,"osm_id":e.get("id"),"tags":e.get("tags",{}),
       "evidence":"UNVERIFIED_OSM_CANDIDATE_OR_NAMED_CANAL","verified_2014_Di_seven_pumps":False,
       "source":f"https://www.openstreetmap.org/{typ}/{e.get('id')}"}})
   featurecollection={"type":"FeatureCollection","properties":{
     "title":"OSM tagged candidate pumping features and named canals, NOT MCC as-built Di geometry",
     "overpass_endpoint":endpoint,"query":QUERY,
     "locality_reference_latlon":[LAT,LON],
     "verified_MCC_7_pumps":False},"features":features}
   (O/"Di_22km_OpenStreetMap_PUMP_CANDIDATES_not_verified_asbuilt.geojson").write_text(
      json.dumps(featurecollection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
   LOG["result"]={"endpoint":endpoint,"n_raw_elements":len(elements),"n_geolocatable":len(features),
     "non_geolocatable":nonpoint,"n_pumping_tags":sum("pumping_station" in str(f["properties"]["tags"]) or
       str(f["properties"]["tags"].get("man_made",""))=="pump" for f in features),
     "distinct_osm_ids":len({(e.get("type"),e.get("id")) for e in elements}),
     "actual_mcc_pumps_confirmed":0}
   LOG["status"]="OSM_CANDIDATE_DISCOVERY_ONLY"
   break
  except Exception as e:LOG.setdefault("attempts",[]).append({"endpoint":endpoint,"error":repr(e)[:300]})
 if LOG["status"]=="STARTED":LOG["status"]="OSM_NOT_ACCESSIBLE"
except Exception as e:
 LOG["status"]="FAILED";LOG["exception"]=repr(e);LOG["traceback"]=traceback.format_exc()[-2000:]
(O/"stage32_OSM_Di_Pump_and_Canal_candidate_discovery_QA.json").write_text(
json.dumps(LOG,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"status":LOG["status"],"result":LOG.get("result"),"attempts":LOG.get("attempts")},
 ensure_ascii=False)[:2200])
sys.exit(0 if LOG["status"]!="FAILED" else 1)
