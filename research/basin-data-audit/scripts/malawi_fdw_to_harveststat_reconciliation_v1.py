"""Exact FNID×year×season×system Malawi maize FDW→HarvestStat audit.
Uses canonical FDW raw bytes (pinned Dryad SHA-256), never automatic period shift.
APES dashboard is inspected as a separate secondary source and NOT assumed to
share category definitions. Raw FDW inputs are not redistributed in Git.
"""
import io,os,json,hashlib,pathlib,zipfile,datetime,sys,traceback,re,collections
import pandas as pd, numpy as np, requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
O=ROOT/"results"/"malawi_apes_fdw_source_audit_v1";O.mkdir(exist_ok=True,parents=True)
TMP=pathlib.Path(os.getenv("RUNNER_TEMP","/tmp"))/"apes_fdw_exact_compare";TMP.mkdir(exist_ok=True,parents=True)
FDW_URL="https://github.com/HarvestStat/HarvestStat-Africa/releases/download/v1.2/doi_10_5061_dryad_vq83bk42w__v20260717.zip"
OUTER_SHA="2ff71261f39b207c0b9d5becaa9efce891cba035d80e0df0acadc7b9b190218f"
FDW_SHA="6e8128f8854f38172aea24583e537395242abafab4382441b3d53805c44b452b"
APES_URL="https://raw.githubusercontent.com/MaxwellMkondiwa/Malawi_APES_Data_App/fbd5629f1200c3c18b615ad87c83297c2ed0bd75/docs/index.html"
APES_SHA="f27ecfcfeb2bf1d710ee9e45bc8ef93deee6bfb5299f7a9bbb61b32e04e06828"
PILOT=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1"/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv"
LOG={"run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED",
 "source_urls":{"fdw_release":FDW_URL,"APES_dash":APES_URL},
 "method":["Strict exact fnid+harvest_year+season_name+crop_production_system keys",
           "No stitching Main/Rainfed with Annual/All; no inferred mapping of area planted to harvested",
           "Raw FDW values are not independently measured APES data",
           "Zero/missing and multiple candidate values remain distinct"],
 "checks":{},"warnings":[]}
def check(k,b,details=None):
    LOG["checks"][k]={"pass":bool(b),"detail":details}
    if not b:raise AssertionError(k+": "+str(details))
def download(url,p,expected):
    if not p.exists():
        with requests.get(url,stream=True,timeout=(30,180),headers={"User-Agent":"AcademicMalawiSourceReconciliation/1.0"}) as r:
            r.raise_for_status()
            with p.open("wb") as f:
                for chunk in r.iter_content(2**20):
                    if chunk:f.write(chunk)
    a=hashlib.sha256(p.read_bytes()).hexdigest()
    check("sha_"+p.name,a==expected,a)
    return p
def exactnum(a,b):
    if pd.isna(a) or pd.isna(b):return False
    return abs(float(a)-float(b))<=max(1e-8,abs(float(b))*1e-8)
