"""MIRCA-OS v2 crop calendars: verified 2015 ir/rf file schema and crop rows.
Official resource http://www.hydroshare.org/resource/e4582ca0042148338bb5e0148b749ed6
"""
import datetime,hashlib,json,pathlib,os,traceback
import requests,pandas as pd
R="e4582ca0042148338bb5e0148b749ed6"
BASE=pathlib.Path(__file__).resolve().parents[1];OUT=BASE/"results"/"mirca_os";OUT.mkdir(exist_ok=True,parents=True)
TMP=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"mirca_calendar";TMP.mkdir(exist_ok=True)
rep={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"sources":[],"status":"STARTED","error":None}
try:
 sess=requests.Session()
 files=sess.get(f"https://www.hydroshare.org/hsapi/resource/{R}/files/",timeout=45).json()["results"]
 for system in ("ir","rf"):
  name=f"MIRCA-OS_2015_{system}_v2.csv"
  src=next(v for v in files if v["file_name"]==name)
  u=src["url"].replace("http://","https://",1)
  fn=TMP/name
  with sess.get(u,stream=True,timeout=(30,120),allow_redirects=True) as r:
   r.raise_for_status()
   with fn.open("wb") as f:
    for chunk in r.iter_content(1024*1024):
     if chunk:f.write(chunk)
  assert fn.stat().st_size==src["size"],f"Bad size {name}"
  with fn.open("rb") as f:sha=hashlib.file_digest(f,"sha256").hexdigest()
  data=pd.read_csv(fn,low_memory=False,encoding='latin1')
  textcols=[c for c in data if data[c].dtype==object]
  masks={}
  for crop in ("Maize","Rice","Sorghum"):
   matched=data[textcols].astype(str).apply(lambda col:col.str.fullmatch(r"(?i).*"+crop+r".*")).any(axis=1)
   masks[crop]={"rows_with_crop_label":int(matched.sum()),
     "example_matching_record":data.loc[matched].head(1).fillna("").to_dict("records")}
  rep["sources"].append({"system":system,"name":name,"source_url":u,"sha256":sha,"rows":len(data),
   "catalogue_size_bytes":src["size"],"columns":list(data.columns),
   "sample_rows":data.head(2).fillna("").to_dict("records"),
   "crop_matches":masks})
 rep["status"]="COMPLETE"
except Exception as e:
 rep["status"]="FAILED";rep["error"]=str(e)[:500];rep["traceback"]=traceback.format_exc()[-2500:]
(OUT/"crop_calendar_schema_2015.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":rep["status"],"error":rep["error"],"sources":[{"name":x["name"],"rows":x["rows"],"cols":x["columns"],"crop_counts":{k:v["rows_with_crop_label"] for k,v in x["crop_matches"].items()}} for x in rep["sources"]]},ensure_ascii=False,indent=2))
if rep["status"]!="COMPLETE":raise SystemExit(1)
