"""Stage 30: pinned Burkina Faso Sourou province rice vs DGRE Yaran water-storage QA.
No intake-specific delivery records, no approved river-flow gauge for field response,
no inferred international treaty effect. All released data are source-scope labeled.
"""
import pathlib,hashlib,datetime,json,sys,traceback,io
import numpy as np,pandas as pd,requests
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"stage30_sourou_di_physical_water";OUT.mkdir(parents=True,exist_ok=True)
URL="https://raw.githubusercontent.com/HarvestStat/HarvestStat-Africa/5b62fb5/public/hvstat_africa_data_v1.2.csv"
SHA="f659e121e315b9d8656699e4b16421ed3b313e4c8d09d15199452000836dbef9"
LEN=25312039
DGRE_2023="https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf"
DGRE_2024_JAN="https://dgre.gov.bf/documents/6/Bulletin_Janvier_2024_Vf.pdf"
MCC="https://www.mathematica.org/-/media/publications/pdfs/international/2021/burkina_faso_adp_final_report.pdf"
L={"run_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"STARTED","qa":{},
"prohibitions":["Yaran is reservoir WATER LEVEL/STORAGE, not seven Di pump flows",
"3 to 4 m3/s is DGRE stated minimum downstream release expectation, not observed daily flow",
"2023 Dec31 vs 2024 Jan1 volume conflict must not be treated as measured release",
"Province Sourou Annual/Plaine-Bas-fond rice is NOT Di-2246ha scheme-specific yield",
"One or two years of reservoir storage difference cannot identify drought exposure or CTGS effect",
"Niassan old perimeters, old pivot Di, new seven-sector MCC Di are not conflated"]}
def chk(k,ok,details=None):
 L["qa"][k]={"pass":bool(ok),"details":details}
 if not ok:raise AssertionError(k+" : "+str(details))