try:
    bundle=download(FDW_URL,TMP/"source_bundle_v1.2.zip",OUTER_SHA)
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
        members=[n for n in z.namelist() if n.endswith("fdw_raw_data_v1.2.zip")]
        check("one_fdwy_zip",len(members)==1,members)
        fdwbytes=z.read(members[0])
    check("fdw_raw_sha",hashlib.sha256(fdwbytes).hexdigest()==FDW_SHA)
    with zipfile.ZipFile(io.BytesIO(fdwbytes)) as z:
        assert z.testzip() is None
        members=[n for n in z.namelist() if n.endswith("adm_crop_data_raw_MW.csv")]
        check("one_raw_mw",len(members)==1,members)
        fdw=pd.read_csv(io.BytesIO(z.read(members[0])),low_memory=False)
    src=pd.read_csv(PILOT)
    check("pilot_915",len(src)==915)
    check("pilot_uniqueness",not src.duplicated(["fnid","harvest_year","season_name","crop_production_system"]).any())
    check("raw_total",len(fdw)==51892)
    check("raw_unique_ids",fdw["id"].is_unique)
    fdw["year"]=pd.to_datetime(fdw["period_date"],errors="coerce").dt.year
    fdw["value_num"]=pd.to_numeric(fdw.value,errors="coerce")
    maize=fdw.loc[fdw["product"].eq("Maize Grain (White)")].copy()
    check("fdw_maize_product_nonempty",len(maize)>800,len(maize))
    LOG["fdw_maize"]={"rows":len(maize),"record_status":maize.status.value_counts(dropna=False).to_dict(),
      "indicator_counts":maize.indicator.value_counts(dropna=False).to_dict(),
      "source_document_counts":maize.source_document.value_counts(dropna=False).to_dict(),
      "season_counts":maize.groupby(["season_name","crop_production_system"],dropna=False).size().to_dict().__repr__(),
      "years":(int(maize.year.min()),int(maize.year.max())),
      "publication_names":maize.publication_name.value_counts(dropna=False).head(20).to_dict()}
    check("raw_all_date_year_readable",not maize.year.isna().any())
    mkey=["fnid","year","season_name","crop_production_system"]
    dups=maize.duplicated(mkey+["indicator"],keep=False)
    LOG["fdw_maize"]["duplicate_same_full_key_indicator_count"]=int(dups.sum())
    summary_rows=[]
    raw_dict={tuple(k):g for k,g in maize.groupby(mkey,dropna=False,sort=False)}
    indicators=["Area Harvested","Area Planted","Quantity Produced","Yield"]
    for s in src.itertuples(index=False):
        key=(s.fnid,int(s.harvest_year),s.season_name,s.crop_production_system)
        g=raw_dict.get(key)
        rec={"fnid":s.fnid,"harvest_year":int(s.harvest_year),"season_name":s.season_name,
        "crop_production_system":s.crop_production_system,
        "hs_area_ha":float(s.area),"hs_production_t":float(s.production),"hs_yield_t_ha":float(s.yield),
        "raw_same_key_rows":len(g) if g is not None else 0}
        if g is not None and len(g):
            rec["raw_source_documents"]=" | ".join(sorted(g.source_document.dropna().unique()))
            rec["raw_publication_names"]=" | ".join(sorted(g.publication_name.dropna().astype(str).unique())[:10])
            rec["raw_status_codes"]=" | ".join(sorted(g.status.dropna().astype(str).unique()))
        else:rec["raw_source_documents"]=rec["raw_publication_names"]=rec["raw_status_codes"]=""
        for ind,target in [("Area Harvested",s.area),("Area Planted",s.area),("Quantity Produced",s.production),("Yield",s.yield)]:
            typ={"Area Harvested":"area_harvested","Area Planted":"area_planted","Quantity Produced":"production","Yield":"yield"}[ind]
            z=g.loc[g.indicator.eq(ind)] if g is not None else pd.DataFrame(columns=maize.columns)
            vals=z.value_num.dropna().to_numpy()
            rec["raw_"+typ+"_n"]=len(vals)
            rec["raw_"+typ+"_values"]=" | ".join(format(float(t),".12g") for t in vals[:6])
            rec["raw_"+typ+"_exact_matches"]=sum(exactnum(float(v),target) for v in vals)
            rec["raw_"+typ+"_relative_error_min"]=float(min(abs(float(v)-float(target))/max(abs(float(target)),1e-12) for v in vals)) if len(vals) else None
        rec["production_match"]=rec["raw_production_exact_matches"]>0
        rec["area_harvested_match"]=rec["raw_area_harvested_exact_matches"]>0
        rec["area_planted_match"]=rec["raw_area_planted_exact_matches"]>0
        rec["yield_match"]=rec["raw_yield_exact_matches"]>0
        rec["any_area_match"]=rec["area_harvested_match"] or rec["area_planted_match"]
        rec["all_prod_area_match"]=bool(rec["production_match"] and rec["any_area_match"])
        rec["all_three_match"]=bool(rec["all_prod_area_match"] and rec["yield_match"])
        rec["raw_unique_document"]=bool(g is not None and g.source_document.nunique()==1)
        summary_rows.append(rec)
    out=pd.DataFrame(summary_rows)
    out.to_csv(O/"malawi_915_FDW_raw_source_value_reconciliation.csv",index=False)
    raw_years=out.groupby(["season_name","crop_production_system","harvest_year"],dropna=False).agg(
       n_hs=("fnid","size"),n_source_keys=("raw_same_key_rows",lambda a:int((a>0).sum())),
       n_area_harvested_equal=("area_harvested_match","sum"),n_area_planted_equal=("area_planted_match","sum"),
       n_prod_equal=("production_match","sum"),n_yield_equal=("yield_match","sum"),
       n_area_and_prod_equal=("all_prod_area_match","sum"),
       n_all_three_equal=("all_three_match","sum")).reset_index()
    raw_years.to_csv(O/"malawi_915_FDW_match_by_harvest_year.csv",index=False)
    def stats(d):
        return {"rows":len(d),"raw_exact_key":int((d.raw_same_key_rows>0).sum()),
          "area_harvested_equal":int(d.area_harvested_match.sum()),
          "area_planted_equal":int(d.area_planted_match.sum()),
          "production_equal":int(d.production_match.sum()),
          "yield_equal":int(d.yield_match.sum()),
          "any_area_plus_production":int(d.all_prod_area_match.sum()),
          "all_three":int(d.all_three_match.sum()),
          "multiple_document_sources":int((d.raw_same_key_rows.gt(0) & ~d.raw_unique_document).sum())}
    LOG["strict_key_915"]=stats(out)
    LOG["strict_key_by_system"]={f"{x}|{y}":stats(g) for (x,y),g in out.groupby(["season_name","crop_production_system"])}
    check("all_915_audited",len(out)==915)
    check("raw_key_count_not_bigger_than_whole_file",out.raw_same_key_rows.max()<=len(maize))
    # Diagnostics for catalog mapping only; never create fake shifted key.
    m=maize.loc[maize.indicator.eq("Quantity Produced")].copy()
    s0=src[["fnid","harvest_year","production","season_name","crop_production_system"]].copy()
    yy=[]
    for shift in (-1,0,1):
        keydf=m[["fnid","year","season_name","crop_production_system","value_num"]].copy()
        keydf["year"]-=shift
        merged=s0.merge(keydf,left_on=["fnid","harvest_year","season_name","crop_production_system"],
            right_on=["fnid","year","season_name","crop_production_system"],how="inner")
        yy.append({"nominal_source_year_minus_hs_year":shift,"raw_pair_candidates":len(merged),
                   "equal_production":int(sum(exactnum(v,w) for v,w in zip(merged.value_num,merged.production)))})
    LOG["year_shift_diagnostic_not_year_mapping"]=yy
    # Published independent historical dashboard is a secondary source:
    html=download(APES_URL,TMP/"mkondiwa_ap_es_2023.html",APES_SHA).read_bytes()
    widgets=[]
    for m in re.finditer(rb'<script\b[^>]*type=["\']application/json["\'][^>]*data-for=["\']([^"\']+)["\'][^>]*>',html,re.I):
        start=m.end();end=html.find(b"</script>",start)
        if end<0:continue
        payload=html[start:end]
        try:j=json.loads(payload)
        except Exception as e:widgets.append({"id":m.group(1).decode("utf-8","replace"),"decode_failed":str(e)[:80]});continue
        sid=m.group(1).decode("utf-8","replace")
        t={"id":sid,"json_bytes":len(payload),"root_keys":list(j.keys()) if isinstance(j,dict) else []}
        x=j.get("x",{}) if isinstance(j,dict) else {}
        if isinstance(x,dict):
            t["x_keys"]=list(x.keys())
            for field in ["data","colnames","columns"]:
                v=x.get(field)
                if v is not None:
                    t[field+"_type"]=type(v).__name__;t[field+"_n"]=len(v) if hasattr(v,"__len__") else None
                    t[field+"_sample"]=repr(v[:2] if isinstance(v,list) else list(v)[:10] if isinstance(v,dict) else v)[:380]
        widgets.append(t)
    LOG["apes_data_widgets"]=widgets
    LOG["apes_dash_summary"]={"html_bytes":len(html),
       "age":"2023 snapshot, not a complete primary ministry APES archive",
       "embedded_year_items_regex":(re.search(rb'"value"\s*:\s*\[([^\]]*)\]',html) or [b"",b""])[1][:400].decode("utf-8","replace") if b'"value"' in html else None,
       "widgets_json":len(widgets),"widget_top_sizes":sorted(widgets,key=lambda x:x.get("json_bytes",0),reverse=True)[:8]}
    LOG["status"]="COMPARISON_PASS_WITH_SOURCE_LIMITS"
except Exception as ex:
    LOG["status"]="FAILED";LOG["error"]=repr(ex);LOG["traceback"]=traceback.format_exc()[-4000:]
(O/"malawi_FDW_to_HarvestStat_reconciliation_QA.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str,allow_nan=True)+"\n")
print(json.dumps({"status":LOG["status"],"strict":LOG.get("strict_key_915"),"year":LOG.get("year_shift_diagnostic_not_year_mapping"),
 "error":LOG.get("error")},ensure_ascii=False)[:5000])
sys.exit(0 if LOG["status"]=="COMPARISON_PASS_WITH_SOURCE_LIMITS" else 1)
