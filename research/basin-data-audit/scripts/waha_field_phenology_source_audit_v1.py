"""Independent LSMS-ISA field-reported planting/harvest audit (Waha et al. 2026).

SOURCE: Katharina Waha et al., AfricanCropCalendar.csv,
https://github.com/koendvos/AfricanCropCalendar, peer-reviewed
https://doi.org/10.1038/s41597-026-07906-9

Privacy: Do not export GPS, household IDs, plot IDs, EA IDs or observation rows.
Output aggregated ONLY country×crop and admin1×crop tables, suppress n<30.
The Mali planting YEAR is missing; Niger planting/harvest YEARS missing:
therefore neither annual crop-year JRC validation nor trends in these
countries can be inferred. Only MONTH-of-year comparisons are considered.
"""
import datetime as dt,hashlib,json,pathlib,sys,traceback,re,unicodedata,os
import requests,numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"field_phenology_v1";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"field_phenology_waha";TMP.mkdir(parents=True,exist_ok=True)
URL="https://raw.githubusercontent.com/koendvos/AfricanCropCalendar/main/AfricanCropCalendar.csv"
SHA_GITBLOB="7d6ed8d701d2bf2188bd48a68e9e3fe0c94b43fd"
SIZE=93628545
DOI="https://doi.org/10.1038/s41597-026-07906-9"
TARGET={"Mali":"ML","Malawi":"MW","Niger":"NE","Nigeria":"NG","Uganda":"UG","Ethiopia":"ET"}
CROPS={"maize":"Maize","corn":"Maize","sorghum":"Sorghum","rice":"Rice",
       "zea mays":"Maize","sorghum bicolor":"Sorghum","oryza sativa":"Rice"}
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "source":{"url":URL,"doi":DOI,"github_blob_sha1":SHA_GITBLOB,"expected_bytes":SIZE},
 "redaction":"Aggregate country×crop or admin1×crop only; never export GPS/household/plot rows",
 "method":"Unweighted observational survey month-of-year distributions; NOT national crop-area representative; no year imputations",
 "warnings":[
  "Mali planting_year missing by source design; survey years not harvest/planting years",
  "Niger planting and harvest years missing; do not infer complete crop-year intervals",
  "Survey points may be anonymized / displaced up to 10km rural: do not spatially intersect raw GPS against small schemes",
  "Survey is predominantly rainfed in Mali according to authors; no validation of irrigated rice specificity",
  "Field-reported monthly dates subject to recall, survey waves differ, and some years missing",
  "Do not infer that a national field survey crop calendar matches every subnational JRC polygon",
  "Never join Waha survey outcomes directly to HarvestStat yields; purpose is external timing validation"],
 "checks":{},"errors":[]}
def ck(name,good,details=None):
 LOG["checks"][name]={"pass":bool(good),"detail":details}
 if not good:LOG["errors"].append(name)