try:
 import os
 cache=pathlib.Path(os.environ.get("RUNNER_TEMP","/tmp"))/"harveststat_sourou_original_v1_2.csv"
 if not cache.exists():
  with requests.get(URL,stream=True,timeout=(30,170),headers={"User-Agent":"HydrologicSourceGateStage30/1.0"}) as r:
   r.raise_for_status()
   with cache.open("wb") as f:
    for c in r.iter_content(2**20):
     if c:f.write(c)
 checksum=hashlib.sha256(cache.read_bytes()).hexdigest()
 chk("pinned_HarvestStat_original_SHA",cache.stat().st_size==LEN and checksum==SHA,
     {"bytes":cache.stat().st_size,"sha":checksum})
 df=pd.read_csv(cache,low_memory=False)
 chk("source_rows",len(df)==217487,len(df))
 sub=df.loc[(df.fnid=="BF2020A24606")&(df.country_code=="BF")&
     df["product"].astype(str).str.contains("rice",case=False,na=False)].copy()
 L["observed_source_rice_systems"]=sub.groupby(["product","season_name","crop_production_system"]).size().to_dict().__repr__()
 irr=sub.loc[(sub.season_name=="Annual")&
      (sub.crop_production_system=="Plaine/Bas-fond irrigated (PS)")].copy()
 irr=irr.sort_values("harvest_year")
 chk("correct_nine_Sourou_BF_province_rice_years",len(irr)==9 and
      set(irr.harvest_year.astype(int))==set(range(2015,2024)),irr[["harvest_year","product"]].to_dict("records"))
 chk("positive_area_production_yield",bool(irr.area.gt(0).all() and irr.production.gt(0).all() and irr["yield"].gt(0).all()))
 err=abs(irr.production/irr.area-irr["yield"])
 chk("source_yield_consistent",bool((err<=np.maximum(1e-9,abs(irr["yield"])*1e-8)).all()),float(err.max()))
 chk("zero_qc_flags_nine",bool((irr.qc_flag==0).all()),irr.qc_flag.tolist())
 arr=irr[["fnid","product","season_name","crop_production_system",
          "planting_year","harvest_year","area","production","yield","qc_flag"]].copy()
 arr["outcome_spatial_support"]="Sourou Province BF2020A24606, not Di or Niassan scheme"
 arr["outcome_agronomic_period"]="Annual Plaine/Bas-fond irrigated broad category; exact actual field irrigation dates unverified"
 arr["observed_at_specific_pumps"]=False
 arr["independent_water_delivery_records_linked"]=False
 arr["source_url"]=URL
 arr.to_csv(OUT/"province_sourou_2015_2023_nine_irrigated_rice_source_verified.csv",index=False)
 # DGRE annual report December 2024 (2023 annual period), printed hydrology pp 46-49, Table 12.
 annual=pd.DataFrame([
  {"year":2022,"storage_01jan_Mm3":511.0,"max_Mm3":884.0,"max_date":"2022-10-02","min_Mm3":105.0,
   "min_date":"2022-06-21","storage_31dec_Mm3":717.0,"spill_days":117,"document_capacity_inferred_from_pct_Mm3":608.0},
  {"year":2023,"storage_01jan_Mm3":717.0,"max_Mm3":726.0,"max_date":"2023-10-02","min_Mm3":143.0,
   "min_date":"2023-06-21","storage_31dec_Mm3":668.0,"spill_days":126,"document_capacity_inferred_from_pct_Mm3":608.0}
 ])
 annual["source_url"]=DGRE_2023
 annual["source_page"]="Hydrologie printed p.49 Table 12"
 annual["variable_type"]="Yaran reservoir STORAGE, not Di pump deliveries"
 annual.to_csv(OUT/"DGRE_Yaran_2022_2023_annual_storage_SOURCE_TRANSCRIPTION.csv",index=False)
 # 2024 January monthly bulletin printed p.24 Table 16.
 jan=pd.DataFrame([
  {"year":2022,"volume_01jan_Mm3":511.462,"volume_31jan_Mm3":393.329,"reported_pct_01jan":84.82,
   "reported_pct_31jan":65.23},
  {"year":2023,"volume_01jan_Mm3":716.566,"volume_31jan_Mm3":631.656,"reported_pct_01jan":118.83,
   "reported_pct_31jan":104.75},
  {"year":2024,"volume_01jan_Mm3":585.339,"volume_31jan_Mm3":450.701,"reported_pct_01jan":97.07,
   "reported_pct_31jan":74.74}])
 jan["jan_storage_delta_Mm3"]=jan.volume_31jan_Mm3-jan.volume_01jan_Mm3
 jan["pct_check_01jan"]=100*jan.volume_01jan_Mm3/603
 jan["pct_check_31jan"]=100*jan.volume_31jan_Mm3/603
 jan["storage_not_release_or_pump"]=True
 jan["source_url"]=DGRE_2024_JAN
 jan["source_page"]="Hydrologie printed p.24 Table 16"
 jan.to_csv(OUT/"DGRE_Yaran_January_2022_2024_storage_SOURCE_TRANSCRIPTION.csv",index=False)
 chk("January_PEN_capacity_percentages_603_consistent",
   bool(np.all(abs(jan.pct_check_01jan-jan.reported_pct_01jan)<0.36) and
        np.all(abs(jan.pct_check_31jan-jan.reported_pct_31jan)<0.36)))
 # Compare the SAME 2022/23 years and following January bulletin without hiding clashes
 a=annual.set_index("year"); j=jan.set_index("year")
 chk("2022_annual_end_to_2023_Jan_start_rounding_agrees",
   abs(a.loc[2022,"storage_31dec_Mm3"]-j.loc[2023,"volume_01jan_Mm3"])<1.0)
 diff=float(j.loc[2024,"volume_01jan_Mm3"]-a.loc[2023,"storage_31dec_Mm3"])
 L["cross_document_2023Dec31_2024Jan1_gap_Mm3"]=diff
 L["cross_document_2023Dec31_2024Jan1_discrepancy_verified"]=abs(diff)>10
 L["capacity_definition_conflict"]={
  "annual_2023_table_pct_implies_Mm3":608.0,
  "monthly_Jan2024_PEN_Mm3":603.0,
  "difference_Mm3":5.0,
  "resolution":"UNRESOLVED, no cross-document percent-of-capacity splice"}
 chk("critical_cross_document_storage_disagreement_flagged",abs(diff)>80 and abs(diff)<83,diff)
 chk("capacity_convention_difference_flagged",608!=603)
 jan["annual_reservoir_storage_Mm3_not_usable_as_irrigation_delivery"]=True
 # Two-point descriptive join ONLY, storage and province outcome incompatible for causal/physical inference.
 compare=arr.loc[arr.harvest_year.isin([2022,2023])].merge(annual,
     left_on="harvest_year",right_on="year",validate="one_to_one")
 chk("2_year_province_storage_join_only",len(compare)==2)
 compare["relationship_verified"]="NONE: same province/year only, no field-to-reservoir operations record"
 compare["causal_estimate_allowed"]=False
 compare["drought_severity_from_this_table"]="NOT CLASSIFIABLE"
 compare.to_csv(OUT/"Sourou_2022_2023_STORAGE_vs_PROVINCE_RICE_NO_FIELD_LINK.csv",index=False)
 L["counts"]={"9_irrigated_province_rice_years":len(irr),"DGRE_annual_years":len(annual),
      "DGRE_Jan_same_month_years":len(jan),"descriptive_overlap_no_scheme_link":len(compare)}
 L["hydraulic_logic"]=[
  "Natural Sourou is affuent-d effluent, Mouhoun flood inflow reversal; 1984 upstream Mouhoun diversion, Lery controlled division",
  "DGRE Yaran 12°58'48.8 N 03°26'49.4 W gauges reservoir levels, not pump extraction",
  "New Di 2246 ha seven electrically powered station sectors (Mathematica), original figures may be sector diagrams only not georeferenced",
  "Di AMVS responsible infrastructure river-to-pumping station; WUA responsible pumps-to-farm valves and water turns",
  "DGRE recommended minimum dry-season Lery downstream release 3-4 m3/s is NOT an observed field delivery or transboundary treaty quota",
  "Official annual 2023 Dec31 storage 668 vs Jan2024 bulletin Jan1 585.339, unresolved cross-report reference conflict"]
 L["status"]="PASS_WITH_CRITICAL_DGRE_CROSS_SOURCE_CONFLICT"
except Exception as ex:
 L["status"]="FAILED";L["error"]=repr(ex);L["traceback"]=traceback.format_exc()[-4200:]
(OUT/"stage30_water_source_drought_outcome_QA.json").write_text(json.dumps(L,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in L.items() if k in ("status","counts","cross_document_2023Dec31_2024Jan1_gap_Mm3","error")},ensure_ascii=False))
sys.exit(0 if L["status"]=="PASS_WITH_CRITICAL_DGRE_CROSS_SOURCE_CONFLICT" else 1)
