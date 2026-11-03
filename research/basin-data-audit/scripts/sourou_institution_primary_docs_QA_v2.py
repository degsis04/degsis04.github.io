"""Independent source-document verification for cross-border Sourou CTGS/CTC.

The UNEP 2016 PDF is available indexed by web but some Github runners get
HTML or HTTP404. This audit MUST report 'SOURCE_PARTIAL', not invented PASS,
when original UNEP or legal PDF cannot be independently downloaded.

IIED original external-review G04090 is independently fetched as a real PDF,
SHA-256 and pdf text extracted. Original 2012 IIED legal instrument is
optional and cannot by itself prove 2013 executed signature.
"""
import pathlib,datetime as dt,hashlib,json,traceback,re,subprocess,sys,csv,unicodedata,requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"water_source_gate_v1";OUT.mkdir(exist_ok=True)
TMP=pathlib.Path("/tmp")/"sourou_institution_docs_v3";TMP.mkdir(exist_ok=True)
FILES={
 "IIED_G04090_2016_external_review":"https://www.iied.org/sites/default/files/pdfs/migrate/G04090.pdf",
 "UNEP_2016_terminal_eval_GEF_mirror":"https://www.gefieo.org/sites/default/files/documents/projects/tes/1111-terminal-evaluation.pdf",
 "UNEP_2016_terminal_eval_original":"https://wedocs.unep.org/bitstream/handle/20.500.11822/20812/1111_2016_te_unep_regional_iw_fsp_volta_river.pdf",
 "IIED_G04226_2012_agreement_publication":"https://www.iied.org/sites/default/files/pdfs/migrate/G04226.pdf"
}
R={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","errors":[],
   "checks":{},"files":{},
   "factual_limitations":[
    "UNEP published March 2016 draft-evaluation PDF has a DRAFT ONE cover despite later official posting.",
    "A 2012 online legal template or IIED publication is not by itself an authenticated copy with actual June 2013 signatures.",
    "Meeting implementation is documentary evidence of consultation, not controlled river releases or agricultural yield effects.",
    "When hosted PDFs are only available through indexed web search rather than direct bytes, original checksum cannot be independently confirmed by this CI runner.",
    "FEWSNET direct-irrigated rice series is only 2015-2023, after 2013 committee setup; no compatible before period."],
   "web_verified_sources_not_machine_verified":[
    "UNEP GEF official indexed 2016 original, paragraph 83 negative/demo and paragraph 86 committee 2013 (web search)",
    "FAOLEX catalog agreement date June 20 2013 (web search)",
    "Contemporaneous press first CTGS assembly 2013 (web search)"]}
def n(s):
 return re.sub(r"\s+"," ",unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().casefold()).strip()
def check(label,passed,details=None):
 R["checks"][label]={"pass":bool(passed),"detail":details}
 if not passed:R["errors"].append(label)
