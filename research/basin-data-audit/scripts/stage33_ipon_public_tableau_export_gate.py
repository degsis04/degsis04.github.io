"""Stage33 exact public-IPON Tableau export and source-access gate.
Never equate a live dashboard, a screenshot, or a successful HTTP 200 HTML page
with public tabular in-situ irrigation water delivery observations.

The script attempts documented public workbook URLs only; no login/session
stealing and no restricted data bypass. If a public TWBX exists, inspect
metadata and downloadable CSVs, retain checksums but do not republish raw
datasets when their redistribution license is unknown.
"""
import requests,json,os,pathlib,datetime,hashlib,zipfile,io,xml.etree.ElementTree as ET,re,csv,traceback,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"stage33_ipon_public_access";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"stage33_IPON_public_only";TMP.mkdir(parents=True,exist_ok=True)
BASE="https://public.tableau.com"
VIEW="/views/IWMI_IPADT_Dashboard_20240320/Overview"
REQUESTS=[
 ("profile",BASE+"/app/profile/water.eleaf/viz/IWMI_IPADT_Dashboard_20240320/Overview"),
 ("view_html",BASE+VIEW+"?:showVizHome=no"),
 ("dashboard_csv",BASE+VIEW+".csv?:showVizHome=no"),
 ("dashboard_xlsx",BASE+VIEW+".xlsx?:showVizHome=no"),
 ("twbx",BASE+VIEW+".twbx?:showVizHome=no"),
]
P={"run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED",
   "public_workbook_url":BASE+VIEW,"endpoints":[],
   "limitations":[
    "HTTP 200 from a Tableau page is NOT access to underlying zone, casier, or in-situ volumes",
    "A dashboard-level export may not expose data sheets; one sheet cannot represent all 11 indicators",
    "Tableau may have access restrictions even though FAO links public beta",
    "Unique labels and polygons must have original source mapping/metadata before WaPOR spatial overlap",
    "In-situ water diversion is distinct from WaPOR evapotranspiration and published screenshot values",
    "Do not infer measured irrigation water volumes from percentage or chart graphics"]}
def sha(b):return hashlib.sha256(b).hexdigest()
def decode_metadata(s):
 a={"body_first100":s[:100].decode("utf8","replace")}
 try:
  h=s[:2500000].decode("utf8","replace")
  tokens=("worksheet","dashboard","Zone","Casier","casiers","volumes","irrigation","water supplied",
           "tableauSoftware","vizql")
  a["signal_counts"]={t:len(re.findall(re.escape(t),h,re.I)) for t in tokens}
  a["viz_id_examples"]=list(dict.fromkeys(re.findall(r"(?:worksheet|sheet|zone|casier)[^<>'\"\n]{0,90}",h,re.I)))[:30]
 except:pass
 return a
def inspect_workbook(b):
 o={"zip_bytes":len(b),"sha256":sha(b)}
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  bad=z.testzip()
  o["zip_crc_ok"]=bad is None
  arr=z.infolist()
  o["member_count"]=len(arr)
  o["members"]=[{"name":v.filename,"bytes_uncompressed":v.file_size,"bytes_compressed":v.compress_size} for v in arr[:120]]
  wb=[v for v in arr if v.filename.lower().endswith(".twb")]
  o["twb_count"]=len(wb)
  if len(wb)==1:
   xml=z.read(wb[0])
   o["twb_xml_sha256"]=sha(xml)
   root=ET.fromstring(xml)
   o["datasources"]=[]
   for ds in root.findall(".//datasource"):
    q={"name":ds.attrib.get("name"),"caption":ds.attrib.get("caption"),
       "connection_types":sorted(set(c.attrib.get("class","") for c in ds.findall(".//connection"))),
       "columns":[{"name":c.attrib.get("name"),"caption":c.attrib.get("caption"),
         "datatype":c.attrib.get("datatype"),"role":c.attrib.get("role")} for c in ds.findall("column")][:100]}
    o["datasources"].append(q)
   o["dashboard_names"]=list(dict.fromkeys(z.attrib.get("name","") for z in root.findall(".//dashboard")))
   o["worksheet_names"]=list(dict.fromkeys(z.attrib.get("name","") for z in root.findall(".//worksheet")))
  # Warn on Hyper extracts: pack may include measures but their existence doesn't authorize generic export.
  o["data_member_inventory"]=[x for x in o["members"] if x["name"].lower().endswith((".hyper",".tde",".csv",".xlsx",".geojson",".shp",".gpkg"))]
  o["in_situ_volumes_read_from_public_export"]=False
 return o
