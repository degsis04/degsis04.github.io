"""Decision-gate re-audit of previously downloaded real HarvestStat/TFDD crop-year tables.
No new observations and no 'significant effect' claims. Produces explicit
basin-crop-production-system-season eligibility; conservatively records
non-verified institutional implementation and season comparability.
"""
from __future__ import annotations
import datetime as dt
import itertools
import json
import pathlib
import traceback
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUT = ROOT / "results" / "crop_continuity"
OUT = ROOT / "results" / "design_gate_v1"
OUT.mkdir(parents=True, exist_ok=True)
LOG = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
       "status": "STARTED", "source": "HarvestStat Africa v1.2 + TFDD 2024 prior QA outputs",
       "assumptions": {"minimum_years_with_two_districts": 10,
                       "minimum_longest_consecutive": 6,
                       "minimum_qualified_districts": 2,
                       "maximum_gap_fraction_within_first_last_covered_year": .30,
                       "common_cross_country_calendar_years": 8,
                       "common_cross_country_longest_run": 5,
                       "class_label_same_not_physically_validated": True,
                       "implementation_not_checked_is_UNKNOWN_not_ZERO": True},
       "warnings": []}

def writejson(path, obj):
    (OUT / path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

def longest(seq):
    years = sorted(set(int(x) for x in seq if pd.notna(x)))
    if not years:
        return 0
    best = current = 1
    for a, b in zip(years, years[1:]):
        current = current + 1 if b == a + 1 else 1
        best = max(best, current)
    return best

def ps_class(v):
    s = str(v).lower()
    if "rainfed" in s or "rain-fed" in s or "pluvial" in s:
        return "explicit_rainfed"
    if "irrigat" in s:
        return "explicit_irrigated_broad"
    if s in ("all (ps)", "all", "all (ps and rf)"):
        return "all_production_systems"
    if s in ("none", "unspecified", "nan", ""):
        return "unclassified"
    return "other_requires_review"

try:
    s = pd.read_csv(INPUT / "bcu_crop_season_summary.csv")
    y = pd.read_csv(INPUT / "bcu_crop_season_year_availability.csv")
    inst = pd.read_csv(ROOT / "institutions" / "verified_document_events_v1.csv")
    keys = ["BCODE", "Basin_Name", "dominant_bcu", "country_code",
            "product", "season_name", "crop_production_system"]
    assert not s.duplicated(keys).any(), "One BCU-season-system stratum has duplicate summary"
    assert not y.duplicated(keys+["harvest_year"]).any(), "Duplicated BCU-season-system-year"
    assert set(y.product.unique()) == {"Maize", "Rice", "Sorghum"}
    assert (y.n_records >= y.n_districts).all()
    assert not y.duplicated(keys+["harvest_year"]).any()
    assert s.dominant_bcu.nunique() >= 40

    s["production_class"] = s.crop_production_system.map(ps_class)
    years_by_key = {}
    v = y.loc[y.n_districts >= 2]
    for k, grp in v.groupby(keys, dropna=False, sort=False):
        years_by_key[k] = sorted(grp.harvest_year.astype(int).unique().tolist())
    checks = []
    for row in s.itertuples(index=False):
        key = tuple(getattr(row, c) for c in keys)
        yr = years_by_key.get(key, [])
        span = yr[-1] - yr[0] + 1 if yr else None
        gaps = (1.0 - len(yr) / span) if span else None
        checks.append((len(yr), longest(yr), yr[0] if yr else None,
                       yr[-1] if yr else None, gaps))
    aux = pd.DataFrame(checks, columns=["verified_two_district_years",
                                       "verified_longest_run",
                                       "first_year_2districts", "last_year_2districts",
                                       "fraction_missing_between_first_last_2districts"])
    s = pd.concat([s.reset_index(drop=True), aux], axis=1)
    assert (s.verified_two_district_years == s.n_years_two_districts).all()
    assert (s.verified_longest_run == s.longest_two_districts).all()
    s["statistical_screen_pass"] = (
        s.verified_two_district_years.ge(10) &
        s.verified_longest_run.ge(6) &
        s.n_qualified_districts.ge(2) &
        s.fraction_missing_between_first_last_2districts.le(.30))
    s["crop_calendar_cross_country_verified"] = False
    s["institutional_regime_implemented_verified"] = False
    s["suitable_for_causal_treaty_claim"] = False
    s["main_limitations"] = (
        "Crop-season definition not harmonized across countries; "
        "irrigation-system source & treaty implementation unverified.")
    s.sort_values(["BCODE","country_code","product","season_name"]).to_csv(
        OUT / "strict_stratum_eligibility.csv", index=False)

    base = s.loc[s.statistical_screen_pass].copy()
    matches = []
    for (basin, crop), group in base.groupby(["BCODE", "product"]):
        for aa, bb in itertools.combinations(group.itertuples(index=False), 2):
            if aa.country_code == bb.country_code:
                continue
            k1 = tuple(getattr(aa, c) for c in keys)
            k2 = tuple(getattr(bb, c) for c in keys)
            common = sorted(set(years_by_key[k1]) & set(years_by_key[k2]))
            exact_ps = aa.crop_production_system == bb.crop_production_system
            same_class = aa.production_class == bb.production_class
            known_class = aa.production_class not in ("unclassified","other_requires_review")
            same_season_label = str(aa.season_name).casefold() == str(bb.season_name).casefold()
            matches.append({
                "BCODE":basin, "product":crop,
                "country_a":aa.country_code, "country_b":bb.country_code,
                "bcu_a":aa.dominant_bcu, "bcu_b":bb.dominant_bcu,
                "season_a":aa.season_name, "season_b":bb.season_name,
                "system_a":aa.crop_production_system, "system_b":bb.crop_production_system,
                "class_a":aa.production_class,"class_b":bb.production_class,
                "same_production_class_known":same_class and known_class,
                "exact_production_label":exact_ps,
                "same_season_label_unvalidated":same_season_label,
                "overlapping_harvest_years":len(common),
                "longest_overlapping_harvest_run":longest(common),
                "calendar_pair_screen":len(common)>=8 and longest(common)>=5,
                "stronger_label_match_candidate":(len(common)>=8 and longest(common)>=5
                   and same_class and known_class and same_season_label),
                "physically_equivalent_crop_seasons_verified": False,
                "treaty_effect_identified": False,
                "note":"Identical season labels not independently validated for planting/harvesting months."})
    pairdf = pd.DataFrame(matches)
    pairdf.to_csv(OUT / "cross_country_system_year_pairs.csv",index=False)

    basinrows = []
    for (basin,name),g in s.groupby(["BCODE","Basin_Name"]):
        good = g.loc[g.statistical_screen_pass]
        pairs = pairdf.loc[pairdf.BCODE.eq(basin)] if len(pairdf) else pairdf
        basinrows.append({
            "basin_code":basin, "basin_name":name,
            "observed_bcu":g.dominant_bcu.nunique(),
            "observed_countries":g.country_code.nunique(),
            "strict_strata":len(good),
            "strict_bcu":good.dominant_bcu.nunique(),
            "strict_countries":good.country_code.nunique(),
            "strict_maize_strata":int(good.product.eq("Maize").sum()),
            "strict_sorghum_strata":int(good.product.eq("Sorghum").sum()),
            "strict_rice_strata":int(good.product.eq("Rice").sum()),
            "cross_country_calendar_pairs":int(pairs.calendar_pair_screen.sum()) if len(pairs) else 0,
            "cross_country_same_label_pairs_UNVALIDATED":int(pairs.stronger_label_match_candidate.sum()) if len(pairs) else 0,
            "implemented_treaty_mechanism_verifications":0,
            "physical_hydrologic_linkage_verified":False,
            "eligible_for_causal_model":False})
    bdf = pd.DataFrame(basinrows).sort_values(
        ["strict_countries","strict_bcu","strict_strata"],ascending=False)
    bdf.to_csv(OUT / "basin_gate_dashboard.csv", index=False)

    i = inst.copy()
    i["implementation_status_reinterpreted"] = np.where(
        i.implemented_in_practice_verified.astype(str).str.lower().eq("yes"),
        "IMPLEMENTATION_REPORTED_VERIFY_SOURCE",
        "UNKNOWN_NOT_CHECKED")
    i["legally_active_before_shock_verified"] = False
    i["treatment_time_eligible"] = False
    i.to_csv(OUT / "existing_institution_events_coding_risk.csv", index=False)
    implementation_verified = int(i.implemented_in_practice_verified.astype(str).str.lower().eq("yes").sum())

    croplist = {}
    for name,g in base.groupby("product"):
        croplist[name] = {"strata":len(g),"bcu":g.dominant_bcu.nunique(),
                          "basins":g.BCODE.nunique(),"countries":g.country_code.nunique(),
                          "production_system_classes":g.production_class.value_counts().to_dict()}
    LOG["counts"] = {
        "source_strata":len(s),
        "source_bcu":int(s.dominant_bcu.nunique()),
        "source_basins":int(s.BCODE.nunique()),
        "strict_strata_meeting_data_only_screen":len(base),
        "strict_bcu":int(base.dominant_bcu.nunique()),
        "strict_basins":int(base.BCODE.nunique()),
        "strict_countries":int(base.country_code.nunique()),
        "strata_by_crop":croplist,
        "candidate_pairs_calendar_year_only":int(pairdf.calendar_pair_screen.sum()) if len(pairdf) else 0,
        "candidate_basins_calendar_year_only":int(pairdf.loc[pairdf.calendar_pair_screen,"BCODE"].nunique()) if len(pairdf) else 0,
        "pairs_with_same_known_production_class_and_season_name_not_physical_season":int(pairdf.stronger_label_match_candidate.sum()) if len(pairdf) else 0,
        "basins_same_known_class_and_label":int(pairdf.loc[pairdf.stronger_label_match_candidate,"BCODE"].nunique()) if len(pairdf) else 0,
        "documentary_events_in_existing_register":len(i),
        "implementation_verified_events":implementation_verified}
    LOG["gates"] = {
        "G0_read_and_recompute_source_years": "PASS",
        "G1_crop_panel_numeric_screen": "PARTIAL: reported counts; season/country equivalence NOT verified",
        "G2_confirmed_active_institution_rule_for_model": "BLOCKED: 0 verified implementation records in existing dataset",
        "G3_water_intake_to_upstream_catchment_to_station": "BLOCKED: only descriptive water-source documents, no full geocoded chain",
        "G4_causal_event_study_identification": "NOT APPROVED: no validated reform/control/comparable outcome",
        "G5_asian_replication": "DEFERRED"}
    LOG["status"]="COMPLETE"
    LOG["warnings"]=[
        "This stricter missingness rule is an exploratory screening threshold, NOT a universal power criterion.",
        "Country-level equivalence of crop seasons unverified even where labels match.",
        "No number of district-year observations translates into independent institution regimes.",
        "Unknown implementation from the existing registry is UNKNOWN, not verified absence.",
        "No source produces actual hydrometric observations at irrigation intakes here."]
except Exception as ex:
    LOG["status"]="FAILED";LOG["exception"]=repr(ex)
    LOG["traceback"]=traceback.format_exc()
finally:
    writejson("gate_reaudit_provenance.json",LOG)
print(json.dumps({"status":LOG["status"],"counts":LOG.get("counts"),
                  "gates":LOG.get("gates"),"exception":LOG.get("exception")},ensure_ascii=False,indent=2))
if LOG["status"]!="COMPLETE":
    sys.exit(1)
