"""Rigorous audit of MIRCA rice exposure against observed HarvestStat rice outcomes.

No assumptions of irrigation scheme membership. Geographic labels extracted
from official HarvestStat boundaries for candidate FNIDs, never guessed.
Checks pre/post 2015 and 2020 outcome years separately and missingness.
Uses full official HarvestStat v1.2 source, pinned SHA from prior provenance.
"""
import datetime as dt,hashlib,json,os,pathlib,traceback
import pandas as pd, numpy as np, geopandas as gpd, requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"rice_feasibility";OUT.mkdir(parents=True,exist_ok=True)
TMP=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"rice_feasibility";TMP.mkdir(exist_ok=True)
PROV=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())
EXP=ROOT/"results"/"mirca_os"/"district_exposure"/"district_irrigation_crop_share_2015_2020.csv"
KEY_FOCUS=["ML2016A104","ML2016A105","BF2020A24606","BF2020A25301","ZM2011A20601","MW2018A20330","MW2018A20321"]
LOG={"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED","error":None,
 "inputs":{},"definitions":{
  "year_window":"1981–2024 harvest years observed, not imputed",
  "source_row_good":"qc_flag==0, area>0, production>0, yield>0; at least harvest year",
  "unit_of_analysis":"fnid × Rice × season_name × crop_production_system × harvest_year",
  "unique_full_key":"do not sum/average simultaneous seasons and production systems",
  "longest_consecutive":"actual observed distinct valid harvest years only",
  "sufficient_rice_series":"at least 10 unique QC-passing years within SAME season and crop production system AND a consecutive stretch >= 6 years; this is a planning screen, not econometric power",
  "irrigation_exposure":"MIRCA-OS v2 modeled harvested-area irrigation fraction at 2015 or 2020; never assume observed source outcomes are irrigated only",
  "irrigation_sensitivity":"2020 share >=10%, >=20%, >=50%; >=100 modeled harvested ha",
  "source_validation":"district metadata from GPKG includes not guaranteed scheme footprints; manual scheme overlay required"
 }}
