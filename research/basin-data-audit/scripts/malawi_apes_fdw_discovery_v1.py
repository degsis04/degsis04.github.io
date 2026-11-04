"""Primary-source discovery only: HarvestStat pinned FDW raw and independent APES dashboard.
Uses exact external GitHub commits / Dryad digest. No regression, no claim of APES row-match.
A failed download or malformed source must set FAILED, not quietly substitute data.
"""
import pathlib, os, io, hashlib, zipfile, json, re, collections, datetime, traceback, sys
import requests, pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_apes_fdw_source_audit_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"malawi_apes_fdw_discovery";TMP.mkdir(parents=True,exist_ok=True)
RELEASE="https://github.com/HarvestStat/HarvestStat-Africa/releases/download/v1.2/doi_10_5061_dryad_vq83bk42w__v20260717.zip"
FDW_SIZE=54698516; FDW_SHA="6e8128f8854f38172aea24583e537395242abafab4382441b3d53805c44b452b"
APES_COMMIT="fbd5629f1200c3c18b615ad87c83297c2ed0bd75"
APES="https://raw.githubusercontent.com/MaxwellMkondiwa/Malawi_APES_Data_App/"+APES_COMMIT+"/docs/index.html"
LOG={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "status":"STARTED","source_urls":{"raw_fdw_bundle":RELEASE,"apes_secondary_dashboard_html":APES},
     "constraints":["FDW raw extracts are intermediate, not Ministry of Agriculture APES originals",
     "Mkondiwa APES visualization is an independently published presentation, not independently surveyed field data",
     "data year/season/units and original API schema must be inspected before matching",
     "do not infer season codes or correct years without original documents"],
     "checks":{},"errors":[]}
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def check(n,cond,detail=None):
    LOG["checks"][n]={"pass":bool(cond),"detail":detail}
    if not cond:LOG["errors"].append(n)
def download(url,path):
    if not path.exists():
        with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"UniversityMalawiHistoricalCropAudit/1.0"}) as r:
            LOG.setdefault("http_attempts",[]).append({"url":url,"status":r.status_code,"target":r.url})
            r.raise_for_status()
            with path.open("wb") as w:
                for q in r.iter_content(1024*1024):
                    if q:w.write(q)
    return path
def small_counts(d,cols):
    return {c:d[c].astype(str).value_counts(dropna=False).head(15).to_dict() for c in cols if c in d}
try:
    z=download(RELEASE,TMP/"harveststat_v1.2_public_release_bundle.zip")
    LOG["release_outer"]={"size":z.stat().st_size,"sha256":sha_bytes(z.read_bytes())}
    with zipfile.ZipFile(z) as outzip:
        check("outer_zip_crc_valid",outzip.testzip() is None)
        candidates=[i for i in outzip.infolist() if i.filename.endswith("fdw_raw_data_v1.2.zip")]
        check("exactly_one_canonical_FDW",len(candidates)==1,[i.filename for i in candidates])
        if len(candidates)!=1:raise RuntimeError("Missing pinned raw FDW member")
        payload=outzip.read(candidates[0])
        LOG["fdw_zip"]={"inner_member":candidates[0].filename,"size":len(payload),"sha256":sha_bytes(payload)}
        check("fdw_digest_canonical_Dryad",len(payload)==FDW_SIZE and sha_bytes(payload)==FDW_SHA,LOG["fdw_zip"])
    with zipfile.ZipFile(io.BytesIO(payload)) as fdwzip:
        check("raw_zip_crc_valid",fdwzip.testzip() is None)
        names=[i.filename for i in fdwzip.infolist()]
        LOG["fdw_manifest"]={"members":len(names),"mw_candidates":[n for n in names if n.lower().endswith("adm_crop_data_raw_mw.csv")]}
        matches=LOG["fdw_manifest"]["mw_candidates"]
        check("one_MW_original_FDW_member",len(matches)==1,matches)
        if len(matches)!=1:raise RuntimeError("Missing MW raw member")
        raw_bytes=fdwzip.read(matches[0])
        LOG["malawi_raw"]={"zip_member":matches[0],"bytes":len(raw_bytes),"sha256":sha_bytes(raw_bytes)}
        d=pd.read_csv(io.BytesIO(raw_bytes),low_memory=False)
        LOG["malawi_raw"].update({"rows":len(d),"columns":list(d.columns),
          "row_keys_sample_types":{c:str(d[c].dtype) for c in d.columns},
          "mild_metadata_counts":small_counts(d,[c for c in d if any(s in c.lower() for s in ["crop","product","season","source","survey","system"]) and d[c].nunique()<60])})
        LOG["malawi_raw"]["first_3_rows"]=d.head(3).replace({pd.NA:None}).where(pd.notna(d.head(3)),None).to_dict("records")
    a=download(APES,TMP/"mkondiwa_apes_2023_static_dashboard.html")
    # Published data embedded in pre-rendered HTML and plot crosstalk.
    bs=a.read_bytes()
    LOG["apes_html"]={"size":len(bs),"sha256":sha_bytes(bs),"source_commit":APES_COMMIT,
      "bytes_District":bs.count(b"DISTRICT"),"bytes_Maize":bs.count(b"Maize"),
      "json_script_count":len(re.findall(rb'<script[^>]*type=["\']application/json',bs,re.I))}
    needle_list=[b'"DISTRICT"',b'"HAs"',b'"MTs"',b'crosstalk',b'htmlwidget',b'data-for=',b'"year"']
    snippets={}
    for needle in needle_list:
        positions=[m.start() for m in list(re.finditer(re.escape(needle),bs))[:6]]
        snippets[needle.decode()]=[bs[max(0,pos-150):pos+300].decode("utf-8","replace") for pos in positions]
    LOG["apes_html"]["sample_context"]=snippets
    # Extract metadata about JSON scripts only; limit output to 20 for safety.
    tags=re.findall(rb'<script\b[^>]*>',bs,re.I)
    LOG["apes_html"]["script_tag_count"]=len(tags)
    LOG["apes_html"]["script_tag_head"]=[s[:240].decode("utf8","replace") for s in tags[:20]]
    LOG["apes_html"]["largest_script_tags"]=[s[:240].decode("utf8","replace") for s in tags[-20:]]
    check("APES_HTML_dataset_is_not_empty",len(bs)>300000 and bs.count(b"DISTRICT")>1,LOG["apes_html"]["size"])
    LOG["status"]="DISCOVERY_PASS" if not LOG["errors"] else "FAILED"
except Exception as e:
    LOG["status"]="FAILED";LOG["errors"].append(str(e));LOG["traceback"]=traceback.format_exc()[-3200:]
(OUT/"discovery_original_FDW_and_APES_html_QA.json").write_text(
    json.dumps(LOG,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"fdw":LOG.get("malawi_raw",{}).get("columns"),
 "APES_script_count":LOG.get("apes_html",{}).get("script_tag_count")},ensure_ascii=False)[:9000])
sys.exit(0 if LOG["status"]=="DISCOVERY_PASS" else 1)
