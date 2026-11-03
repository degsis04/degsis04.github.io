"""Trace published v1.2 raw FDW Malawi extract through the Dryad REST API.

The GitHub release/static raw paths are 404; do not infer nonexistence.
The canonical Dryad v1.2 deposit lists fdw_raw_data_v1.2.zip.
Document file ID/version before fetching, audit zip and Malawi member.
No corrected values or new causal claims.
"""
import datetime as dt,io,json,hashlib,pathlib,sys,traceback,zipfile
import requests,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_maize_semantics_v1";OUT.mkdir(parents=True,exist_ok=True)
API="https://datadryad.org/api/v2"
DOI="doi%3A10.5061%2Fdryad.vq83bk42w"
L={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "status":"STARTED","api_endpoint":API,"doi":"10.5061/dryad.vq83bk42w",
   "errors":[],"publication":"v1.2 source archive published July 2026",
   "warnings":["Raw warehouse data may not reveal original ministry APES survey definitions.",
   "Raw rows are not automatically comparable to harmonized rows because source fields and classifications can differ."]}
try:
 s=requests.Session();s.headers["User-Agent"]="University-HarvestStat-Source-Audit/1.0"
 meta=s.get(f"{API}/datasets/{DOI}",timeout=45);meta.raise_for_status()
 dat=meta.json();L["dataset_metadata"]={
   "doi":dat.get("identifier"),"latestVersion":dat.get("lastSubmittedVersion"),
   "versionNumber":dat.get("versionNumber"),"versionStatus":dat.get("versionStatus"),
   "id":dat.get("id"),"versionId":dat.get("versionId")}
 versions=s.get(f"{API}/datasets/{DOI}/versions",timeout=45);versions.raise_for_status()
 vv=versions.json()
 vlist=vv.get("_embedded",{}).get("stash:versions",[])
 if not vlist:vlist=vv.get("_embedded",{}).get("versions",[])
 if not vlist:vlist=vv.get("versions",[])
 L["versions_metadata"]=[{"id":v.get("id"),"version_link":v.get("_links",{}).get("self",{}).get("href"),
    "created":v.get("created"),"versionNumber":v.get("versionNumber"),
    "versionStatus":v.get("versionStatus"),"publicationDate":v.get("publicationDate")} for v in vlist]
 L["dataset_metadata"]["links"]=dat.get("_links",{})
 candidates=[]
 for v in vlist:
  if v.get("id"):candidates.append(v["id"])
  link=v.get("_links",{}).get("self",{}).get("href","")
  if "/versions/" in link:
   tail=link.rstrip("/").rsplit("/",1)[-1]
   if tail.isdigit():candidates.append(int(tail))
 if dat.get("lastSubmittedVersion"):candidates.append(dat["lastSubmittedVersion"])
 if dat.get("versionId"):candidates.append(dat["versionId"])
 if not candidates:raise ValueError("Unable to discover Dryad version ID from official API")
 found=None
 for vid in list(dict.fromkeys(candidates[::-1])):
  rr=s.get(f"{API}/versions/{vid}/files",timeout=45)
  if rr.status_code!=200:continue
  js=rr.json()
  items=js.get("_embedded",{}).get("stash:files",[])
  if not items:items=js.get("_embedded",{}).get("files",[])
  if not items:items=js.get("files",[])
  L.setdefault("scanned_versions",[]).append({"id":vid,"filenames":[x.get("path") for x in items]})
  for item in items:
   if str(item.get("path","")).endswith("fdw_raw_data_v1.2.zip"):
    found=(vid,item)
    break
  if found:break
 if not found:raise ValueError("v1.2 raw source zip not found in scanned Dryad versions")
 vid,item=found
 fileid=item.get("id")
 L["raw_file"]={"version_id":vid,"file_id":fileid,"path":item.get("path"),
   "size":item.get("size"),"digestType":item.get("digestType"),"digest":item.get("digest")}
 if not fileid:raise ValueError("No official Dryad raw file ID")
 # Follow documented per-file endpoint, never guess/download a proprietary URL.
 url=f"{API}/files/{fileid}/download"
 resp=s.get(url,timeout=(30,180),stream=True);resp.raise_for_status()
 tempfile=pathlib.Path("/tmp")/"fdw_raw_dryad_v1.2_verified.zip"
 with tempfile.open("wb") as f:
  for b in resp.iter_content(2**20):
   if b:f.write(b)
 with tempfile.open("rb") as f:L["raw_file"]["sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
 L["raw_file"]["downloaded_size"]=tempfile.stat().st_size
 with zipfile.ZipFile(tempfile) as z:
  assert z.testzip() is None
  names=z.namelist()
  L["raw_file"]["member_count"]=len(names)
  matches=[n for n in names if n.lower().endswith("adm_crop_data_raw_mw.csv")]
  if len(matches)!=1:raise ValueError(f"MW raw archive member ambiguous: {matches}")
  member=matches[0]
  payload=z.read(member)
 L["malawi_raw"]={"member":member,"sha256":hashlib.sha256(payload).hexdigest(),
   "member_bytes":len(payload)}
 d=pd.read_csv(io.BytesIO(payload),low_memory=False)
 L["malawi_raw"].update({"records":len(d),"columns":list(d.columns),
    "first_row_column_types":{x:str(d[x].dtype) for x in d.columns}})
 for col in d:
  if "system" in col.lower() or "season" in col.lower():
   if d[col].nunique(dropna=True)<50:
    L["malawi_raw"].setdefault("source_category_values",{})[col]=d[col].astype(str).value_counts().head(30).to_dict()
 L["status"]="COMPLETE"
except Exception as ex:
 L["status"]="UNAVAILABLE"
 L["errors"].append(repr(ex))
 L["traceback"]=traceback.format_exc()[-2400:]
(OUT/"raw_fdw_Malawi_DRYAD_canonical_archive_inventory.json").write_text(
 json.dumps(L,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({k:v for k,v in L.items() if k not in ("traceback",)},ensure_ascii=False,indent=2,default=str)[:15000])
# Source may be unavailable due to firewall/auth: preserve status and proceed.
