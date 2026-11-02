"""Reproducible follow-up: HarvestStat Africa v1.2 season-specific crop continuity.

Input: pinned HarvestStat v1.2 CSV and previously verified TFDD/admin BCU crosswalk.
NO estimated yields, synthetic observations, or spatial allocations are created.
Outputs explicitly distinguish raw crop records, valid rows, district series,
BCU series, and cross-border year overlap.

See official dataset: https://doi.org/10.5061/dryad.vq83bk42w
"""
import csv, datetime as dt, hashlib, json, pathlib, os, platform, traceback, sys
from itertools import combinations
import pandas as pd
import numpy as np
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"crop_continuity"
OUT.mkdir(parents=True, exist_ok=True)
PREV=ROOT/"results"/"harveststat"
INPUT_URL="https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/5b62fb5/public/hvstat_africa_data_v1.2.csv"
INPUT_SHA="f659e121e315b9d8656699e4b16421ed3b313e4c8d09d15199452000836dbef9"
CROPS=("Maize","Sorghum","Rice")
START,END=1981,2024
meta={"started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "source":INPUT_URL,"pinned_sha256":INPUT_SHA,"crops":CROPS,
      "window_inclusive":[START,END],
      "code_version":"crop_continuity_v1",
      "definitions":{
        "valid_row":"qc_flag==0 and yield>0 and area>0 and production>0, non-null harvest year",
        "district_series":"fnid x crop x season_name x crop_production_system; seasons/systems never averaged together",
        "duplicated_year_in_series":"if >1 source row has same fnid/crop/season/system/year, exclude that year from continuity",
        "longest_run":"maximum strictly consecutive run of distinct valid harvest years (no filled missing years)",
        "bcu_eligible":"at least 2 districts with 8+ valid years each AND >=10 harvest years containing >=2 distinct districts in same season/system, longest such stretch >=6 years",
        "basin_eligible":"at least 2 eligible BCU of distinct countries with >=8 overlapping qualifying harvest years for a common crop; based on *year*, season/system may differ between countries",
        "geographic_assignment":"previous audit's single >=80%-area-dominant BCU crosswalk, not irrigated acreage",
        "uncertainties":"qc_flag=0 only means not flagged, not a guarantee of truth; crop seasons are calendar metadata not exact phenology; nonrandom reporting gaps; historical borders; no institutional effectiveness inferred"
      },"status":"STARTED"}