try:
 sess=requests.Session()
 sess.headers.update({"User-Agent":"Mozilla/5.0 (compatible; AcademicPublicOpenDataAudit/1.0)"})
 for name,url in REQUESTS:
  it={"name":name,"url":url}
  try:
   with sess.get(url,timeout=(15,45),stream=True,allow_redirects=True) as resp:
    it.update({"status_code":resp.status_code,"url_final":resp.url,"content_type":resp.headers.get("Content-Type",""),
      "content_disposition":resp.headers.get("Content-Disposition",""),
      "length_header":resp.headers.get("Content-Length")})
    pieces=[];n=0;cap=110*1024*1024 if name=="twbx" else 2*1024*1024
    for chunk in resp.iter_content(128*1024):
     if chunk:
      n+=len(chunk)
      if n>cap:
       it["capped_at_bytes"]=cap;break
      pieces.append(chunk)
    body=b"".join(pieces)
    it["bytes_received"]=len(body)
    it["sha256_partial_if_capped"]=sha(body)
    it.update(decode_metadata(body))
    if name=="twbx" and resp.status_code==200 and body.startswith(b"PK") and "capped_at_bytes" not in it:
     it["verified_public_twbx"]=True
     it["workbook_inspection"]=inspect_workbook(body)
    if name in ("dashboard_csv","dashboard_xlsx") and resp.status_code==200:
     if name=="dashboard_csv" and "capped_at_bytes" not in it and "text/html" not in it["content_type"].lower():
      try:
       text=body.decode("utf-8-sig")
       lines=list(csv.reader(io.StringIO(text)))
       if 1<len(lines)<100000 and len(lines[0])>=2:
        it["verified_csv_header"]=lines[0][:60]
        it["verified_csv_rows"]=len(lines)-1
        it["original_csv_sha256"]=sha(body)
      except Exception as e:it["csv_parser_error"]=str(e)
     elif name=="dashboard_xlsx" and body.startswith(b"PK"):
      it["xlsx_download_possible"]=True
    if name in ("profile","view_html") and resp.status_code==200 and "text/html" in it["content_type"].lower():
     it["html_document_verified"]=True
  except Exception as e:it["error"]=repr(e)
  P["endpoints"].append(it)
 public=[z for z in P["endpoints"] if z.get("verified_public_twbx") or z.get("verified_csv_header")]
 P["public_machine_readable_tables_found"]=len(public)
 P["verified_in_situ_water_flow_records_count"]=0
 P["actual_individual_casier_polygon_count"]=0
 P["status"]="PUBLIC_EXPORT_AVAILABLE_INSPECT_SCHEMA" if public else "PUBLIC_SOURCE_LINK_BUT_NO_VERIFIED_EXPORT"
except Exception as ex:
 P["status"]="FAILED";P["error"]=repr(ex);P["traceback"]=traceback.format_exc()[-3500:]
(OUT/"IPON_Tableau_exact_public_export_QA.json").write_text(json.dumps(P,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":P["status"],"endpoints":[{k:v for k,v in x.items() if k in ("name","status_code","content_type","bytes_received","error","verified_public_twbx","verified_csv_rows","xlsx_download_possible")} for x in P["endpoints"]]},ensure_ascii=False)[:5000])
sys.exit(0 if P["status"]!="FAILED" else 1)
