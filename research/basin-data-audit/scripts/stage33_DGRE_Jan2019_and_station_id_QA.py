"""Stage33 source-based DGRE Jan 2019 Yaran 2017/2018/2019 month table,
plus historic Lanfièra gauge / modern Yaran station identity separation.
No inference of observed pumping, releases, or IPON water allocation.
"""
import pathlib,csv,json,math,datetime,traceback,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
O=ROOT/"results"/"stage33_sourou_di_hydrometric_QA";O.mkdir(exist_ok=True,parents=True)
SRC=ROOT/"results"/"stage32_sourou_real_hydrology"/"DGRE_Yaran_2015_2023_nine_annual_first_report_source_tables.csv"
URL="https://eauburkina.com/images/SNIEau/Janvier_2019.pdf"
REFERENCE_2024="https://dgre.gov.bf/documents/6/Bulletin_Janvier_2024_Vf.pdf"
ATLAS="https://www.altwym.nl/wp-content/uploads/2019/05/atlas_sourou_partie-3_225-dpi-final.pdf"
ANNUAIRE="https://dgre.gov.bf/documents/5/Annuaire_hydrologique_national_20091.pdf"
L={"status":"STARTED","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"checks":[],
   "provenance":{"2019_january_pdf":URL,"2019_table":"Tableau 11, printed page 19; screenshots independently checked",
      "historical_atlas_pdf":ATLAS,"modern_DGRE_annual_pdf":"https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf",
      "2024_jan_bulletin":REFERENCE_2024},
   "conditions":["January 2017/2018/2019 monthly net storage change is NOT water intake or reservoir release",
      "PEN (normal water level) volume 360 in Jan2019 bulletin must not be equated with full reservoir capacity 603 from Jan2024",
      "Lanfièra BFQ4048 coordinate from historic Sourou atlas may identify DIFFERENT gauge, not modern Yaran published station",
      "Hydrological source station matching requires station ID / coordinate / rating curve / regulated regime equivalence",
      "No interpolation, no fabricated daily hydro observations, no causal climate institutional coefficient"]}
def ck(k,b,d=None):
 L["checks"].append({"name":k,"pass":bool(b),"details":d})
 if not b:raise AssertionError(k+" "+str(d))
def writecsv(name,arr):
 with (O/name).open("w",encoding="utf8",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=list(arr[0]));writer.writeheader();writer.writerows(arr)
def haversine(lat1,lon1,lat2,lon2):
 R=6371.0088
 a,b=map(math.radians,(lat1,lat2))
 dp=b-a; dl=math.radians(lon2-lon1)
 return 2*R*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2))
try:
 with SRC.open(encoding="utf8",newline="") as f:d={int(x["year"]):x for x in csv.DictReader(f)}
 ck("all_three_years_present",all(y in d for y in [2017,2018,2019]))
 # DGRE Bulletin hydrologique mensuel January 2019, Table 11, original values in millions m3
 rs=[
  (2017,432,354,119.88,98.20),
  (2018,327,263,90.70,73.13),
  (2019,618,466,171.53,129.44)]
 out=[]
 for year,start,end,pstart,pend in rs:
  ck("annual_jan1_consistent_"+str(year),float(d[year]["start_01jan_storage_Mm3"])==start,d[year])
  fill_start=100*start/360; fill_end=100*end/360
  ck("PEN360_percent_rounding_start_"+str(year),abs(fill_start-pstart)<.21,(fill_start,pstart))
  ck("PEN360_percent_rounding_end_"+str(year),abs(fill_end-pend)<.21,(fill_end,pend))
  out.append({"year":year,"month":"Jan","storage_jan01_Mm3":start,"storage_jan31_Mm3":end,
    "delta_month_Mm3":end-start,"published_percent_jan01":pstart,"published_percent_jan31":pend,
    "PEN_normal_water_reference_Mm3":360,"recomputed_percent_jan01_at_360":round(fill_start,4),
    "recomputed_percent_jan31_at_360":round(fill_end,4),
    "reference_definition":"2019 report plan d'eau normal, NOT 2024 full capacity 603 Mm3",
    "site_claim":"Yaran reservoir / Sourou (not asbuilt Di pumps)",
    "pdf_source":URL,"printed_table":"11","printed_page":"19",
    "monthly_delta_is_observed_pump_or_treaty_release":False})
 writecsv("DGRE_Jan2019_2017_2019_Yaran_monthly_storage_PRIMARY_TABLE.csv",out)
 ck("three_declining_january_storage",all(z["delta_month_Mm3"]<0 for z in out))
 ck("different_reference_volume_2019PEN_vs_2024total",360!=603)
 ck("jan2019_152_Mm3_drop",out[2]["delta_month_Mm3"]==-152)
 # Atlas Sourou 2019 part3 Fig3 historic daily hydro source BFQ4048 at Lanfièra 12.753/-3.433;
 # modern DGRE 2023 hydrometric "Yaran" level 12°58'48.8 N, 03°26'49.4 W.
 old=(12.753,-3.433)
 modern=(12+58/60+48.8/3600,-(3+26/60+49.4/3600))
 distance=haversine(old[0],old[1],modern[0],modern[1])
 site=[
  {"name":"Lanfièra (Yaran-linked historic gauge in Atlas Sourou Part3 Fig3)",
   "station_id":"SIEREM BFQ4048","latitude":old[0],"longitude":old[1],
   "period":"1985-01-01/2007-06-30","variable":"Historic daily river discharge Q m3/s from atlas chart / SIEREM",
   "source":ATLAS,"status":"HISTORIC_SECONDARY_GAUGE_METADATA_ONLY"},
  {"name":"Yaran annual DGRE reservoir-monitoring station",
   "station_id":"IRD 1202702205","latitude":modern[0],"longitude":modern[1],
   "period":"2015-2023 published annual source tables",
   "variable":"Reservoir stage/storage volumes, not scheme intake Q",
   "source":"https://dgre.gov.bf/documents/21/DOC_SYNT_2023_DEIE_vF.pdf",
   "status":"OFFICIAL_COORDINATE_NOT_MATCHED_TO_HISTORIC_GAUGE"}
 ]
 writecsv("Yaran_vs_Lanfiera_two_station_identity_and_distances.csv",
   [{**x,"haversine_distance_between_two_claimed_sites_km":distance,
    "same_station_proven":False,"safe_to_merge_time_series":False} for x in site])
 ck("two_sites_gt20km_apart",20<distance<30,distance)
 L["stations"]={"historical":old,"modern":modern,"separation_km":distance,
                "same_station":"UNVERIFIED","allow_synthetic_1985_2023_series":False}
 L["reproducible_monthly_values"]=out
 L["source_date_scope"]="Three January snapshots ONLY: 2017, 2018, 2019. Not a 2015-2023 daily stream."
 L["status"]="PASS_SOURCE_IDENTITY_AND_MONTHLY_MATH"
except Exception as ex:
 L["status"]="FAILED";L["error"]=repr(ex);L["trace"]=traceback.format_exc()[-3500:]
(O/"stage33_DGRE_2019_Jan_and_station_identity_QA.json").write_text(json.dumps(L,ensure_ascii=False,indent=2,default=str)+"\n")
print(json.dumps({"status":L["status"],"n_checks":len(L["checks"]),"station_distance":L.get("stations",{}).get("separation_km"),
"january":[(x["year"],x["delta_month_Mm3"]) for x in L.get("reproducible_monthly_values",[])],"error":L.get("error")},ensure_ascii=False))
sys.exit(0 if L["status"]=="PASS_SOURCE_IDENTITY_AND_MONTHLY_MATH" else 1)