def savej(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf8")
def tab(name,obj):obj.to_csv(OUT/name,index=False)
def consecutive_length(a):
    a=sorted(set(int(x) for x in a if pd.notna(x)))
    if not a:return 0
    best=cur=1
    for i in range(1,len(a)):
        cur=cur+1 if a[i]==a[i-1]+1 else 1
        best=max(best,cur)
    return best
def years_list(grp):return set(grp["harvest_year"].astype(int).tolist())
try:
    cache=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"harveststat_v1_2_pinned.csv"
    if not cache.exists():
        with requests.get(INPUT_URL,stream=True,timeout=(30,180),headers={"User-Agent":"AcademicReproducibleThesisAudit/1.0"}) as res:
            res.raise_for_status()
            with cache.open("wb") as f:
                for chunk in res.iter_content(1024*1024):
                    if chunk:f.write(chunk)
    with cache.open("rb") as f:actual=hashlib.file_digest(f,"sha256").hexdigest()
    assert actual==INPUT_SHA,f"STOP: unexpected source SHA: {actual}"
    raw=pd.read_csv(cache,low_memory=False)
    for col in ("harvest_year","qc_flag","yield","area","production"):
        raw[col]=pd.to_numeric(raw[col],errors="coerce")
    for col in ("season_name","crop_production_system"):
        raw[col]=raw[col].fillna("UNSPECIFIED").astype(str)
    raw["product"]=raw["product"].astype(str)
    selected=raw.loc[raw["product"].isin(CROPS) & raw["harvest_year"].between(START,END,inclusive="both")].copy()
    meta["full_source_rows"]=len(raw)
    meta["selected_crop_and_period_rows"]=len(selected)
    meta["per_crop_raw_counts"]={k:int(v) for k,v in selected.groupby("product").size().items()}
    selected["row_valid"]=(selected["qc_flag"].eq(0)&
             selected["yield"].gt(0)&selected["area"].gt(0)&selected["production"].gt(0)&selected["harvest_year"].notna())
    meta["selected_valid_rows"]=int(selected.row_valid.sum())
    meta["selected_qc_counts"]={str(k):int(v) for k,v in selected.qc_flag.fillna(-999).value_counts().items()}
    # Crosswalk is previously created by geo-overlap restricted within the same country.
    cross=pd.read_csv(PREV/"dominant_bcu_assignment.csv")
    assert not cross.fnid.duplicated().any(),"STOP: nonunique crosswalk fnids"
    cross=cross.loc[cross["dominant_ge_80pct"].eq(True),
                    ["fnid","dominant_bcu","dominant_share","BCODE","Basin_Name"]].copy()
    selected=selected.merge(cross,on="fnid",how="left",validate="many_to_one")
    meta["selected_valid_with_ge80_bcu"]=int((selected.row_valid&selected.dominant_bcu.notna()).sum())
    # Temporal uniqueness within EXACT crop × season × production system.
    strata=["fnid","country_code","dominant_bcu","BCODE","Basin_Name","product","season_name","crop_production_system"]
    yearcols=strata+["harvest_year"]
    eligible_rows=selected[selected.row_valid & selected.dominant_bcu.notna()].copy()
    dup=eligible_rows.groupby(yearcols,dropna=False).size().rename("n_rows").reset_index()
    meta["ambiguous_duplicate_series_year_keys"]=int((dup.n_rows>1).sum())
    meta["ambiguous_duplicate_rows"]=int(dup.loc[dup.n_rows>1,"n_rows"].sum())
    eligible_rows=eligible_rows.merge(dup,on=yearcols,how="left",validate="many_to_one")
    eligible_rows=eligible_rows.loc[eligible_rows.n_rows.eq(1)].copy()
    group=eligible_rows.groupby(strata,dropna=False,sort=False)
    distr=group.agg(valid_years=("harvest_year","nunique"),
                    first_year=("harvest_year","min"),last_year=("harvest_year","max")).reset_index()
    length=group["harvest_year"].apply(consecutive_length).rename("longest_consecutive").reset_index()
    distr=distr.merge(length,on=strata,how="left",validate="one_to_one")
    distr["span_coverage"]=distr.valid_years/(distr.last_year-distr.first_year+1)
    distr["district_qualified"]=(distr.valid_years>=8)&(distr.longest_consecutive>=5)
    tab("district_crop_season_series.csv",distr.sort_values(["BCODE","dominant_bcu","product","fnid"]))
    meta["district_crop_season_series"]=len(distr)
    meta["qualified_district_crop_season_series"]=int(distr.district_qualified.sum())
    # Count distinct districts with valid rows in a fixed crop, season, system, year.
    bgroup=["BCODE","Basin_Name","dominant_bcu","country_code","product","season_name","crop_production_system"]
    byyear=bgroup+["harvest_year"]
    yr=eligible_rows.groupby(byyear,dropna=False).agg(n_districts=("fnid","nunique"),
                 n_records=("fnid","size")).reset_index()
    yr["at_least_two_districts"]=yr.n_districts>=2
    tab("bcu_crop_season_year_availability.csv",yr.sort_values(byyear))
    # BCU-specific highest density within a stable season/system.
    distqualified=distr.loc[distr.district_qualified].groupby(bgroup).agg(
         n_qualified_districts=("fnid","nunique")).reset_index()
    summaries=[]
    for key,g in yr.groupby(bgroup,dropna=False):
        yy=sorted(int(x) for x in g.harvest_year)
        yy2=sorted(int(x) for x in g.loc[g.at_least_two_districts,"harvest_year"])
        summaries.append(dict(zip(bgroup,key),n_years_any=len(yy),
                              n_years_two_districts=len(yy2),
                              longest_any=consecutive_length(yy),
                              longest_two_districts=consecutive_length(yy2),
                              start_year=min(yy),end_year=max(yy),
                              distinct_districts_max=int(g.n_districts.max()),
                              coverage_span=len(yy)/(max(yy)-min(yy)+1)))
    summary=pd.DataFrame(summaries)
    summary=summary.merge(distqualified,on=bgroup,how="left",validate="one_to_one")
    summary["n_qualified_districts"]=summary.n_qualified_districts.fillna(0).astype(int)
    summary["bcu_eligible"]=((summary.n_qualified_districts>=2)&
       (summary.n_years_two_districts>=10)&
       (summary.longest_two_districts>=6))
    tab("bcu_crop_season_summary.csv",summary.sort_values(["BCODE","dominant_bcu","product","season_name"]))
    meta["bcu_crop_season_series"]=len(summary)
    meta["eligible_bcu_crop_season_series"]=int(summary.bcu_eligible.sum())
    meta["eligible_distinct_bcu"]=int(summary.loc[summary.bcu_eligible,"dominant_bcu"].nunique())
    # Aggregate eligible year sets across candidate series within BCU,crop; never average yield.
    eligible_set=summary.loc[summary.bcu_eligible,bgroup].copy()
    joined=yr.merge(eligible_set,on=bgroup,how="inner",validate="many_to_one")
    joined=joined.loc[joined.at_least_two_districts]
    # For cross-border panel, crop-year can be comparable, harvest season still needs checks.
    grouped=joined.groupby(["BCODE","Basin_Name","dominant_bcu","country_code","product"],dropna=False)
    index={}
    for key,g in grouped:
        index[key] = set(int(x) for x in g.harvest_year)
    pairs=[]
    for (basin,crop),sub in pd.DataFrame([dict(BCODE=k[0],product=k[4],BCCODE=k[2],CCODE=k[3]) for k in index]).groupby(["BCODE","product"]):
        rows=sub.to_dict("records")
        for a,b in combinations(rows,2):
            if a["CCODE"]==b["CCODE"]:continue
            ka=next(k for k in index if k[0]==basin and k[2]==a["BCCODE"] and k[4]==crop)
            kb=next(k for k in index if k[0]==basin and k[2]==b["BCCODE"] and k[4]==crop)
            common=sorted(index[ka]&index[kb])
            pairs.append({"BCODE":basin,"product":crop,"bcu_a":a["BCCODE"],"bcu_b":b["BCCODE"],
                          "country_a":a["CCODE"],"country_b":b["CCODE"],
                          "common_years":len(common),"longest_common_run":consecutive_length(common),
                          "first_common_year":common[0] if common else None,
                          "last_common_year":common[-1] if common else None,
                          "cross_country_pair_eligible":len(common)>=8 and consecutive_length(common)>=5})
    pairdf=pd.DataFrame(pairs,columns=["BCODE","product","bcu_a","bcu_b","country_a","country_b",
                       "common_years","longest_common_run","first_common_year","last_common_year","cross_country_pair_eligible"])
    tab("basin_crossborder_crop_year_pairs.csv",pairdf.sort_values(["BCODE","product","common_years"],ascending=[True,True,False]))
    # Summary per basin incl data-rich non-eligible for transparent screening.
    basins=[]
    for basin,subset in summary.groupby("BCODE"):
        eligible=subset.loc[subset.bcu_eligible]
        ps=pairdf.loc[pairdf.BCODE==basin] if len(pairdf) else pairdf
        cross=ps.loc[ps.cross_country_pair_eligible] if len(ps) else ps
        basins.append({"BCODE":basin,"Basin_Name":subset.Basin_Name.iloc[0],
             "n_bcu_any":int(subset.dominant_bcu.nunique()),
             "n_countries_any":int(subset.country_code.nunique()),
             "n_bcu_eligible":int(eligible.dominant_bcu.nunique()),
             "n_countries_eligible":int(eligible.country_code.nunique()),
             "n_eligible_bcu_crop_seasons":len(eligible),
             "eligible_crops":";".join(sorted(eligible["product"].unique())),
             "cross_country_comparable_pairs":len(cross),
             "max_crossborder_common_years":int(ps.common_years.max()) if len(ps) else 0,
             "max_crossborder_consecutive_years":int(ps.longest_common_run.max()) if len(ps) else 0,
             "cross_country_minimum_data_met":len(cross)>0,
             "suggested_role":("crossborder-panel-candidate" if len(cross)>0 else
                              "single-country-or-case-study-candidate" if len(eligible)>0 else
                              "data-sparse-exclude-from-main-panel")})
    bs=pd.DataFrame(basins).sort_values(["cross_country_minimum_data_met","n_bcu_eligible","max_crossborder_common_years"],
                                      ascending=[False,False,False])
    tab("basin_screening.csv",bs)
    meta["basin_screen"]={"basins_with_any_3crop_data":len(bs),
                         "basins_with_eligible_bcu":int((bs.n_bcu_eligible>0).sum()),
                         "cross_country_basins_meeting_strict_panel_criterion":int(bs.cross_country_minimum_data_met.sum()),
                         "basins_with_strict_crossborder_panel":bs.loc[bs.cross_country_minimum_data_met,"BCODE"].tolist()}
    meta["status"]="COMPLETE"
except Exception as ex:
    meta["status"]="FAILED";meta["exception"]=repr(ex);meta["traceback"]=traceback.format_exc()
finally:
    savej("continuity_provenance.json",meta)
print(json.dumps({k:v for k,v in meta.items() if k not in ["source","definitions"]},indent=2,default=str))
if meta["status"]!="COMPLETE":sys.exit(1)
