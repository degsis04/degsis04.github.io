"""Secondary APES dashboard exact static-table audit (Mkondiwa 2023 pinned HTML).
Do not promote this researcher's dashboard to original Ministry APES survey.
Never assume Local/Hybrid/Composite maize equivalence to FEWS Net aggregate without evidence.
"""
import pathlib,os,requests,hashlib,re,json,datetime,sys,traceback,pandas as pd,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
O=ROOT/"results"/"malawi_apes_fdw_source_audit_v1";O.mkdir(exist_ok=True,parents=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"mw_apes_dashboard_extract";TMP.mkdir(parents=True,exist_ok=True)
URL="https://raw.githubusercontent.com/MaxwellMkondiwa/Malawi_APES_Data_App/fbd5629f1200c3c18b615ad87c83297c2ed0bd75/docs/index.html"
SHA="f27ecfcfeb2bf1d710ee9e45bc8ef93deee6bfb5299f7a9bbb61b32e04e06828"
PILOT=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1"/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv"
ELIG=ROOT/"results"/"malawi_maize_semantics_v1"/"main_rainfed_only_district_eligibility.csv"
L={"utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED",
  "scope":["Secondary publicly distributed APES dashboard, published 2023","No primary APES questionnaire/yearly methodology accessible",
  "Dashboard says 1982-2019 but HTML coverage empirically checked, not assumed",
  "Maize type categories Local, Hybrid, Composite may not be exhaustive or identically measured"],
  "checks":{}}
def check(k,b,info=None):
 L["checks"][k]={"pass":bool(b),"detail":info}
 if not b:raise AssertionError(k+": "+str(info))
def norm(s):
 return re.sub(r"[^a-z0-9]+","",str(s).casefold())
try:
 p=TMP/"dashboard.html"
 with requests.get(URL,stream=True,timeout=(30,180),headers={"User-Agent":"MalawiAPESIndependentDashboardQA/1.0"}) as r:
  r.raise_for_status()
  with p.open("wb") as f:
   for chunk in r.iter_content(2**20):
    if chunk:f.write(chunk)
 h=p.read_bytes()
 check("published_dashboard_html_sha",hashlib.sha256(h).hexdigest()==SHA)
 sid=b'htmlwidget-d65a289717b5c014b86e'
 pos=h.find(b'<script type="application/json" data-for="'+sid+b'">')
 check("original_static_datatable_exists",pos>=0)
 start=h.find(b'>',pos)+1;end=h.find(b'</script>',start)
 obj=json.loads(h[start:end])
 cols=["DISTRICT","X","year","crop","HAs","Yield","MTs","Region"]
 arr=obj["x"]["data"]
 check("8_original_columns",len(arr)==len(cols),len(arr))
 lens=list(map(len,arr))
 check("column_lengths_identical",len(set(lens))==1,lens)
 df=pd.DataFrame({col:arr[i] for i,col in enumerate(cols)})
 for c in ("year","HAs","Yield","MTs"):df[c]=pd.to_numeric(df[c],errors="coerce")
 check("all_core_columns_have_names",df.DISTRICT.notna().all() and df.crop.notna().all())
 check("year_between_1980_2025",df.year.dropna().between(1980,2025).all())
 dup=df.duplicated(["DISTRICT","year","crop"],keep=False)
 L["table"]={"rows":len(df),"districts":df.DISTRICT.nunique(),"crop_values":df.crop.value_counts(dropna=False).to_dict(),
   "year_min":int(df.year.min()),"year_max":int(df.year.max()),"year_values":sorted(df.year.dropna().astype(int).unique().tolist()),
   "duplicates_district_year_crop":int(dup.sum()),"regions":df.Region.value_counts(dropna=False).to_dict(),
   "negative_area_rows":int(df.HAs.lt(0).sum()),"missing_area":int(df.HAs.isna().sum()),
   "negative_production_rows":int(df.MTs.lt(0).sum()),"missing_production":int(df.MTs.isna().sum()),
   "yield_units_unverified":True}
 check("dashboard_has_maize_categories",df.crop.str.contains("Maize",case=False,na=False).any())
 valid=df.loc[df.HAs.gt(0)&df.MTs.notna()&df.Yield.gt(0)].copy()
 for factor in (1,1000,.001):
   err=np.abs(valid.HAs*valid.Yield*factor-valid.MTs)/valid.MTs.clip(lower=1)
   L.setdefault("unit_scenarios",[]).append({"factor":factor,"median_relative_error":float(err.median()),
    "fraction_within_1percent":float((err<.01).mean())})
 maize=df.loc[df.crop.str.contains("Maize",case=False,na=False)].copy()
 L["maize"]={"rows":len(maize),"types":maize.crop.value_counts(dropna=False).to_dict(),
   "districts":maize.DISTRICT.nunique(),"n_unique_district_year":len(maize[["DISTRICT","year"]].drop_duplicates()),
   "years":sorted(maize.year.dropna().astype(int).unique().tolist())}
 # No automatic aggregate claim: create candidate hypothetical sum to test against source.
 groups=maize.groupby(["DISTRICT","Region","year"],dropna=False)
 agg=groups.agg(n_types=("crop","nunique"),
   crop_types=("crop",lambda a:" | ".join(sorted(set(a)))),
   area_ha_sum_candidate=("HAs","sum"),production_t_sum_candidate=("MTs","sum"),
   n_rows=("crop","size")).reset_index()
 agg["implied_candidate_yield"]=agg.production_t_sum_candidate/agg.area_ha_sum_candidate.replace(0,np.nan)
 agg.to_csv(O/"secondary_APES_dashboard_maize_type_sums_CANDIDATE_NOT_VERIFIED.csv",index=False)
 origin=pd.read_csv(PILOT)
 elig=pd.read_csv(ELIG)[["fnid","admin_1","admin_2"]]
 origin=origin.merge(elig,on="fnid",validate="many_to_one")
 origin=origin.loc[(origin.season_name=="Main")&(origin.crop_production_system=="Rainfed (PS)")].copy()
 check("812_main",len(origin)==812)
 agg["key"]=agg.DISTRICT.map(norm)+"|"+agg.Region.map(norm)+"|"+agg.year.astype(str)
 origin["key"]=origin.admin_2.map(norm)+"|"+origin.admin_1.map(norm)+"|"+origin.harvest_year.astype(str)
 # Independent overlapping exact district/region/year; no fuzzy or shifted mapping.
 candidates=origin.merge(agg,on="key",how="inner",validate="one_to_one",suffixes=("_hs","_apes"))
 if not candidates.empty:
  candidates["rel_error_prod"]=np.abs(candidates.production_t_sum_candidate-candidates.production)/candidates.production
  candidates["rel_error_area"]=np.abs(candidates.area_ha_sum_candidate-candidates.area)/candidates.area
  candidates["rel_error_implied_yield"]=np.abs(candidates.implied_candidate_yield-candidates["yield"])/candidates["yield"]
  candidates["production_exact"]=np.isclose(candidates.production_t_sum_candidate,candidates.production,rtol=1e-8,atol=1e-6)
  candidates["area_exact"]=np.isclose(candidates.area_ha_sum_candidate,candidates.area,rtol=1e-8,atol=1e-6)
 else:
  for c in ["rel_error_prod","rel_error_area","rel_error_implied_yield","production_exact","area_exact"]:
   candidates[c]=pd.Series(dtype=float if c.startswith("rel") else bool)
 candidates[["fnid","admin_2","harvest_year","production","area","DISTRICT","Region","year",
     "n_types","crop_types","area_ha_sum_candidate","production_t_sum_candidate",
     "rel_error_prod","rel_error_area","rel_error_implied_yield","production_exact","area_exact"]].to_csv(
     O/"secondary_APES_dashboard_2000s_versus_HarvestStat_DESCRIPTIVE.csv",index=False)
 L["comparison"]={"candidate_overlap":len(candidates),
   "production_exact":int(candidates.production_exact.sum()),"area_exact":int(candidates.area_exact.sum()),
   "both_exact":int((candidates.production_exact&candidates.area_exact).sum()),
   "median_rel_error_prod":float(candidates.rel_error_prod.median()) if len(candidates) else None,
   "median_rel_error_area":float(candidates.rel_error_area.median()) if len(candidates) else None,
   "types_count_dist":candidates.n_types.value_counts().to_dict(),
   "warning":"Candidate sum of maize subtypes is not a validated official aggregate or independent raw APES proof."}
 L["status"]="SECONDARY_APES_EXTRACT_PASS_NOT_PRIMARY"
except Exception as e:
 L["status"]="FAILED";L["error"]=repr(e);L["traceback"]=traceback.format_exc()[-4000:]
(O/"secondary_APES_dashboard_extraction_QA.json").write_text(json.dumps(L,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({k:v for k,v in L.items() if k in ["status","table","maize","comparison","unit_scenarios","error"]},ensure_ascii=False)[:9000])
sys.exit(0 if L["status"]=="SECONDARY_APES_EXTRACT_PASS_NOT_PRIMARY" else 1)
