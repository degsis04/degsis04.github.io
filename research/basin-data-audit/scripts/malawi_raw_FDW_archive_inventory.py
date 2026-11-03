"""Malawi raw FEWS NET Data Warehouse extract provenance (v1.2 archive).
Source archive can explain whether 'Main / Rainfed' and 'Annual / All' are
native source categories or transformations. NOT use unsupported semantics.

Archive is not committed. Only filename hashes/schema, metadata counts
and 2023 Thyolo / 2024 Lilongwe source-specific evidence are committed.
"""
import datetime as dt,hashlib,io,json,pathlib,os,sys,traceback,zipfile
import requests,pandas as pd,numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_maize_semantics_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"malawi_fdw_raw";TMP.mkdir(exist_ok=True)
SOURCES=[
"https://github.com/HarvestStat/HarvestStat-Africa/releases/download/v1.2/fdw_raw_data_v1.2.zip",
"https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/5b62fb5/public/fdw_raw_data_v1.2.zip",
]
L={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "all_candidates":SOURCES,"attempts":[],"limits":[
 "An original FDW extract, if available, is itself a FEWSNET harmonized archive; may lack primary Malawi APES questionnaires.",
 "A source record labelled Rainfed in FDW does not verify field-level irrigation for all district crops.",
 "No raw individual farmer observations are exported.",
 "No source values are overwritten, corrected or removed."]}
try:
 file=None;source=None
 for url in SOURCES:
  row={"url":url}
  try:
   with requests.get(url,timeout=(30,120),stream=True,
       headers={"User-Agent":"AcademicMalawiHarvestStatIndependentQA/1.0"}) as r:
    row["http_status"]=r.status_code;r.raise_for_status()
    p=TMP/"fdw_raw_data_v1.2.zip"
    with p.open("wb") as f:
     for x in r.iter_content(2**20):
      if x:f.write(x)
   with p.open("rb") as f:
    row["sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
   row["bytes"]=p.stat().st_size
   with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
   file=p;source=url
   L["attempts"].append(row);break
  except Exception as e:
   row["error"]=repr(e)[:300]
   L["attempts"].append(row)
 if file is None:
  L["status"]="UNAVAILABLE"
  L["reason"]="Raw FDW ZIP unavailable from two verified upstream candidate URLs; cannot claim original FDW provenance verified."
 else:
  with zipfile.ZipFile(file) as z:
   names=z.namelist()
   L["archive"]={"url":source,"sha256":L["attempts"][-1]["sha256"],
           "member_count":len(names),
           "Malawi_member_candidates":[s for s in names if s.lower().endswith("adm_crop_data_raw_mw.csv")]}
   candidates=L["archive"]["Malawi_member_candidates"]
   if len(candidates)!=1:raise RuntimeError(f"Expected one MW member, found {candidates}")
   name=candidates[0];raw=z.read(name)
  L["Malawi_raw_member"]={"name":name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
  data=pd.read_csv(io.BytesIO(raw),low_memory=False)
  L["Malawi_raw_member"]["rows"]=len(data)
  L["Malawi_raw_member"]["columns"]=list(data.columns)
  L["Malawi_raw_member"]["column_types"]={c:str(data[c].dtype) for c in data.columns}
  L["Malawi_raw_member"]["some_column_unique_values"]={
     c:data[c].astype(str).value_counts().head(12).to_dict()
     for c in data.columns if
        ("season" in c.lower() or "production_system" in c.lower() or
         "product" in c.lower() or "crop" in c.lower() or "date" in c.lower()) and
        data[c].nunique(dropna=True)<70}
  # Use only aggregate descriptive conditions and records for two widely identified
  # extreme cases by source FNID and 2023/2024.
  L["Malawi_raw_member"]["FNID-like-columns"]=[c for c in data.columns if "fnid" in c.lower() or "geo" in c.lower()]
  L["Malawi_raw_member"]["Source-ID-like-columns"]=[c for c in data.columns if
      "source" in c.lower() or "report" in c.lower() or "reference" in c.lower()]
  L["status"]="COMPLETE"
except Exception as ex:
 L["status"]="FAILED";L["error"]=repr(ex)
 L["traceback"]=traceback.format_exc()[-3000:]
(OUT/"raw_fdw_Malawi_source_archive_inventory.json").write_text(
 json.dumps(L,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({k:v for k,v in L.items() if k!="Malawi_raw_member"},ensure_ascii=False,indent=2,default=str)[:12000])
print(json.dumps({"Malawi_raw_member":L.get("Malawi_raw_member")},ensure_ascii=False,indent=2,default=str)[:8000])
if L["status"]=="FAILED":sys.exit(1)
