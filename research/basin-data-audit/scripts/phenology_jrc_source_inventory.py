"""Independent crop-calendar source inventory: EC JRC ASAP / World Bank open CSVs.

The EC-JRC crop calendar integrates FAO sources with remote-sensing phenology.
It is EXTERNAL to HarvestStat outcomes. Coverage: sorghum, maize, millet,
barley, wheat (not rice). Sources have national/subnational GAUL units;
NEVER merge GAUL1 IDs with HarvestStat FNID without geometric crosswalk.

Outputs:
  source_audit.json (HTTP, SHA256, read status, columns, country matching)
  gaul1_full_source.csv (if small and licensed, only if safe?)
  source_*_sample.csv
  asap_crop_calendar_target_countries.csv (only genuinely matched rows)
"""
import datetime as dt, hashlib, io, json, os, pathlib, zipfile, traceback, sys
import requests, pandas as pd

R=pathlib.Path(__file__).resolve().parents[1]
OUT=R/"results"/"phenology_v1";OUT.mkdir(exist_ok=True,parents=True)
TMP=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"phenology_source";TMP.mkdir(exist_ok=True)
COUNTRIES={"BFA":["Burkina Faso","Burkina","BF"],"MLI":["Mali","ML"],
 "BEN":["Benin","Bénin","BJ"],"GHA":["Ghana","GH"],"TGO":["Togo","TG"],
 "ZWE":["Zimbabwe","ZW"],"ZMB":["Zambia","ZM"],"MWI":["Malawi","MW"]}
SOURCES={
 "jrc_gaul1_worldbank":"https://datacatalogfiles.worldbank.org/ddh-published/0066842/DR0095319/crop_calendar_gaul1.csv",
 "jrc_gaul0_worldbank":"https://datacatalogfiles.worldbank.org/ddh-published/0066842/DR0095318/crop_calendar_gaul0.csv",
 "jrc_gaul1_original":"https://agricultural-production-hotspots.ec.europa.eu/files/crop_calendar_gaul1.zip",
 "jrc_gaul1_shapes":"https://agricultural-production-hotspots.ec.europa.eu/files/gaul1_asap_v05.zip"
}
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "attribution":"European Commission Joint Research Centre ASAP; Dimou (2018), data.europa.eu/89h/jrc-10112-10003; World Bank catalog 0066842 (CC BY 4.0)",
 "target_countries":list(COUNTRIES),"sources":{},"errors":[],
 "caveats":["JRC-ASAP dates are reference phenological windows, not observed annual planting or harvesting.",
  "JRC calendars include maize and sorghum; published catalog does not claim rice.",
  "GAUL1 boundaries may not match HarvestStat FNID administrative boundaries.",
  "HarvestStat metadata may be statistical labels, not plant phenology.",
  "When source includes 10-day dekads use their definitions; do not convert to precise days." ]}
try:
 for k,url in SOURCES.items():
  file=TMP/(k+(".zip" if url.endswith(".zip") else ".csv"))
  with requests.get(url,stream=True,timeout=(30,120),
   headers={"User-Agent":"University-Reproducible-HydroAgronomy/1.0"}) as response:
   response.raise_for_status()
   with file.open("wb") as f:
    for chunk in response.iter_content(2**20):
     if chunk:f.write(chunk)
  with file.open("rb") as stream:sha=hashlib.file_digest(stream,"sha256").hexdigest()
  record={"url":url,"size_bytes":file.stat().st_size,"sha256":sha,"http_status":response.status_code,
       "content_type":response.headers.get("Content-Type")}
  if file.suffix==".csv":
   # avoid encoding artifacts, keep source region and crop text verbatim
   for enc in ("utf-8-sig","cp1252","latin1"):
    try:
     a=pd.read_csv(file,encoding=enc,sep=None,engine="python",low_memory=False)
     break
    except (UnicodeDecodeError,ValueError,TypeError):
     try:a=pd.read_csv(file,encoding=enc,sep=None,engine="python");break
     except (UnicodeDecodeError,ValueError):pass
   record.update({"encoding":enc,"columns":list(a.columns),"row_count":len(a),
    "first_3_rows":a.head(3).fillna("").to_dict("records"),
    "unique_crop_col_possible":{c:sorted(a[c].dropna().astype(str).unique())[:60]
                       for c in a.columns if "crop" in c.lower() or "product" in c.lower()},
    "unique_country_col_possible":{c:sorted(a[c].dropna().astype(str).unique())[:90]
                  for c in a.columns if any(t in c.lower() for t in ["country","adm0","name0","iso"])}
     })
   # Generic string matching to isolate verified target countries without guessing schema.
   textcols=[c for c in a.columns if a[c].dtype=="object"]
   pattern="|".join(r"\b"+x+r"\b" for names in COUNTRIES.values() for x in names if len(x)>2)
   mask=a[textcols].astype(str).apply(lambda s:s.str.contains(pattern,case=False,regex=True,na=False)).any(axis=1) if textcols else pd.Series(False,index=a.index)
   aa=a.loc[mask].copy()
   record["rows_text_matching_target_country"]=len(aa)
   if len(aa):
    aa.to_csv(OUT/(k+"_target_country_text_matches.csv"),index=False)
   a.head(20).to_csv(OUT/(k+"_source_head.csv"),index=False)
  else:
   with zipfile.ZipFile(file) as z:
    assert z.testzip() is None
    names=z.namelist()
    record["archive_files"]=names[:60]
    # record CSV member schema when present, without distributing full zip.
    for member in names:
     if member.lower().endswith(".csv"):
      data=z.read(member)
      for enc in ("utf-8-sig","cp1252","latin1"):
       try:
        a=pd.read_csv(io.BytesIO(data),encoding=enc,sep=None,engine="python")
        break
       except Exception:pass
      record["archived_csv"]={"name":member,"columns":list(a.columns),"rows":len(a),
         "head":a.head(5).fillna("").to_dict("records")}
  LOG["sources"][k]=record
 LOG["status"]="COMPLETE"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(str(e)[:500]);LOG["traceback"]=traceback.format_exc()[-2500:]
(OUT/"jrc_asap_source_inventory.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False,default=str)+"\n")
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"records":{
 k:{m:v.get(m) for m in ("row_count","columns","rows_text_matching_target_country","archive_files","archived_csv")}
 for k,v in LOG["sources"].items()}},ensure_ascii=False,indent=2,default=str)[:14500])
if LOG["status"]!="COMPLETE":sys.exit(1)
