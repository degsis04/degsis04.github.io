"""Stage32 source-explicit annual Yaran reservoir STORAGE (not intake flow) 2015-2023.
Each year transcribed from the primary original DGRE PDF's visible printed table.
Critical: 2021 MIN=105 in the contemporaneous 2021 edition, vs conflicting retrospective
2022 edition MIN=117 + a copied 2020 date; preserve both and DO NOT silently reconcile.
"""
import csv,json,math,pathlib,datetime,traceback,sys,hashlib
R=pathlib.Path(__file__).resolve().parents[1]
O=R/"results"/"stage32_sourou_real_hydrology";O.mkdir(exist_ok=True,parents=True)
RICE=R/"results"/"stage30_sourou_di_physical_water"/"province_sourou_2015_2023_nine_irrigated_rice_source_verified.csv"
SRC={
 "2016":"https://dgre.gov.bf/documents/9/Document_synth%C3%A8se_du_suivi_des_ressources_en_eau_de_2016_VF.pdf",
 "2017":"https://dgre.gov.bf/documents/10/Document_synth%C3%A8se_du_suivi_des_ressources_en_eau_de_2017_NMNC_06_02_2019_vf.pdf",
 "2019":"https://dgre.gov.bf/documents/18/Document_ynth%C3%A8se_Ouaga_03_10_2020vf_1.pdf",
 "2021":"https://dgre.gov.bf/documents/19/Synth%C3%A8se_annuelle_ressources_2021.pdf",
 "2022":"https://dgre.gov.bf/documents/20/DOC_SYNT_2022_VF.pdf",
 "2023":"https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf",
 "2024Jan":"https://dgre.gov.bf/documents/6/Bulletin_Janvier_2024_Vf.pdf"}
DATA=[
 # year, Jan 1, max, min, Dec 31, spill days, source report id, printed page, exact table
 (2015,431.58,763.92,64.62,528.43,76,"2016",34,"Table 1.10"),
 (2016,522.79,650.53,99.50,440.35,40,"2016",34,"Table 1.10"),
 (2017,432.00,511.00,111.00,333.00,0,"2017",41,"Table 1.14"),
 (2018,327.00,808.00,64.00,618.00,96,"2019",55,"Table 1-14"),
 (2019,618.00,618.00,127.00,511.00,22,"2019",55,"Table 1-14"),
 (2020,506.00,802.00,117.00,613.00,107,"2021",66,"Table 1-9"),
 (2021,608.00,721.00,105.00,580.00,102,"2021",66,"Table 1-9"),
 (2022,511.00,884.00,105.00,717.00,117,"2023",49,"Table 12"),
 (2023,717.00,726.00,143.00,668.00,126,"2023",49,"Table 12"),
]
LOG={"status":"STARTED","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "data_type":"DGRE table-transcribed reservoir STORAGE, not actual scheme intake Q",
  "checks":{},"sources":SRC,
  "critical_source_conflicts":[
   "Retrospective DGRE 2022 Table 12 reports 2021 min 117 with 2020 minimum date; contemporaneous DGRE 2021 Table 1-9 reports 2021 min 105, dated 21/06/2021",
   "2021 Dec 31 storage 580 vs 2022 Jan 1 storage 511.462 from Jan2024 bulletin, unresolved ~68.5 Mm3 gap",
   "2023 Dec31 storage 668 vs 2024 Jan1 585.339 from Jan2024 bulletin, unresolved ~82.7 Mm3 gap",
   "Yearly stored reservoir volume is NOT Di pump actual m3, no route-based release allocation known",
   "Possible use of varying height-volume curve / storage percentage capacity 608 vs 603 requires independent DGRE records",
   "No institutional treatment and no causal inference permitted with nine province-level matched outcome years"]}
def check(k,condition,details=None):
 LOG["checks"][k]={"pass":bool(condition),"details":details}
 if not condition:raise AssertionError(f"{k}: {details}")
def readcsv(p):
 with p.open(encoding="utf8",newline="") as f:return list(csv.DictReader(f))
