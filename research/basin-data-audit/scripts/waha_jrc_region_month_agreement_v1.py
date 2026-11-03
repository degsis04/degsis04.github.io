"""Auditable regional survey-vs-JRC crop-calendar comparison, no person-level records.
Input 1: Waha et al. (2026) anonymized survey month histograms by administrative region.
Input 2: JRC ASAP independent reference crop sowing/harvesting dekads.
Comparison at country + explicitly reviewed GAUL1 admin1 region + crop only.

This is a plausibility/sensitivity check on reference climatological months,
not field-level validation of JRC phenology and NOT the validation of
HarvestStat crop-specific outcome definitions or institution effects.
"""
import datetime as dt, json, pathlib, unicodedata, re, sys, traceback
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"field_phenology_v1"
J=ROOT/"results"/"phenology_v1"/"jrc_asap_8countries_subnational_crop_dekads.csv"
A=OUT/"waha_admin1_crop_month_distribution_anonymized.csv"
P=OUT/"waha_field_source_qa.json"
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
  "comparison":"Monthly (not dekadal) unweighted survey histograms vs independent static JRC sowing/harvest month windows",
  "source_Waha":"Waha et al. Scientific Data 2026, DOI 10.1038/s41597-026-07906-9, author's current pinned GitHub CSV",
  "source_JRC":"European Commission JRC ASAP 2018, original GAUL1 csv, verified source SHA256",
  "explicit_region_aliases":{
   "Malawi":{"central":"Central Region","northern":"Northern Region","southern":"Southern Region"},
   "Mali":{"segou":"Segou","sikasso":"Sikasso","kayes":"Kayes","koulikoro":"Koulikoro"}},
  "limits":[
   "Survey months are field-reported, subject to recall bias and varying coverage by wave.",
   "Unweighted counts are not survey-weighted national or crop-area representative estimates.",
   "Mali planting year missing, so year-by-year calendar alignment and shifts cannot be verified.",
   "Rainfed plots dominate Mali survey; no irrigated rice validation.",
   "Small admin1 or crop samples <30 suppressed in prior source output.",
   "Month windows span dekad-defined JRC boundaries: a month counted even if just one dekad overlaps.",
   "Only explicit named admin1 matches, no fuzzy auto-join; geographic survey sample != HarvestStat boundary.",
   "Comparative month agreement does NOT automatically upgrade JRC×HarvestStat outcome strata to validated."],
  "checks":{},"errors":[]}
def check(n,good,more=None):
 LOG["checks"][n]={"pass":bool(good),"details":more}
 if not good:LOG["errors"].append(n)
def norm(v):
 v=unicodedata.normalize("NFKD",str(v)).encode("ascii","ignore").decode().casefold()
 return re.sub(r"[^a-z0-9]","",v)
def m(d):
 v=int(d)
 assert 1<=v<=36
 return (v-1)//3+1
def months(a,b):
 """Inclusive circular month sequence from dekads, for a single season."""
 a,b=m(a),m(b)
 seq=[a]
 while seq[-1]!=b:
  seq.append(seq[-1]%12+1)
  assert len(seq)<=12,(a,b,seq)
 return seq
def weighted_counts_fraction(row,col,allowed):
 freq=np.array([int(row[f"{col}_n_m{i:02}"]) for i in range(1,13)])
 n=int(freq.sum())
 assert n==int(row["n_valid_plant_month"] if col=="plant" else row["n_valid_harvest_month"])
 return (int(sum(freq[mon-1] for mon in allowed)),n,float(sum(freq[mon-1] for mon in allowed)/n))