try:
 texts={}
 for name,url in FILES.items():
  info={"url":url,"status":"STARTED"}
  try:
   rr=requests.get(url,timeout=(30,100),headers={"User-Agent":"University Academic Source QA/1.0"})
   info["status_code"]=rr.status_code
   rr.raise_for_status();payload=rr.content
   info["bytes"]=len(payload);info["sha256"]=hashlib.sha256(payload).hexdigest()
   if not payload.startswith(b"%PDF"):
    info["status"]="BLOCKED_HTML_NOT_PDF"
    info["first_bytes"]=payload[:100].decode("utf-8","replace")
   else:
    f=TMP/(name+".pdf");f.write_bytes(payload)
    proc=subprocess.run(["pdftotext","-layout",str(f),"-"],capture_output=True,text=True,timeout=100)
    if proc.returncode!=0:raise RuntimeError("pdftotext: "+proc.stderr[-400:])
    text=n(proc.stdout);texts[name]=text
    info["status"]="PARSED_PDF"
    info["pdftotext_chars"]=len(text)
    info["has_sourou"]="sourou" in text
    ii=text.find("sourou")
    info["first_sourou_excerpt"]=text[max(0,ii-80):ii+260]
  except Exception as e:
   info["status"]="BLOCKED_DOWNLOAD"
   info["error"]=str(e)[:500]
  R["files"][name]=info
 ii=texts.get("IIED_G04090_2016_external_review","")
 check("IIED_independent_review_original_pdf_hashed",
       len(ii)>100000 and "sourou" in ii,
       {"text_chars":len(ii),"sha256":R["files"]["IIED_G04090_2016_external_review"].get("sha256")})
 # Extract year mentions within +/- 300 characters of Sourou/CTGS mentions.
 hits=[]
 for token in ["sourou","ctgs","decembre 2015","december 2015","2013"]:
  for m in list(re.finditer(re.escape(token),ii))[:7]:
   hits.append({"token":token,"context":ii[max(0,m.start()-110):m.end()+170]})
 R["independently_extracted_IIED_contexts"]=hits[:28]
 check("IIED_exact_2015_CTGS_followup_meeting",
       "comite transfrontalier existe et sest reuni en decembre 2015" in ii,
       {"original_review_excerpt":"Le comite transfrontalier existe et s'est reuni en decembre 2015, deux ans apres la premiere reunion.",
        "relative_first_meeting_year":2013})
 R["checks"]["IIED_has_source_year_2013"]={"pass":"2013" in ii,
   "detail":"Year present (no specific event validated from this condition alone)"}
 R["checks"]["IIED_has_source_year_2015"]={"pass":"2015" in ii,
   "detail":"Year present (no specific event validated from this condition alone)"}
 # Source provenance and no fabricated quantitative water allocation.
 with (ROOT/"institutions"/"sourou_transboundary_management_primary_evidence_v2.csv").open(newline="",encoding="utf-8") as file:
  entries=list(csv.DictReader(file))
 check("registered_events_have_legal_vs_operational_vs_water_caveat",len(entries)>=10 and
       any(x["mechanism"]=="bilateral_allocation_rule" and x["evidence_grade"]=="NOT_ESTABLISHED" for x in entries),
       {"n_events":len(entries)})
 hasunep=any(k.startswith("UNEP_") and len(v)>50000 for k,v in texts.items())
 if hasunep:
  uu=next(v for k,v in texts.items() if k.startswith("UNEP_") and len(v)>50000)
  R["checks"]["UNEP_contains_2013_bilateral_committees"]={
   "pass":all(w in uu for w in ["sourou","two bilateral meetings in 2013","agreements were implemented"]),
   "detail":"Text validated against a downloaded UNEP 2016 PDF"}
  R["checks"]["UNEP_contains_negative_demo_caveat"]={
   "pass":"none of the demonstration projects implemented were actually" in uu,
   "detail":"Negative evidence explicitly distinguished"}
  R["evidence_scope"]="UNEP_AND_IIED_DOCUMENTS_CHECKED"
 else:
  R["evidence_scope"]="ONLY_IIED_DOCUMENT_BYTES_CONFIRMED_UNEP_INDEXED_WEB_NOT_MACHINE_CHECKED"
 R["status"]="PASS" if not R["errors"] and hasunep and all(
    v["pass"] for k,v in R["checks"].items() if k.startswith("UNEP_contains_")) else (
    "PARTIAL_SOURCE_QA" if not R["errors"] else "FAILED")
except Exception as e:
 R["status"]="FAILED";R["errors"].append(repr(e));R["traceback"]=traceback.format_exc()[-3200:]
(OUT/"sourou_UNEP_IIED_signed_vs_draft_institution_evidence_QA.json").write_text(
 json.dumps(R,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":R["status"],"errors":R["errors"],"checks":R["checks"],"files":R["files"],
  "evidence_scope":R.get("evidence_scope"),"context":R.get("independently_extracted_IIED_contexts",[])[:8]},indent=2,ensure_ascii=False,default=str)[:15000])
if R["status"]=="FAILED":sys.exit(1)
