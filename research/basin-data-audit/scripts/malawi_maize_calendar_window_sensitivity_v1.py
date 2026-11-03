"""PRE-REGISTERED (for this comparison) seasonal-rainfall window sensitivity.
Study unit: 26 HarvestStat-admin Malawi districts with JRC maize calendar,
1981–2024 harvest years.

Original reference: JRC sow_start->harvest_end ("broad"), and sow_end->harvest_start ("core").
Alternatives: Waha LSMS crop-sample modal planting month -> mode of beginning of harvest
("Waha modal broad"), or previous month ("Waha modal growth").

All time windows restandardized (1981–2010), and climate years anchored
to HARVEST YEAR. Original outcomes unchanged. No regression or institutional
effect estimated, no selection based on outcome association.

JRC is period-static; Waha mode is estimated from 2009–2019 surveys and
projected BACK to 1981 solely as a sensitivity scenario, not observed history.
"""
import datetime as dt,json,pathlib,traceback,sys,math
import numpy as np,pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1"
OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/"results"
REPORT={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "source":{
  "JRC_region_calendar":"results/phenology_v1/district_JRC_external_cropping_seasons.csv",
  "Waha_field_month_aggregates":"results/field_phenology_v1/waha_admin1_crop_month_distribution_anonymized.csv",
  "CHIRPS_final_1981_2024":"results/climate_panel/district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
  "JRC_existing_calculated_seasons":"results/seasonal_climate_v1/JRC_crop_season_CHIRPS_1981_2024.csv",
  "provisional_HarvestStat_outcome":"results/season_outcome_crosswalk_v1/EXPLORATORY_not_causal_HarvestStat_x_JRC_x_CHIRPS_yield_weather.csv"},
 "design":{
  "selected_country":"Malawi",
  "selected_crop":"Maize",
  "regions":"Central, Northern, Southern (all source-supported)",
  "unit":"district x hypothetical reference window x harvest year",
  "baseline_years":"1981-2010 inclusive, >=25 valid baseline years",
  "climatology_sd_min_mm":5,
  "shock_threshold_z":-1,
  "year_alignment":"if mode sow month > mode first-harvest month, sowing is year-1; harvest is year",
  "survey_window":"modal months aggregated at admin1 (not field-level date, not annual historical calendar)",
  "outcome_selection":"NO optimization; weather comparisons do not use yield",
  "two_original_windows":"JRC broad sow_begin..harvest_end; JRC core sow_end..harvest_begin",
  "two_alternatives":"Waha broad modal sowing..modal harvest_begin; Waha growth modal sowing..month before modal harvest_begin"},
 "cautions":[
  "Comparing JRC HARVEST END to Waha harvest BEGIN causes different event definitions; this is calendar sensitivity not validation truth.",
  "Waha aggregated 2009-2019 mode is retrospectively imposed on 1981-2024 only as scenario.",
  "Standardizing separately per window avoids comparing raw totals with unequal exposure months, but obscures different seasonal means.",
  "Mixed irrigation and rainfed outcome categories not reclassified.",
  "Area-averaged district rainfall != irrigated field root-zone water != river discharge or treaty effect.",
  "Even a large change in z does not imply one calendar is scientifically correct.",
  "Baseline climatology may include 1981-2010 with first year unavailable for crossing year - do not impute 1980.",
  "A drought-year discrepancy is not an error rate: neither window is ground truth."],
 "checks":{},"errors":[]}
def check(name,passed,extra=None):
 REPORT["checks"][name]={"pass":bool(passed),"details":extra}
 if not passed:REPORT["errors"].append(name)
def save():
 (OUT/"malawi_maize_calendar_sensitivity_qa.json").write_text(
  json.dumps(REPORT,indent=2,ensure_ascii=False,default=str,allow_nan=False)+"\n")
def step_ym(year,month,inc=1):
 n=(year*12+(month-1))+inc
 return n//12,n%12+1
def month_range(first_year,first_month,last_year,last_month):
 s=[];y,m=first_year,first_month
 while (y,m)<=(last_year,last_month):
  s.append((y,m));y,m=step_ym(y,m)
  assert len(s)<=12,("unexpected length",first_year,first_month,last_year,last_month)
 return s
def waha_months(plant,harvest,hy,mode):
 p,h=int(plant),int(harvest)
 assert 1<=p<=12 and 1<=h<=12 and p!=h,(p,h)
 start_y=hy-int(p>h)
 if mode=="waha_broad":
  end_y,end_m=hy,h
 elif mode=="waha_growth":
  end_y,end_m=step_ym(hy,h,-1)
 else:raise ValueError(mode)
 window=month_range(start_y,p,end_y,end_m)
 assert 1<=len(window)<=12
 return window
