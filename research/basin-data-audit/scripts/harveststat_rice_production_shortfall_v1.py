#!/usr/bin/env python3
"""Case-level HarvestStat v1.2 rice yield shortfalls; descriptive, non-causal.
No combination of distinct statistical production systems. Download from pinned release,
verify published source hash, compute trailing 5-calendar-year within-stratum medians.
"""
import csv, hashlib, io, json, math, os, statistics, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("research/basin-data-audit/results/rice_loss_v1")
ROOT.mkdir(parents=True, exist_ok=True)
SOURCE = "https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/5b62fb5/public/hvstat_africa_data_v1.2.csv"
FALLBACK = "https://github.com/HarvestStat/HarvestStat-Africa/releases/download/v1.2/hvstat_africa_data_v1.2.csv"
EXPECTED_SHA256 = "f659e121e315b9d8656699e4b16421ed3b313e4c8d09d15199452000836dbef9"
CASES = {
    "OFFICE_DU_NIGER_SEGOu": "ML2016A104",
    "MALANVILLE": "BJ2015A20705",
    "SOUROU_NIASSAN": "BF2020A24606",
}
WINDOW_YEARS = 5
MIN_BASELINE_N = 3

def download():
    errors=[]
    for url in (SOURCE,FALLBACK):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"research-reproducibility-audit/1.0"})
            with urllib.request.urlopen(req,timeout=90) as h:
                payload=h.read()
            sha=hashlib.sha256(payload).hexdigest()
            if sha!=EXPECTED_SHA256: raise ValueError(f"sha mismatch {sha}, expected {EXPECTED_SHA256}")
            return payload,url,sha
        except Exception as exc:errors.append(f"{url}: {exc}")
    raise RuntimeError("Cannot obtain byte-verified original: "+" | ".join(errors))

