"""Reproducible MIRCA-OS v2 annual-map RAR index (no guessed layer filenames).

Official HydroShare e4582ca0042148338bb5e0148b749ed6 (March 2026).
Download only 284MB 'Annual Harvested Area Grids.rar', never 10.6GB.
Save list of actual raster members, bytes, hashes, and format.
"""
import datetime,hashlib,json,pathlib,os,subprocess,sys,traceback
import requests
R="e4582ca0042148338bb5e0148b749ed6"
BASE=pathlib.Path(__file__).resolve().parents[1]
OUT=BASE/"results"/"mirca_os";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"mirca_v2";TMP.mkdir(parents=True,exist_ok=True)
LOG={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"stage":"official annual RAR index","status":"STARTED","errors":[]}
def save(): (OUT/"annual_archive_index.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False)+"\n")
try:
 url=f"https://www.hydroshare.org/hsapi/resource/{R}/files/"
 sess=requests.Session()
 r=sess.get(url,timeout=35);r.raise_for_status()
 results=r.json()["results"];match=[x for x in results if x.get("file_name")=="Annual Harvested Area Grids.rar"]
 assert len(match)==1,match
 entry=match[0];url=entry["url"].replace("http://","https://",1)
 LOG["official_catalog_metadata"]={"url":url,"file_name":entry["file_name"],"size":entry["size"],"checksum":entry.get("checksum")}
 f=TMP/"Annual Harvested Area Grids.rar"
 if not f.exists() or f.stat().st_size!=entry["size"]:
  with sess.get(url,stream=True,timeout=(30,300),allow_redirects=True) as rr:
   rr.raise_for_status()
   LOG["final_download_url"]=rr.url
   LOG["content_type"]=rr.headers.get("Content-Type")
   with f.open("wb") as w:
    for chunk in rr.iter_content(1024*1024):
     if chunk:w.write(chunk)
 LOG["download_bytes"]=f.stat().st_size
 with f.open("rb") as h:
  LOG["sha256"]=hashlib.file_digest(h,"sha256").hexdigest()
 with f.open("rb") as h:
  LOG["md5"]=hashlib.file_digest(h,"md5").hexdigest()
 with f.open("rb") as h: LOG["magic_first_12"]=h.read(12).hex()
 LOG["size_matches_catalog"]=f.stat().st_size==entry["size"]
 assert LOG["size_matches_catalog"],"Downloaded file length differs from official catalog"
 expected=entry["checksum"].lower()
 if len(expected)==32 and all(c in "0123456789abcdef" for c in expected):
  LOG["md5_matches_catalog"]=LOG["md5"]==expected
  assert LOG["md5_matches_catalog"],"Archive differs from official HydroShare MD5"
 command=["7z","l","-slt",str(f)]
 q=subprocess.run(command,capture_output=True,text=True,timeout=240)
 LOG["archive_listing_exit_code"]=q.returncode
 if q.returncode!=0:
  LOG["7z_stderr"]=q.stderr[:10000]
  raise RuntimeError("Unable to list RAR via 7z")
 members=[]
 for raw in q.stdout.split("\n\n"):
  d={}
  for line in raw.splitlines():
   if " = " in line:
    k,v=line.split(" = ",1);d[k]=v
  if d.get("Path") and d.get("Folder")=="-" and d["Path"]!=str(f):
   members.append({"path":d["Path"],"size":int(d["Size"]) if d.get("Size","").isdigit() else None,"packed_size":int(d["Packed Size"]) if d.get("Packed Size","").isdigit() else None})
 LOG["raster_members"]=members
 LOG["member_count"]=len(members)
 LOG["relevant_candidates"]=[x for x in members if any(w in x["path"].lower() for w in ("maize","rice","sorghum"))]
 LOG["status"]="COMPLETE"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(repr(e));LOG["traceback"]=traceback.format_exc()
finally:save()
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"bytes":LOG.get("download_bytes"),"sha256":LOG.get("sha256"),"md5_match":LOG.get("md5_matches_catalog"),"members":LOG.get("member_count"),"relevant_candidates":LOG.get("relevant_candidates",[])[:45]},ensure_ascii=False,indent=2)[:16000])
if LOG["status"]!="COMPLETE":sys.exit(1)