def outcsv(filename,rows):
 with (O/filename).open("w",encoding="utf8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
try:
 rice=readcsv(RICE)
 check("nine_province_2015_2023",len(rice)==9 and [int(x["harvest_year"]) for x in rice]==list(range(2015,2024)))
 d=[]
 for y,jan,hi,lo,dec,spill,src,page,table in DATA:
  check("each_year_min_below_max_"+str(y),0<=lo<=hi and jan>=lo and jan<=hi and dec>=lo and dec<=hi)
  check("nonnegative_days_"+str(y),0<=spill<=366)
  d.append({"year":y,"start_01jan_storage_Mm3":jan,
   "annual_max_storage_Mm3":hi,"annual_min_storage_Mm3":lo,
   "end_31dec_storage_Mm3":dec,"spill_days":spill,
   "DGRE_primary_report_year":src,"DGRE_PDF_source":SRC[src],
   "printed_page":page,"printed_table":table,
   "transcription_method":"Original PDF table, manual double-check with screenshot; no image-derived digitization",
   "reservoir_Q_only":False,"scheme_irrigation_delivery_verified":False})
 check("years_unique_and_complete",[x["year"] for x in d]==list(range(2015,2024)))
 outcsv("DGRE_Yaran_2015_2023_nine_annual_first_report_source_tables.csv",d)
 overlaps=[]
 rix={int(x["harvest_year"]):x for x in rice}
 for row in d:
  y=row["year"];r=rix[y]
  overlaps.append({"year":y,"DGRE_min_storage_Mm3":row["annual_min_storage_Mm3"],
  "DGRE_max_storage_Mm3":row["annual_max_storage_Mm3"],
  "DGRE_end_storage_Mm3":row["end_31dec_storage_Mm3"],
  "Sourou_PROVINCE_Rice_area_ha":float(r["area"]),
  "Sourou_PROVINCE_Rice_production_t":float(r["production"]),
  "Sourou_PROVINCE_Rice_yield_t_ha":float(r["yield"]),
  "same_research_support_verified":False,
  "crop_season_specific_storage_exposure_verified":False,
  "Di_scheme_crop_outcome_available":False,
  "causal_institution_coefficient_allowed":False,
  "source_hydrology":row["DGRE_PDF_source"],"source_rice":r["source_url"]})
 outcsv("Yaran_2015_2023_NINE_year_reservoir_vs_province_rice_DESCRIPTIVE_NOT_REGRESSION.csv",overlaps)
 # Approximate temporal discontinuities, not to be attributed to actual one-day releases.
 jumps=[]
 for a,b in zip(d,d[1:]):
  abs_gap=b["start_01jan_storage_Mm3"]-a["end_31dec_storage_Mm3"]
  jumps.append({"boundary":f"{a['year']}-12-31 -> {b['year']}-01-01",
   "year_left":a["year"],"year_right":b["year"],
   "previous_end_Mm3":a["end_31dec_storage_Mm3"],
   "next_start_Mm3":b["start_01jan_storage_Mm3"],
   "reported_difference_Mm3":abs_gap,
   "flag_over_10_Mm3":abs(abs_gap)>10,
   "meaning":"unreconciled cross-source and/or storage-conversion gap, not measured discharge"})
 outcsv("DGRE_Yaran_all_8_2015_2023_report_boundary_quality_flags.csv",jumps)
 check("reported_2021_to_2022_gap_large",jumps[6]["reported_difference_Mm3"]==-69,jumps[6])
 # index of 2021->2022 is 6, correct.
 check("2015_2016_report_internal_gap_over_5",abs(jumps[0]["reported_difference_Mm3"]+5.64)<1e-8)
 check("2017_2018_gap_six",jumps[2]["reported_difference_Mm3"]==-6)
 check("2022_2023_continuity",jumps[7]["reported_difference_Mm3"]==0)
 check("2021_contemporaneous_min",d[6]["annual_min_storage_Mm3"]==105)
 # Explicitly audit the 2022 retrospective year 2021 row; do not replace source value.
 check("2022_retrospective_conflicts_2021_contemporary_min",
   d[6]["annual_min_storage_Mm3"]!=117)
 LOG["retrospective_2022_2021_conflicting_minimum"]={"2021_edition_2021_min_Mm3":105,
  "2022_edition_2021_min_Mm3":117,"possible_2020_row_repeat":True,
  "decision":"USE contemporaneous 2021 report as baseline, retain 117 as an alternate unresolved value"}
 LOG["year_boundary_jumps_over_10"]=[x for x in jumps if x["flag_over_10_Mm3"]]
 LOG["report_scope"]={"source_report_years":[2016,2017,2019,2021,2022,2023],
  "data_years":[x["year"] for x in d],"unmeasured_2015_to_2023_daily_stage_or_pump_flows":True,
  "Sourou_2015_2023_rice_matches_year_label_only":len(overlaps)}
 LOG["status"]="PASS_9YR_SOURCE_TABLES_WITH_CONFLICTS"
except Exception as e:
 LOG["status"]="FAILED";LOG["error"]=repr(e);LOG["trace"]=traceback.format_exc()[-4000:]
(O/"stage32_DGRE_9year_SOURCE_CHECK.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":LOG["status"],"nchecks":len(LOG["checks"]),
 "jumps":LOG.get("year_boundary_jumps_over_10"),"error":LOG.get("error")},ensure_ascii=False)[:3200])
sys.exit(0 if LOG["status"]=="PASS_9YR_SOURCE_TABLES_WITH_CONFLICTS" else 1)