try:
 # UNIT TESTS known specific cases - independent of source records
 assert waha_months(11,4,2020,"waha_broad")==[(2019,11),(2019,12),(2020,1),(2020,2),(2020,3),(2020,4)]
 assert waha_months(11,4,2020,"waha_growth")==[(2019,11),(2019,12),(2020,1),(2020,2),(2020,3)]
 assert waha_months(12,5,2020,"waha_growth")==[(2019,12),(2020,1),(2020,2),(2020,3),(2020,4)]
 assert waha_months(6,10,2020,"waha_growth")==[(2020,6),(2020,7),(2020,8),(2020,9)]
 assert waha_months(11,4,1981,"waha_broad")[0][0]==1980
 
 jrc=pd.read_csv(BASE/"phenology_v1"/"district_JRC_external_cropping_seasons.csv")
 f=pd.read_csv(BASE/"field_phenology_v1"/"waha_admin1_crop_month_distribution_anonymized.csv")
 clim=pd.read_csv(BASE/"climate_panel"/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
  usecols=["fnid","year","month","rainfall_mm_month","valid_grid_cell_centres"])
 old=pd.read_csv(BASE/"seasonal_climate_v1"/"JRC_crop_season_CHIRPS_1981_2024.csv",
  usecols=["fnid","BCODE","country_code","jrc_crop_season","window","harvest_year",
           "calendar_months_included","precip_total_mm","seasonal_precip_z","window_data_status"])
 
 jrc=jrc.loc[jrc.country_code.eq("MW")&jrc.crop.eq("Maize")].copy()
 check("malawi_maize_26_districts",jrc.fnid.nunique()==26,{"districts":jrc.fnid.nunique(),"calendar_rows":len(jrc)})
 check("one_calendar_per_district_maize",not jrc.duplicated("fnid").any())
 check("only_Zambezi_basin_for_pilot",jrc.BCODE.eq("ZAMB").all(),jrc.BCODE.value_counts().to_dict())
 regions={"Central Region":"central","Northern Region":"northern","Southern Region":"southern"}
 meta=[]
 for r in jrc.itertuples(index=False):
  z=f.loc[f.country.eq("Malawi")&f.crop.eq("Maize")&f.adm1_normalized.eq(regions[r.name1_shr])]
  if len(z)!=1:raise ValueError(f"Missing Waha regional maize: {r.name1_shr}: {len(z)}")
  v=z.iloc[0]
  meta.append({"fnid":r.fnid,"BCODE":r.BCODE,"country_code":r.country_code,
     "jrc_crop_season":r.crop_name,"jrc_region":r.name1_shr,
     "survey_adm1":v.adm1_name,"Waha_n_maize_records_region":v.n_source_field_records,
     "Waha_n_valid_plant_month_region":v.n_valid_plant_month,
     "Waha_n_valid_harvest_month_region":v.n_valid_harvest_month,
     "Waha_modal_sow_month":int(v.plant_modal_month),
     "Waha_modal_harvest_begin_month":int(v.harvest_modal_month),
     "JRC_sow_start_dekad":r.sos_s,"JRC_sow_end_dekad":r.sos_e,
     "JRC_harvest_start_dekad":r.eos_s,"JRC_harvest_end_dekad":r.eos_e})
 info=pd.DataFrame(meta)
 info.to_csv(OUT/"malawi_maize_26_district_fixed_calendar_scenarios.csv",index=False)
 rain={(r.fnid,int(r.year),int(r.month)):(float(r.rainfall_mm_month),int(r.valid_grid_cell_centres))
        for r in clim.itertuples(index=False)}
 check("original_source_rain_panel_253x528",len(clim)==133584,len(clim))
 check("original_source_rain_monthly_unique",not clim.duplicated(["fnid","year","month"]).any())
 check("distinct_source_regions_three",info.jrc_region.nunique()==3,info.jrc_region.value_counts().to_dict())
 
 rows=[]
 for r in info.itertuples(index=False):
  for hy in range(1981,2025):
   for variant in ("waha_broad","waha_growth"):
    months=waha_months(r.Waha_modal_sow_month,r.Waha_modal_harvest_begin_month,hy,variant)
    arr=[];missing=[];pixel_support=[]
    for yy,mm in months:
     x=rain.get((r.fnid,yy,mm))
     if x is None or not np.isfinite(x[0]) or x[1]<3:missing.append((yy,mm))
     else:arr.append(x[0]);pixel_support.append(x[1])
    rows.append({"fnid":r.fnid,"BCODE":r.BCODE,"country_code":"MW",
        "jrc_crop_season":r.jrc_crop_season,"jrc_region":r.jrc_region,
        "harvest_year":hy,"window":variant,
        "from_year":months[0][0],"from_month":months[0][1],
        "to_year":months[-1][0],"to_month":months[-1][1],
        "months_in_window":len(months),
        "calendar_months_included":";".join(f"{y}-{m:02d}" for y,m in months),
        "precip_total_mm":float(sum(arr)) if not missing else np.nan,
        "status":"COMPLETE" if not missing else "SOURCE_MONTH_MISSING_OR_LOW_SUPPORT",
        "missing_n_months":len(missing)})
 alt=pd.DataFrame(rows)
 chkkeys=["fnid","harvest_year","window"]
 check("alternative_unique_district_year_window",not alt.duplicated(chkkeys).any())
 check("alternative_expected_26x44x2",len(alt)==26*44*2,len(alt))
 old=old.loc[old.fnid.isin(info.fnid)&old.window.isin(["broad","core"])].copy()
 check("old_reference_26x44x2",len(old)==26*44*2,len(old))
 old=old.rename(columns={"window_data_status":"status"})
 # Verify each existing JRC total by re-summing original independent source months
 mismatches=[]
 for r in old.itertuples(index=False):
  stamps=[(int(s[:4]),int(s[5:7])) for s in str(r.calendar_months_included).split(";")]
  vals=[rain.get((r.fnid,yy,mm)) for yy,mm in stamps]
  if all(v is not None and np.isfinite(v[0]) and v[1]>=3 for v in vals):
   p=sum(v[0] for v in vals)
   if not np.isfinite(r.precip_total_mm) or abs(p-r.precip_total_mm)>1e-7:
    mismatches.append({"fnid":r.fnid,"year":r.harvest_year,"window":r.window,"source_recalc":p,
      "previously_stored":r.precip_total_mm})
  else:
   if np.isfinite(r.precip_total_mm):mismatches.append({"fnid":r.fnid,"year":r.harvest_year,
                "window":r.window,"reason":"Saved non-missing despite unsupported source month"})
 check("independently_recompute_all_existing_JRC_rain_totals",not mismatches,
       {"mismatches":len(mismatches),"examples":mismatches[:5]})
 old=old[["fnid","harvest_year","window","calendar_months_included","precip_total_mm","status"]]
 combined=pd.concat([old,alt[old.columns]],ignore_index=True)
 check("combined_district_year_window_unique",not combined.duplicated(chkkeys).any())
 check("combined_expected_26x44x4",len(combined)==26*44*4,len(combined))
 combined=combined.merge(info,on="fnid",how="left",validate="many_to_one")
 
 # First 30 harvest years 1981–2010 are fixed climatology per district/window.
 b=combined.loc[combined.harvest_year.between(1981,2010)&
                combined.status.eq("COMPLETE")]
 stats=b.groupby(["fnid","window"]).precip_total_mm.agg(
  reference_n="count",reference_mean="mean",reference_sd="std").reset_index()
 combined=combined.merge(stats,on=["fnid","window"],validate="many_to_one")
 valid=combined.status.eq("COMPLETE")&combined.reference_n.ge(25)&combined.reference_sd.ge(5)
 combined["seasonal_z"]=np.where(valid,
      (combined.precip_total_mm-combined.reference_mean)/combined.reference_sd,np.nan)
 combined["seasonal_drought_z"]=np.where(combined.seasonal_z.notna(),
      np.maximum(-combined.seasonal_z,0),np.nan)
 combined["is_drought_z_le_minus1"]=np.where(combined.seasonal_z.notna(),
     combined.seasonal_z<=-1,np.nan)
 combined.to_csv(OUT/"malawi_maize_4_window_chirps_1981_2024.csv",index=False)
 # Wide table for per-district-year contrast.
 zz=combined.pivot(index=["fnid","harvest_year"],columns="window",values="seasonal_z")
 zz=zz.reset_index()
 assert set(["broad","core","waha_broad","waha_growth"]).issubset(zz.columns)
 zz=zz.merge(info[["fnid","BCODE","country_code","jrc_region"]],on="fnid",validate="many_to_one")
 check("unique_26x44_wide",len(zz)==26*44 and not zz.duplicated(["fnid","harvest_year"]).any())
 
 records=[]
 for a_name,b_name in [("broad","waha_broad"),("core","waha_growth")]:
  for region,g in [("ALL_3_MALAWI_REGIONS",zz)]+list(zz.groupby("jrc_region")):
   pair=g[[a_name,b_name]].apply(pd.to_numeric,errors="coerce").dropna()
   n=len(pair)
   z0=pair[a_name];z1=pair[b_name]
   shock0=z0.le(-1);shock1=z1.le(-1)
   records.append({"jrc_window":a_name,"survey_modal_window":b_name,"region":region,
      "districts":g.fnid.nunique(),"paired_district_years":n,
      "pearson_r":float(pair.corr().iloc[0,1]) if n>2 else np.nan,
      "spearman_r":float(pair.corr(method="spearman").iloc[0,1]) if n>2 else np.nan,
      "mean_abs_difference_z":float((z0-z1).abs().mean()) if n else np.nan,
      "median_abs_difference_z":float((z0-z1).abs().median()) if n else np.nan,
      "pct_different_negative_anomaly_sign":100*float((z0.lt(0)!=z1.lt(0)).mean()) if n else np.nan,
      "jrc_drought_z_below_minus1_count":int(shock0.sum()),
      "survey_modal_drought_z_below_minus1_count":int(shock1.sum()),
      "jrc_only_drought_classified":int((shock0&~shock1).sum()),
      "survey_only_drought_classified":int((~shock0&shock1).sum()),
      "pct_different_severe_drought_classification":100*float((shock0!=shock1).mean()) if n else np.nan,
      "n_drought_classification_disagree":int((shock0!=shock1).sum()),
      "independent_institution_effect_estimated":False})
 summ=pd.DataFrame(records)
 summ.to_csv(OUT/"malawi_maize_climate_window_sensitivity_summary.csv",index=False)
 # Attach pre-declared alternate-weather sensitivity to previously stored outcomes
 y=pd.read_csv(BASE/"season_outcome_crosswalk_v1"/
   "EXPLORATORY_not_causal_HarvestStat_x_JRC_x_CHIRPS_yield_weather.csv",low_memory=False)
 y=y.loc[y.country_code.eq("MW") & y["product"].eq("Maize")].copy()
 keep=["fnid","harvest_year","jrc_crop_season","product","season_name",
       "crop_production_system","yield","area","production","qc_flag"]
 outcomes=y[[c for c in keep if c in y.columns]].copy()
 src_n=len(outcomes)
 yy=outcomes.merge(zz[["fnid","harvest_year","jrc_region","broad","core",
                        "waha_broad","waha_growth"]],
                  on=["fnid","harvest_year"],how="left",validate="many_to_one")
 check("no_original_outcome_duplication",len(yy)==src_n and
       not yy.duplicated(["fnid","product","season_name","crop_production_system","harvest_year"]).any(),
       {"input":src_n,"result":len(yy)})
 check("no_outcome_year_loss",yy[["broad","core","waha_broad","waha_growth"]].notna().all(axis=1).sum()>0,
       {"n_with_all_4_z":int(yy[["broad","core","waha_broad","waha_growth"]].notna().all(axis=1).sum())})
 check("no_outcome_yield_recalculation_error",
       bool(((yy.production/yy.area-yy["yield"]).abs()/yy["yield"]).max()<1e-8))
 yy["status"]="EXPLORATORY_REFERENCES_NOT_PHENOLOGY_CONFIRMED"
 yy.to_csv(OUT/"malawi_maize_observed_yield_4_weather_windows_NO_REGRESSION.csv",index=False)
 REPORT["counts"]={
  "original_JRC_districts":int(info.fnid.nunique()),"regions":int(info.jrc_region.nunique()),
  "reference_window_month_year_rows":len(combined),
  "alternative_climate_rows":len(alt),
  "baseline_years":30,"season_comparison_district_year_pairs":int(len(zz)),
  "district_year_with_all_4_z":int(zz[["broad","core","waha_broad","waha_growth"]].notna().all(axis=1).sum()),
  "observed_HarvestStat_outcome_rows_unchanged":src_n,
  "sensitivity_pair_rows":len(summ),
  "comparisons":summ.to_dict("records")}
 REPORT["status"]="COMPLETE" if not REPORT["errors"] else "FAILED"
except Exception as e:
 REPORT["status"]="FAILED";REPORT["errors"].append(repr(e))
 REPORT["traceback"]=traceback.format_exc()[-4200:]
finally:
 save()
 print(json.dumps({"status":REPORT["status"],"errors":REPORT["errors"],
    "counts":REPORT.get("counts")},ensure_ascii=False,indent=2,default=str)[:24000])
if REPORT["status"]!="COMPLETE":sys.exit(1)
