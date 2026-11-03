"""Independently source-check operationalization of Sourou committee agreements.

Original UNEP March 2016 terminal evaluation and independent IIED 2016
review downloaded and hashed. Inspect positive AND NEGATIVE passages:
UNEP records two bilateral committee meetings in 2013, *but explicitly*
states the demonstration projects themselves were not truly transboundary.

The one online 'original agreement' file appears to be a 2012 template
with blank dated signature lines, not an authenticated signed instrument.
Therefore legal signature day uses FAOLEX 2013 catalog, not falsely this PDF.

Do NOT infer river allocation, crops, water releases or causal outcomes.
"""
import pathlib,datetime as dt,hashlib,json,traceback,re,subprocess,sys,unicodedata,os,csv
import requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"water_source_gate_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"sourou_legal_2013";TMP.mkdir(exist_ok=True)
FILES={
 "UNEP_2016_terminal_evaluation":"https://wedocs.unep.org/bitstream/handle/20.500.11822/20812/1111_2016_te_unep_regional_iw_fsp_volta_river.pdf",
 "IIED_G04090_2016_external_review":"https://www.iied.org/sites/default/files/pdfs/migrate/G04090.pdf",
 "CTGS_2012_template_not_signed":"https://swm-programme.info/documents/20142/955374/MLI_AG_WA_20130620.pdf/24b3ce4e-7d56-14c7-d92a-84fa01385a82?t=1636734943514"}
R={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "files":{},"checks":{},"errors":[],"definitions":{
  "implementation_evidence":"Documentary establishment and activities of Sourou bilateral committees",
  "not_demonstrated":"Actual dam water sharing, river withdrawals and harvested-rice effect",
  "negative_evidence":"UNEP: actual demonstration projects not implemented in transboundary manner",
  "2013_signed_date":"From FAOLEX list, independently cross-referenced to contemporaneous newspaper; available 2012 PDF is draft",
  "2015_activity":"Independent IIED external review says committee met again December 2015"},
 "caveats":["A source quote does not imply project success or implementation of a water-allocation treaty.",
  "Original signed/stamped legal copies need additional verification before treating instruments as authenticated.",
  "Institutional event in 2013 and observed direct irrigated rice category in 2015–2023 have no same-category pre-event counterfactual."]}
def norm(v):
 return re.sub(r"\s+"," ",unicodedata.normalize("NFKD",v)
    .encode("ascii","ignore").decode("ascii").lower()).strip()
def ck(name,good,detail=None):
 R["checks"][name]={"pass":bool(good),"detail":detail}
 if not good:R["errors"].append(name)
try:
 texts={}
 for label,url in FILES.items():
  r=requests.get(url,timeout=(35,140),headers={"User-Agent":"UniversityThesisSourceReplication/1.0"})
  r.raise_for_status()
  f=TMP/(label+".pdf")
  f.write_bytes(r.content)
  with f.open("rb") as fd:sha=hashlib.file_digest(fd,"sha256").hexdigest()
  R["files"][label]={"url":url,"bytes":len(r.content),"sha256":sha,
    "source_is_pdf":bool(r.content.startswith(b"%PDF"))}
  ck("PDF_format_"+label,r.content.startswith(b"%PDF"),len(r.content))
  if not r.content.startswith(b"%PDF"):continue
  ret=subprocess.run(["pdftotext","-layout",str(f),"-"],capture_output=True,text=True,timeout=90)
  ck("pdftotext_exit_"+label,ret.returncode==0,ret.stderr[:180])
  texts[label]=norm(ret.stdout)
  R["files"][label]["pdftotext_characters"]=len(ret.stdout)
 u=texts["UNEP_2016_terminal_evaluation"]
 # Literal independent controls, SOURCE wording rather than secondary metadata
 for key,fragment in [
    ("UNEP_2013_committee_meetings","two bilateral meetings in 2013"),
    ("UNEP_agreements_implemented","agreements were implemented and followed up"),
    ("UNEP_not_truly_transboundary_demos","none of the demonstration projects implemented were actually"),
    ("UNEP_early_warning","early warning system to assist in anticipating floods"),
    ("UNEP_bilateral_technical_committee","joint iwrm technical committee between burkina"),
    ("UNEP_hydromet_equipment_in_Mali","installation of hydro-meteorological equipment in mali")]:
  ck(key,fragment in u,{"key":fragment,"found":fragment in u})
 i=texts["IIED_G04090_2016_external_review"]
 ck("IIED_independent_2015_meeting",
    bool("decembre 2015" in i and ("comite transfrontalier" in i or "comite transfrontaliers" in i)),
    {"reference_month":"2015-12","narrative_verification":"sourou committee met, review"})
 template=texts["CTGS_2012_template_not_signed"]
 ck("template_mentions_2012_not_verified_signed_2013",
    "2012" in template and "sourou" in template and "comite transfrontalier" in template,
    {"template_date_seen":2012,"DO_NOT_CLASSIFY_AS_ACTUAL_SIGNED_2013":True})
 # QA input schema, no copying unstable paragraph text into output
 with (ROOT/"institutions"/"sourou_transboundary_management_primary_evidence_v2.csv").open(newline="",encoding="utf-8") as fd:
  events=list(csv.DictReader(fd))
 ck("evidence_register_sources_at_least10",len(events)>=10,len(events))
 ck("never_classify_irrigation_allocation_from_2013_committee",
   any(x["evidence_grade"]=="NOT_ESTABLISHED" and x["mechanism"]=="bilateral_allocation_rule" for x in events))
 ck("exact_2013_legal_date_recorded_but_signature_copy_disclaimed",
   any(x["date_or_period"]=="2013-06-20" and "NOT_SIGNED_COPY" in x["evidence_grade"] for x in events))
 R["summary"]={"committee_agreements_verified_in_UNEP_review":True,
  "operational_meetings_at_least_2013":True,
  "independent_report_meeting_2015":bool(R["checks"].get("IIED_independent_2015_meeting",{}).get("pass")),
  "physical_water_allocation_to_crop_verified":False,
  "joint_dam_release_effect_on_yield_verified":False,
  "eligible_for_causal_pre_post_in_source_rice_HarvestStat":False}
 R["status"]="PASS" if not R["errors"] else "FAILED"
except Exception as e:
 R["status"]="FAILED";R["errors"].append(repr(e))
 R["traceback"]=traceback.format_exc()[-4500:]
(OUT/"sourou_UNEP_IIED_signed_vs_draft_institution_evidence_QA.json").write_text(
 json.dumps(R,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":R["status"],"errors":R["errors"],"checks":R["checks"],
                  "files":R["files"],"summary":R.get("summary")},indent=2,ensure_ascii=False,default=str)[:19000])
if R["status"]!="PASS":sys.exit(1)