try:
 qa=json.loads(P.read_text())
 check("Waha_pinned_source_hash_ok",qa["checks"]["original_github_blob_sha"]["pass"])
 check("Waha_source_table2_count_ok",qa["checks"]["source_table2_total_rows_462347"]["pass"])
 a=pd.read_csv(A)
 j=pd.read_csv(J)
 audit=[]
 for country in ("Mali","Malawi"):
  aa=a.loc[a.country.eq(country)].copy()
  jj=j.loc[j.name0_shr.eq(country)].copy()
  alias=LOG["explicit_region_aliases"][country]
  for r in aa.itertuples(index=False):
   name=alias.get(r.adm1_normalized)
   if not name:
    audit.append({"country":country,"adm1_survey":r.adm1_name,
       "crop":r.crop,"status":"UNMATCHED_NO_EXPLICIT_ADMIN_ALIAS"})
    continue
   c=jj.loc[jj.name1_shr.map(norm).eq(norm(name)) & jj.crop.eq(r.crop)]
   if len(c)!=1:
    audit.append({"country":country,"adm1_survey":r.adm1_name,
       "JRC_admin1":name,"crop":r.crop,
       "status":"NO_UNIQUE_JRC_CROP_WINDOW","source_match_count":len(c)})
    continue
   jjrow=c.iloc[0]
   sow=months(jjrow.sos_s,jjrow.sos_e)
   harvest=months(jjrow.eos_s,jjrow.eos_e)
   row=r._asdict()
   valid_sow,ns,ps=weighted_counts_fraction(row,"plant",sow)
   valid_harv,nh,ph=weighted_counts_fraction(row,"harvest",harvest)
   audit.append({
    "country":country,"adm1_survey":r.adm1_name,"JRC_admin1":name,
    "crop":r.crop,"JRC_crop_name":jjrow.crop_name,"status":"MATCH_ADMIN1_CROP_MONTH_REFERENCE_ONLY",
    "survey_n_fields":int(r.n_source_field_records),
    "survey_n_valid_sowing":ns,
    "survey_n_valid_harvest_begin":nh,
    "survey_sowing_modal_month":int(r.plant_modal_month),
    "survey_harvest_modal_month":int(r.harvest_modal_month),
    "JRC_sowing_dekads":f"{int(jjrow.sos_s)}-{int(jjrow.sos_e)}",
    "JRC_harvest_dekads":f"{int(jjrow.eos_s)}-{int(jjrow.eos_e)}",
    "JRC_sowing_months":";".join(map(str,sow)),
    "JRC_harvest_months":";".join(map(str,harvest)),
    "survey_sowing_n_within_JRC":valid_sow,
    "survey_sowing_fraction_in_JRC_months":ps,
    "survey_harvest_n_within_JRC":valid_harv,
    "survey_harvest_fraction_in_JRC_months":ph,
    "survey_year_specific_validation":False,
    "HarvestStat_PS_verified":False,
    "source_region_area_weights_available":False})
 results=pd.DataFrame(audit)
 results.to_csv(OUT/"waha_vs_jrc_Mali_Malawi_admin1_month_agreement.csv",index=False)
 matched=results.loc[results.status.eq("MATCH_ADMIN1_CROP_MONTH_REFERENCE_ONLY")]
 check("only_two_target_countries",set(results.country)=={"Mali","Malawi"},results.country.value_counts().to_dict())
 check("source_all_month_count_exhaustive",bool(
   matched.survey_sowing_n_within_JRC.le(matched.survey_n_valid_sowing).all() and
   matched.survey_harvest_n_within_JRC.le(matched.survey_n_valid_harvest_begin).all()))
 check("fraction_in_zero_to_one",bool(matched.survey_sowing_fraction_in_JRC_months.between(0,1).all() and
   matched.survey_harvest_fraction_in_JRC_months.between(0,1).all()))
 check("no_duplicate_country_region_crop",not matched.duplicated(["country","JRC_admin1","crop"]).any())
 check("aggregate_min_30",matched.survey_n_valid_sowing.ge(30).all() and matched.survey_n_valid_harvest_begin.ge(30).all())
 LOG["counts"]={"survey_admin1_crop_records":len(a),
                "target_Mali_Malawi_rows":len(results),
                "source_region_crop_month_comparisons":len(matched),
                "unmatched_source_region_crop":len(results)-len(matched),
                "sowing_measured_total":int(matched.survey_n_valid_sowing.sum()),
                "harvest_measured_total":int(matched.survey_n_valid_harvest_begin.sum()),
                "agreement_country_crop":matched.groupby(["country","crop"]).agg(
                   region_crop_pairs=("status","size"),
                   n_sowing_valid=("survey_n_valid_sowing","sum"),
                   n_sow_in_JRC=("survey_sowing_n_within_JRC","sum"),
                   n_harvest_valid=("survey_n_valid_harvest_begin","sum"),
                   n_harv_in_JRC=("survey_harvest_n_within_JRC","sum")
                 ).reset_index().to_dict("records"),
                "regions_by_country":matched.groupby("country").JRC_admin1.nunique().to_dict()}
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(repr(e))
 LOG["traceback"]=traceback.format_exc()[-3500:]
(OUT/"waha_jrc_region_agreement_QA.json").write_text(
 json.dumps(LOG,ensure_ascii=False,indent=2,default=str,allow_nan=False)+"\n")
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],
                  "counts":LOG.get("counts")},ensure_ascii=False,indent=2,default=str)[:18000])
if LOG["status"]!="COMPLETE":sys.exit(1)