def save():
 (OUT/"rice_series_provenance.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
def download(k):
 p=PROV["inputs"][k];name=pathlib.PurePosixPath(p["url"]).name
 f=TMP/name
 if not f.exists() or f.stat().st_size!=p["size_bytes"]:
  with requests.get(p["url"],stream=True,timeout=(30,180),
                    headers={"User-Agent":"DissertationScienceDataAudit/1.0"}) as r:
   r.raise_for_status()
   with f.open("wb") as w:
    for part in r.iter_content(2**20):
     if part:w.write(part)
 with f.open("rb") as fp:sha=hashlib.file_digest(fp,"sha256").hexdigest()
 assert sha==p["sha256"],f"Official source SHA mismatch {k}: {sha}"
 LOG["inputs"][k]={"url":p["url"],"sha256":sha,"bytes":f.stat().st_size}
 return f
def longest(years):
 a=sorted({int(y) for y in years if pd.notna(y)})
 if not a:return 0
 best=cur=1
 for x,y in zip(a,a[1:]):
  cur=cur+1 if y==x+1 else 1;best=max(best,cur)
 return best
try:
 data=download("harveststat_csv")
 boundaries=download("harveststat_boundaries")
 table=pd.read_csv(data,low_memory=False)
 table["harvest_year"]=pd.to_numeric(table["harvest_year"],errors="coerce")
 for c in ("qc_flag","yield","area","production"):table[c]=pd.to_numeric(table[c],errors="coerce")
 assert "fnid" in table and "product" in table
 rice=table.loc[(table["product"].eq("Rice"))&table.harvest_year.between(1981,2024)].copy()
 rice["good"]=(rice.qc_flag.eq(0)&rice["yield"].gt(0)&rice.area.gt(0)&rice.production.gt(0))
 for c in ["season_name","crop_production_system"]:rice[c]=rice[c].fillna("UNSPECIFIED").astype(str)
 exp=pd.read_csv(EXP)
 exp=exp.loc[exp.crop.eq("Rice")].copy()
 assert not exp.duplicated(["fnid","reference_year"]).any()
 rice=rice.merge(exp.loc[exp.reference_year.eq(2020),["fnid","BCODE","dominant_bcu",
                      "dominant_share","irrigated_ha","crop_total_ha","fraction_irrigated",
                      "ir_positive_cells","grid_centres_inside_district"]].rename(columns={
                       "irrigated_ha":"ir_ha_2020","crop_total_ha":"rice_ha_2020",
                       "fraction_irrigated":"fraction_ir_2020",
                       "ir_positive_cells":"ir_pixels_2020"}),
                on="fnid",how="inner",validate="many_to_one")
 LOG["all_rice_rows_3basins"]=len(rice)
 LOG["qc_passed_rice_rows_3basins"]=int(rice.good.sum())
 LOG["distinct_fnid_with_rice_any_year"]=int(rice.fnid.nunique())
 admin=gpd.read_file(boundaries)
 LOG["boundary_columns"]=list(admin.columns)
 geo=admin.drop(columns="geometry").copy()
 assert geo.fnid.is_unique
 geo=geo.rename(columns={x:"adm_"+x for x in geo.columns if x!="fnid"})
 geo.to_csv(OUT/"admin_boundary_metadata_3basins.csv",index=False)
 
 # FULL KEY UNIQUE? Tag duplicate as invalid rather than forcibly averaging.
 key=["fnid","product","season_name","crop_production_system","harvest_year"]
 duplicated=rice.duplicated(key,keep=False)
 LOG["ambiguous_duplicate_fullkey_rows"]=int(duplicated.sum())
 good=rice.loc[rice.good&~duplicated].copy()
 # segment-specific continuity first
 series=[]
 for k,g in good.groupby(["fnid","season_name","crop_production_system"],dropna=False):
  years=sorted(set(g.harvest_year.astype(int)))
  series.append({"fnid":k[0],"season_name":k[1],"crop_production_system":k[2],
   "valid_years":len(years),"first":min(years),"last":max(years),
   "longest_consecutive":longest(years),
   "pre_2015_years":sum(y<2015 for y in years),
   "post_2015_years":sum(y>2015 for y in years),
   "pre_2020_years":sum(y<2020 for y in years),
   "post_2020_years":sum(y>2020 for y in years),
   "record_years":";".join(map(str,years)),
   "valid>=10_and_consecutive>=6":len(years)>=10 and longest(years)>=6,
   "n_source_rows":len(g)})
 s=pd.DataFrame(series)
 if len(s)==0:raise RuntimeError("No rice segment observations!")
 meta_cols=["fnid","BCODE","dominant_bcu","dominant_share",
            "ir_ha_2020","rice_ha_2020","fraction_ir_2020","ir_pixels_2020","grid_centres_inside_district"]
 s=s.merge(rice[meta_cols].drop_duplicates("fnid"),on="fnid",how="left",validate="many_to_one")
 s=s.merge(geo,on="fnid",how="left",validate="many_to_one")
 s.to_csv(OUT/"rice_district_season_observed_series.csv",index=False)
 
 # Country names cannot be assumed from FNID; official metadata included.
 
 exp2020=exp.loc[exp.reference_year.eq(2020)].copy()
 # all 253 districts, including districts with no Rice in HarvestStat.
 counts=rice.groupby("fnid").agg(rice_raw_rows=("good","size"),rice_qc_valid_rows=("good","sum"),
                                rice_qc_invalid_rows=("good",lambda x:int((~x).sum())),
                                distinct_harvest_years_anyseason=("harvest_year","nunique")).reset_index()
 n=exp2020.merge(counts,on="fnid",how="left",validate="one_to_one")
 n=n.merge(geo,on="fnid",how="left",validate="one_to_one")
 n["rice_raw_rows"]=n.rice_raw_rows.fillna(0).astype(int)
 n["rice_qc_valid_rows"]=n.rice_qc_valid_rows.fillna(0).astype(int)
 n=n.merge(s.groupby("fnid").agg(max_valid_years=("valid_years","max"),
             max_consecutive=("longest_consecutive","max"),
             any_sufficient_series=("valid>=10_and_consecutive>=6","max"),
             best_post_2020_years=("post_2020_years","max")).reset_index(),
             on="fnid",how="left",validate="one_to_one")
 n["any_sufficient_series"]=n.any_sufficient_series.fillna(False)
 n["rice_present_in_HarvestStat"]=n.rice_raw_rows.gt(0)
 n["crop_fraction_defined"]=n.fraction_irrigated.notna()
 n["potential_irrigated_rice_10pct_100ha"]=(
   n.fraction_irrigated.ge(.10)&n.irrigated_ha.ge(100)&n.grid_centres_inside_district.ge(3))
 n["candidate_by_both"]=n.potential_irrigated_rice_10pct_100ha & n.any_sufficient_series
 n=n.sort_values(["BCODE","candidate_by_both","irrigated_ha"],ascending=[True,False,False])
 n.to_csv(OUT/"rice_district_feasibility_screen.csv",index=False)
 LOG["district_rice_screen"]={
  "n_assigned_districts":len(n),
  "with_any_HarvestStat_rice":int(n.rice_present_in_HarvestStat.sum()),
  "with_2020_10pct_ir_100ha":int(n.potential_irrigated_rice_10pct_100ha.sum()),
  "with_sufficient_observed_rice":int(n.any_sufficient_series.sum()),
  "both_irrigated_and_long_series":int(n.candidate_by_both.sum()),
  "combined_candidates_by_basin":{str(k):int(v) for k,v in n.loc[n.candidate_by_both].groupby("BCODE").size().items()},
  "by_basin":{str(k):{"districts":len(g),"sufficient":int(g.any_sufficient_series.sum()),
                      "irrigation_exposed":int(g.potential_irrigated_rice_10pct_100ha.sum()),
                      "both":int(g.candidate_by_both.sum())} for k,g in n.groupby("BCODE")}
 }
 # prior touted 3 examples, source long series and candidate location
 focused=n.loc[n.fnid.isin(KEY_FOCUS)].copy()
 focused.to_csv(OUT/"original_focus_districts_verified.csv",index=False)
 LOG["focus_IDs_found"]=sorted(focused.fnid.tolist())
 LOG["focus_IDs_missing"]=sorted(set(KEY_FOCUS)-set(focused.fnid))
 assert not LOG["focus_IDs_missing"],LOG["focus_IDs_missing"]
 LOG["status"]="COMPLETE"
except Exception as e:
 LOG["status"]="FAILED";LOG["error"]=str(e)[:500];LOG["traceback"]=traceback.format_exc()[-3000:]
finally:
 save()
 print(json.dumps({k:v for k,v in LOG.items() if k not in ("definitions","inputs")},ensure_ascii=False,indent=2))
if LOG["status"]!="COMPLETE":raise SystemExit(1)
