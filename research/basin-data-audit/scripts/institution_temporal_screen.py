"""Observed agricultural years around documented institutional events.
NOT a causal impact design, not proof of policy implementation.
Input data from preceding continuity audit and human-verified official document registry.
"""
import json, pathlib, pandas as pd, datetime as dt, traceback, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"crop_continuity"
def longest(seq):
    a=sorted(set(map(int,seq)))
    if not a:return 0
    cur=best=1
    for x,y in zip(a,a[1:]):
        cur=cur+1 if y==x+1 else 1;best=max(best,cur)
    return best
status={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
        "definition":"For each dated documentary event, harvest years < event year are PRE, years > event year POST; event year excluded. 8 pre-years and 5 post-years are a data sufficiency screen only, not causal identification."}
try:
    events=pd.read_csv(ROOT/"institutions"/"verified_document_events_v1.csv",dtype=str).fillna("")
    yr=pd.read_csv(OUT/"bcu_crop_season_year_availability.csv")
    qual=pd.read_csv(OUT/"bcu_crop_season_summary.csv")
    qual=qual.loc[qual["bcu_eligible"].eq(True)]
    keys=["BCODE","Basin_Name","dominant_bcu","country_code","product","season_name","crop_production_system"]
    good=yr.merge(qual[keys],on=keys,how="inner",validate="many_to_one")
    good=good.loc[good.n_districts>=2]
    details=[]
    for r in events.itertuples(index=False):
        basin=str(r.basin_code)
        event_year=int(str(r.event_date)[:4])
        q=good.loc[good.BCODE==basin]
        for key,z in q.groupby(keys):
            years=sorted(set(map(int,z.harvest_year.tolist())))
            before=[y for y in years if y<event_year]
            after=[y for y in years if y>event_year]
            details.append({
              **dict(zip(keys,key)),"event":r.document_or_event,
              "mechanism":r.mechanism,"event_date":r.event_date,
              "date_interpretation":r.date_interpretation,
              "legal_or_org_status":r.legal_or_org_status,
              "implementation_verified":r.implemented_in_practice_verified,
              "n_pre":len(before),"n_post":len(after),
              "longest_pre":longest(before),"longest_post":longest(after),
              "data_pre8_post5":len(before)>=8 and len(after)>=5,
              "first_observed":min(years),"last_observed":max(years),
              "official_source":r.source_url})
    df=pd.DataFrame(details)
    df.to_csv(OUT/"bcu_institution_event_coverage.csv",index=False)
    if len(df):
        out=df.groupby(["BCODE","event","event_date","date_interpretation","mechanism","official_source"],dropna=False).agg(
           bcu_series=("dominant_bcu","size"),
           bcu_with_pre8_post5=("data_pre8_post5","sum"),
           countries_with_evidence=("country_code","nunique"),
           max_pre_years=("n_pre","max"),
           max_post_years=("n_post","max")).reset_index()
        out["is_causal_impact_estimate"]=False
    else:out=pd.DataFrame()
    out.to_csv(OUT/"institution_event_screen.csv",index=False)
    status.update({"status":"COMPLETE","document_events":len(events),
                   "bcu_event_crop_series":len(df),
                   "event_rows_with_sufficient_before_after":int(df.data_pre8_post5.sum()) if len(df) else 0,
                   "institutional_basin_codes":sorted(events.basin_code.unique().tolist()),
                   "IMPORTANT":"Only counts harvest years; implementation, exposure, station quality and parallel trends unverified."})
except Exception as ex:
    status.update({"status":"FAILED","error":repr(ex),"traceback":traceback.format_exc()})
finally:
    (OUT/"institution_event_provenance.json").write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n")
if status["status"]!="COMPLETE":sys.exit(1)
print(json.dumps(status,indent=2))