def save():
 (OUT/"waha_field_source_qa.json").write_text(json.dumps(LOG,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
def norm(x):
 if pd.isna(x):return ""
 text=unicodedata.normalize("NFKD",str(x)).encode("ascii","ignore").decode().casefold()
 return re.sub(r"[^a-z0-9]","",text)
def country_class(x):
 v=norm(x)
 for n,c in TARGET.items():
  if v in {norm(n),c.casefold(),norm({"ML":"MLI","MW":"MWI","NE":"NER","NG":"NGA","UG":"UGA","ET":"ETH"}[c])}:return n
 return "UNRESOLVED"
def crop_class(x):
 v=norm(x)
 if v in ("maize","maizecorn","corn","zeamays"):return "Maize"
 if v in ("sorghum","sorghumbicolor"):return "Sorghum"
 if v in ("rice","paddyrice","oryzasativa"):return "Rice"
 return "OTHER"
try:
 file=TMP/"AfricanCropCalendar.csv"
 if not file.exists() or file.stat().st_size!=SIZE:
  with requests.get(URL,stream=True,timeout=(30,210),headers={"User-Agent":"GraduateThesisDatasetValidation/1.0"}) as r:
   r.raise_for_status()
   with file.open("wb") as f:
    for chunk in r.iter_content(2**20):
     if chunk:f.write(chunk)
 stat=file.stat()
 ck("original_expected_file_size",stat.st_size==SIZE,stat.st_size)
 with file.open("rb") as f:
  sh=hashlib.sha1();sh.update(f"blob {stat.st_size}\0".encode())
  sha256=hashlib.sha256()
  while True:
   b=f.read(4<<20)
   if not b:break
   sh.update(b);sha256.update(b)
 gitsha=sh.hexdigest()
 ck("original_github_blob_sha",gitsha==SHA_GITBLOB,gitsha)
 LOG["source"].update({"actual_github_blob_sha":gitsha,"sha256":sha256.hexdigest(),
                       "actual_bytes":stat.st_size})
 df=pd.read_csv(file,low_memory=False,encoding="utf-8-sig")
 LOG["source"]["row_count"]=len(df)
 LOG["source"]["columns"]=list(df.columns)
 ck("expected_raw_rows_451550",len(df)==451550,len(df))
 required=["country","crop_simplified","planting_month","harvest_month_begin",
           "harvest_month_end","adm1"]
 ck("essential_source_columns_present",all(x in df for x in required),
    [x for x in required if x not in df])
 if not LOG["checks"]["essential_source_columns_present"]["pass"]:
  raise ValueError("Missing essential fields; inspect schema before analysis")
 df["country_name_verified"]=df.country.map(country_class)
 df["crop_target"]=df.crop_simplified.map(crop_class)
 LOG["source"]["country_counts"]=df.country.astype(str).value_counts().head(15).to_dict()
 LOG["source"]["crop_examples"]=df.crop_simplified.astype(str).value_counts().head(30).to_dict()
 LOG["source"]["country_resolution_unresolved"]=int(df.country_name_verified.eq("UNRESOLVED").sum())
 ck("all_countries_recognized",df.country_name_verified.ne("UNRESOLVED").all(),
    LOG["source"]["country_resolution_unresolved"])
 for v in ["planting_month","harvest_month_begin","harvest_month_end",
           "planting_year","year_harvest_begin","harvest_year_end"]:
  if v in df:
   df[v]=pd.to_numeric(df[v],errors="coerce")
   df[v+"_valid"]=df[v].between(1,12) if "month" in v else df[v].between(1900,2025)
 df=df.loc[df.crop_target.isin(("Maize","Sorghum","Rice"))].copy()
 LOG["counts"]={"three_crop_field_rows":len(df),
   "survey_countries":int(df.country_name_verified.nunique())}
 if "planting_year" in df:
  LOG["counts"]["Mali_planting_year_present"]=int(df.loc[df.country_name_verified.eq("Mali"),
                                                     "planting_year_valid"].sum())
 if "year_harvest_begin" in df:
  LOG["counts"]["Niger_harvest_year_begin_present"]=int(df.loc[df.country_name_verified.eq("Niger"),
                                                        "year_harvest_begin_valid"].sum())
 result=[]; regions=[]
 # Year metadata not used to compute within-country seasons.
 for (country,crop),g in df.groupby(["country_name_verified","crop_target"],sort=True):
  vplant=g.planting_month.dropna().loc[g.planting_month.between(1,12)]
  vharv=g.harvest_month_begin.dropna().loc[g.harvest_month_begin.between(1,12)]
  x={"country":country,"crop":crop,"n_source_field_records":len(g),
     "n_valid_plant_month":len(vplant),"n_valid_harvest_begin_month":len(vharv),
     "plant_month_missing_pct":round(100*(len(g)-len(vplant))/len(g),2),
     "harvest_month_missing_pct":round(100*(len(g)-len(vharv))/len(g),2)}
  for kind,valid in [("plant",vplant),("harvest",vharv)]:
   freqs=valid.astype(int).value_counts().reindex(range(1,13),fill_value=0)
   for mon in range(1,13):
    x[f"{kind}_n_m{mon:02}"]=int(freqs.loc[mon])
   x[f"{kind}_modal_month"]=int(freqs.idxmax()) if len(valid) else None
   x[f"{kind}_modal_fraction"]=round(freqs.max()/len(valid),4) if len(valid) else None
  result.append(x)
  if "adm1" in g:
   for adm,region in g.groupby("adm1",dropna=True):
    if len(region)<30:continue
    pv=region.loc[region.planting_month.between(1,12),"planting_month"]
    hv=region.loc[region.harvest_month_begin.between(1,12),"harvest_month_begin"]
    if min(len(pv),len(hv))<30:continue
    xx={"country":country,"crop":crop,"adm1_name":str(adm),
       "adm1_normalized":norm(adm),
       "n_source_field_records":len(region),
       "n_valid_plant_month":len(pv),"n_valid_harvest_month":len(hv),
       "suppression_rule":"all output cells >=30 observations; no GPS or IDs"}
    for k,rr in [("plant",pv),("harvest",hv)]:
     freq=rr.astype(int).value_counts().reindex(range(1,13),fill_value=0)
     xx[f"{k}_modal_month"]=int(freq.idxmax())
     for mo in range(1,13):xx[f"{k}_n_m{mo:02}"]=int(freq.loc[mo])
    regions.append(xx)
 national=pd.DataFrame(result)
 admin=pd.DataFrame(regions)
 national.to_csv(OUT/"waha_country_crop_month_distribution.csv",index=False)
 admin.to_csv(OUT/"waha_admin1_crop_month_distribution_anonymized.csv",index=False)
 LOG["counts"]["country_crop_summary_rows"]=len(national)
 LOG["counts"]["adm1_crop_summary_rows_n30"]=len(admin)
 LOG["counts"]["country_crop_table"]=national[
    ["country","crop","n_source_field_records","n_valid_plant_month",
     "n_valid_harvest_begin_month","plant_modal_month","harvest_modal_month"]].to_dict("records")
 LOG["counts"]["adm1_by_country"]=admin.groupby(["country","crop"]).size().reset_index(name="adm1_count").to_dict("records") if len(admin) else []
 ck("no_sensitive_coordinates_exported",all(not any(s in col.lower() for s in
    ["lat","lon","gps","household","plot","eaid","enumerat","parcel"]) for col in admin.columns))
 LOG["status"]="COMPLETE" if not LOG["errors"] else "FAILED"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(str(e)[:500]);LOG["traceback"]=traceback.format_exc()[-4000:]
finally:save()
print(json.dumps({"status":LOG["status"],"checks":LOG["checks"],"errors":LOG["errors"],"counts":LOG.get("counts"),
                  "source_sha256":LOG["source"].get("sha256")},ensure_ascii=False,indent=2,default=str)[:22000])
if LOG["status"]!="COMPLETE":sys.exit(1)