def num(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (ValueError,TypeError): return None

def valid(row):
    a=num(row["area"]);p=num(row["production"]);y=num(row["yield"])
    flag=(row.get("qc_flag") or "").strip()
    if flag not in ("0","0.0"):return False,"QC_FLAG_"+flag
    if a is None or p is None or y is None or a<=0 or y<=0 or p<0:return False,"MISSING_OR_NONPOSITIVE"
    if abs(p/a-y)>max(0.015,abs(y)*0.005):return False,"ARITHMETIC_MISMATCH"
    return True,"PASS"

def median_independent(a):
    b=sorted(a);n=len(b);i=n//2
    return b[i] if n%2 else (b[i-1]+b[i])/2

def write_csv(path,rows,fieldnames):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def main():
    payload,source_url,sha=download()
    raw=list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    source_counts=defaultdict(int)
    records=[]
    for r in raw:
        if r.get("fnid") not in CASES.values() or (r.get("product") or "").strip().lower()!="rice":continue
        ok,reason=valid(r)
        try:year=int(r["harvest_year"])
        except (ValueError,KeyError):continue
        case=next(k for k,v in CASES.items() if v==r["fnid"])
        source_counts[case]+=1
        records.append({
            "case":case,"fnid":r["fnid"],"country":r.get("country",""),
            "admin_1":r.get("admin_1",""),"admin_2":r.get("admin_2",""),
            "crop":r["product"],"season_name":r.get("season_name",""),
            "crop_production_system":r.get("crop_production_system",""),
            "harvest_year":year,"qc_flag":r.get("qc_flag",""),"area_ha":num(r["area"]),
            "production_t":num(r["production"]),"yield_t_ha":num(r["yield"]),
            "qc_valid":ok,"qc_reason":reason,
        })
    if set(source_counts)!=set(CASES):raise RuntimeError(f"Missing requested cases in original source: {dict(source_counts)}")

    bystr=defaultdict(list)
    for r in records:
        bystr[(r["case"],r["season_name"],r["crop_production_system"])].append(r)
    key_dup=0;num_checked=0;max_qa_difference=0.0
    for k,rows in bystr.items():
        years=defaultdict(int)
        for r in rows: years[r["harvest_year"]]+=1
        for r in rows:
            if years[r["harvest_year"]]>1:
                r["qc_valid"]=False;r["qc_reason"]="DUPLICATE_STRATUM_YEAR"
                key_dup+=1
        valid_rows=sorted([r for r in rows if r["qc_valid"]],key=lambda r:r["harvest_year"])
        for r in rows:
            yr=r["harvest_year"]
            hist=[v["yield_t_ha"] for v in valid_rows if yr-WINDOW_YEARS<=v["harvest_year"]<yr]
            r.update({"baseline_n":len(hist),"reference_yield_t_ha":None,
                "relative_yield_change_pct":None,"yield_shortfall_pct":None,
                "conditional_production_shortfall_t":None,"reference_production_t":None,
                "production_change_pct":None,"indicator_status":"INVALID_OR_UNAVAILABLE"})
            if not r["qc_valid"]:continue
            if len(hist)<MIN_BASELINE_N:
                r["indicator_status"]="INSUFFICIENT_PREVIOUS_YEARS";continue
            ref=statistics.median(hist)
            independent=median_independent(hist)
            if abs(ref-independent)>1e-12:raise AssertionError("two independent median formulas disagree")
            y=r["yield_t_ha"];area=r["area_ha"]
            change=100*(y/ref-1)
            loss=max(0,-change)
            tons=max(0,(ref-y)*area)
            alt_tons=area*ref*max(0,1-y/ref)
            max_qa_difference=max(max_qa_difference,abs(tons-alt_tons))
            if abs(tons-alt_tons)>max(1e-5,tons*1e-10):raise AssertionError("conditional tonnage duplicate QA failed")
            past_p=[v["production_t"] for v in valid_rows if yr-WINDOW_YEARS<=v["harvest_year"]<yr]
            p_ref=statistics.median(past_p)
            r.update({"baseline_n":len(hist),"reference_yield_t_ha":round(ref,8),
                "relative_yield_change_pct":round(change,6),"yield_shortfall_pct":round(loss,6),
                "conditional_production_shortfall_t":round(tons,5),
                "reference_production_t":round(p_ref,5),
                "production_change_pct":round(100*(r["production_t"]/p_ref-1),6) if p_ref>0 else None,
                "indicator_status":"DESCRIPTIVE_COMPARABLE_STRATUM"})
            num_checked+=1

    records.sort(key=lambda r:(r["case"],r["season_name"],r["crop_production_system"],r["harvest_year"]))
    fields=["case","fnid","country","admin_1","admin_2","crop","season_name",
        "crop_production_system","harvest_year","qc_flag","area_ha","production_t","yield_t_ha",
        "qc_valid","qc_reason","baseline_n","reference_yield_t_ha",
        "relative_yield_change_pct","yield_shortfall_pct","conditional_production_shortfall_t",
        "reference_production_t","production_change_pct","indicator_status"]
    write_csv(ROOT/"rice_descriptive_loss_by_year.csv",records,fields)
    summary=[]
    for k,rr in sorted(bystr.items()):
        good=[x for x in rr if x["qc_valid"]]
        measurable=[x for x in good if x["indicator_status"]=="DESCRIPTIVE_COMPARABLE_STRATUM"]
        yrs=sorted(r["harvest_year"] for r in good)
        qa_bad=[x for x in rr if not x["qc_valid"]]
        summary.append({
           "case":k[0],"fnid":CASES[k[0]],"season":k[1],"system":k[2],
           "n_raw":len(rr),"n_qc_valid":len(good),"n_qc_excluded":len(qa_bad),
           "first_year":min(yrs) if yrs else None,"last_year":max(yrs) if yrs else None,
           "n_baseline_eligible":len(measurable),
           "n_yield_below_reference":sum(x["relative_yield_change_pct"]<0 for x in measurable),
           "mean_yield_shortfall_pct_all_eligible":round(statistics.mean(x["yield_shortfall_pct"] for x in measurable),4) if measurable else None,
           "sum_conditional_gap_t_not_causal":round(sum(x["conditional_production_shortfall_t"] for x in measurable),2) if measurable else None,
           "irrigation_identification":"explicit broad irrigated statistical system; NOT scheme-specific" if "irrigat" in k[2].lower() else "aggregate/unknown; not a scheme-specific irrigated outcome",
           "historical_baseline_interpretation":"rolling median (prior 5 calendar years, >=3); NOT no-shock counterfactual"
        })
    fields_s=list(summary[0].keys())
    write_csv(ROOT/"rice_loss_stratum_summary.csv",summary,fields_s)
    audit={
      "utc_created":datetime.now(timezone.utc).isoformat(),
      "input_url":source_url,"input_sha256":sha,"expected_sha256":EXPECTED_SHA256,
      "input_total_rows":len(raw),"input_selected_rice_rows":len(records),
      "selection":dict(CASES),"case_raw_counts":dict(source_counts),
      "n_strata":len(summary),"n_duplicate_excluded_rows":key_dup,
      "n_indicators_calculated":num_checked,"n_qc_valid":sum(r["qc_valid"] for r in records),
      "reference_definition":"Median of yield for SAME fnid x crop x season_name x production system over prior five CALENDAR harvest years; at least 3 complete QC-valid years.",
      "production_shortfall_definition":"max(0, (rolling historical median yield - current yield)*current observed area). Descriptive conditional benchmark, not actual drought-caused tonnage; not scheme-specific.",
      "qa_two_median_algorithms":"PASS","qa_two_tonnage_algorithms":"PASS",
      "qa_max_tonnage_abs_difference_t":max_qa_difference,
      "not_permitted":"No causal claim for treaty, river low-flow, irrigation water delivery, Di/Niassan, Office du Niger plots or Malanville plot; do not splice production systems or sum annual deficits as losses attributable to drought."
    }
    (ROOT/"rice_loss_qa_provenance.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summary":summary,"qa":audit},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
