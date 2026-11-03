"""Crop-reference-season rainfall from independent EC-JRC ASAP FAO/satellite calendars.

Scientific guardrails:
* use ONLY GAUL1 spatially audited HarvestStat district matches (>=80% polygon).
* independently sourced fixed crop/region windows (sos_s/eos_e dekads);
  no harveststat planting/harvest date used to define climate.
* two windows: broad (first sowing to last harvest) and growth-core
  (end sowing to start harvest); convert dekads to WHOLE calendar months.
* assign rainfall relative to HARVEST YEAR, use YEAR-1 for Oct-Apr windows.
* baseline 1981-2010 for seasonal totals; requires >=25 complete reference years
  and >=5 mm sample sd; no extrapolation for missing 1980 winter sources.
* no inferred irrigation, drought causality, or confirmed actual crop season.
* label as standardised precipitation anomalies, NOT distribution-fitted SPI.
"""
import datetime as dt, json, math, pathlib, sys, traceback
import numpy as np,pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/"results"/"phenology_v1"
C=ROOT/"results"/"climate_panel"
OUT=ROOT/"results"/"seasonal_climate_v1";OUT.mkdir(parents=True,exist_ok=True)
LOG={"utc":dt.datetime.now(dt.timezone.utc).isoformat(),"status":"STARTED",
 "source_calendar":"EC JRC ASAP v2018 FAO+FPAR, GAUL1; 80% geometry crosswalk with HarvestStat districts",
 "source_climate":"CHIRPS v3 final monthly rainfall, original 1981-2024 GeoTIFF source-hash validated",
 "calendar_fields":{"sos_s":"start sowing","sos_e":"end sowing / start growing",
 "eos_s":"end growing / start harvest","eos_e":"end harvest"},
 "units":"raw seasonal total mm per full calendar month included; seasonal_z = standardized normal anomaly, NOT SPI",
 "phenology":"Static reference crop-region calendar; no annual variation or measured actual crop growth stages",
 "methods":{"broad":"sos_s through eos_e, inclusive months","core":"sos_e through eos_s, inclusive months",
 "baseline":"1981-2010, by district × JRC crop-season × window",
 "baseline_min_valid_years":25,"baseline_min_sd_mm":5,
 "pixel_valid_threshold":3,"cross_year":"months in calendar year before declared harvest year when start dekad > end dekad"},
 "errors":[],"counts":{}}
def save():
 (OUT/"seasonal_climate_provenance.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=str)+"\n")
def month_of_dekad(d):
 d=int(d)
 assert 1<=d<=36
 return (d-1)//3+1
def window_months(start_dekad,end_dekad,harvest_year):
 """Inclusive whole-month approximation to JRC dekad interval.
 If source start dekad > end dekad, the season crosses New Year.
 E.g. Oct-Dec of t-1, Jan-Apr of t, where t = harvest year.
 """
 start_dekad,end_dekad=int(start_dekad),int(end_dekad)
 assert 1<=start_dekad<=36 and 1<=end_dekad<=36
 start,end=month_of_dekad(start_dekad),month_of_dekad(end_dekad)
 crosses=start_dekad>end_dekad
 if not crosses:
  months=[(harvest_year,m) for m in range(start,end+1)]
 else:
  months=[(harvest_year-1,m) for m in range(start,13)]+[(harvest_year,m) for m in range(1,end+1)]
 assert 1<=len(months)<=12,(start_dekad,end_dekad,harvest_year,months)
 return months,crosses
try:
 # Source logic / cross-year tests independent of data:
 assert window_months(31,11,2010)[0]==[(2009,11),(2009,12),(2010,1),(2010,2),(2010,3),(2010,4)]
 assert window_months(4,18,2010)[0]==[(2010,2),(2010,3),(2010,4),(2010,5),(2010,6)]
 assert window_months(35,2,2010)[0]==[(2009,12),(2010,1)]
 assert window_months(13,13,2010)[0]==[(2010,5)]
 assert window_months(12,7,1981)[0]==[(1980,4),(1980,5),(1980,6),(1980,7),(1980,8),(1980,9),(1980,10),(1980,11),(1980,12),(1981,1),(1981,2),(1981,3)]
 # Last case dekads 12 April3 -> 7 March1 (near-year cycle). It should be 12 months.
 src=json.loads((P/"jrc_spatial_crosswalk_provenance.json").read_text())
 climatesrc=json.loads((C/"full_climate_monthly_qa.json").read_text())
 assert src["status"]=="COMPLETE" and climatesrc["status"]=="COMPLETE"
 a=pd.read_csv(P/"district_JRC_external_cropping_seasons.csv")
 c=pd.read_csv(C/"district_chirps_v3_monthly_1981_2024_with_anomalies.csv",
   usecols=["fnid","year","month","rainfall_mm_month","valid_grid_cell_centres"])
 assert a.fnid.nunique()==159, a.fnid.nunique()
 assert len(a)==338,len(a)
 assert c.fnid.nunique()==253
 assert not c.duplicated(["fnid","year","month"]).any()
 cmap=c.set_index(["fnid","year","month"])
 records=[]
 for r in a.itertuples(index=False):
  for w,begin,end in (("broad",r.sos_s,r.eos_e),
                       ("core",r.sos_e,r.eos_s)):
   for hy in range(1981,2025):
    months,cross=window_months(begin,end,hy)
    mms=[];sup=[];missing=[]
    for year,mo in months:
     key=(r.fnid,year,mo)
     if key in cmap.index:
      val=cmap.loc[key]
      prec=float(val.rainfall_mm_month)
      pixels=int(val.valid_grid_cell_centres)
      if np.isfinite(prec) and prec>=0:
       mms.append(prec)
       sup.append(pixels)
      else:missing.append((year,mo))
     else:missing.append((year,mo))
    if len(mms)!=len(months):
     total=np.nan
     status="INCOMPLETE_WINDOW"
    else:
     total=float(np.sum(mms))
     status="LOW_PIXEL_SUPPORT" if min(sup)<3 else "COMPLETE"
    records.append({"fnid":r.fnid,"BCODE":r.BCODE,"dominant_bcu":r.dominant_bcu,
     "country_code":r.country_code,"asap1_id":int(r.asap1_id),
     "jrc_region":r.name1_shr,"crop":r.crop,"jrc_crop_season":r.crop_name,
     "JRC_sos_start_dekad":r.sos_s,"JRC_sos_end_dekad":r.sos_e,
     "JRC_eos_start_dekad":r.eos_s,"JRC_eos_end_dekad":r.eos_e,
     "jrc_spatial_coverage_fraction":r.frac_district,
     "window":w,"harvest_year":hy,"crosses_calendar_year":cross,
     "months_window":len(months),
     "from_year":months[0][0],"from_month":months[0][1],
     "to_year":months[-1][0],"to_month":months[-1][1],
     "calendar_months_included":";".join(f"{y}-{m:02d}" for y,m in months),
     "precip_total_mm":total,
     "min_raster_grid_centres":int(min(sup)) if sup else 0,
     "window_data_status":status,"n_missing_source_months":len(missing),
     "climate_is_locally_averaged_not_upstream":True,
     "yearly_planting_observed":False})
 panel=pd.DataFrame(records)
 assert len(panel)==338*2*44,len(panel)
 unique=["fnid","jrc_crop_season","window","harvest_year"]
 assert not panel.duplicated(unique).any()
 # standardize seasonal anomalies on fixed ref for *each* district/crop-JRC-season/window
 base=panel.loc[panel.harvest_year.between(1981,2010)&panel.window_data_status.eq("COMPLETE")]
 dims=["fnid","jrc_crop_season","window"]
 bc=base.groupby(dims).precip_total_mm.agg(
   baseline_count="count",baseline_mean_mm="mean",baseline_sd_mm="std").reset_index()
 panel=panel.merge(bc,on=dims,how="left",validate="many_to_one")
 okay=(panel.window_data_status.eq("COMPLETE")&
       panel.baseline_count.ge(25)&panel.baseline_sd_mm.ge(5))
 panel["seasonal_anomaly_mm"]=np.where(panel.window_data_status.eq("COMPLETE"),
                              panel.precip_total_mm-panel.baseline_mean_mm,np.nan)
 panel["seasonal_precip_z"]=np.where(okay,
                              (panel.precip_total_mm-panel.baseline_mean_mm)/panel.baseline_sd_mm,np.nan)
 panel["seasonal_deficit_z"]=np.where(panel.seasonal_precip_z.notna(),
                             np.maximum(-panel.seasonal_precip_z,0),np.nan)
 panel["is_spi"]=False
 assert panel.seasonal_deficit_z.dropna().ge(0).all()
 panel.sort_values(unique).to_csv(OUT/"JRC_crop_season_CHIRPS_1981_2024.csv",index=False)
 # compact safe calendar table for easier manual review of unusual crop seasons
 season_distinct=panel.loc[panel.harvest_year.eq(2020)].drop_duplicates(
  ["fnid","jrc_crop_season","window"])
 summar=(panel.groupby(["BCODE","country_code","crop","jrc_crop_season","window"],dropna=False)
  .agg(districts=("fnid","nunique"),
       grid_seasons=("harvest_year","count"),
       valid_precip_windows=("precip_total_mm","count"),
       valid_z=("seasonal_precip_z","count"),
       crossyear_count=("crosses_calendar_year","sum"),
       missing_month_count=("n_missing_source_months","sum")).reset_index())
 summar.to_csv(OUT/"crop_season_coverage_and_quality.csv",index=False)
 LOG["counts"]={
  "source_season_assignments":len(a),"distinct_districts":a.fnid.nunique(),
  "source_crop_counts":a.groupby("crop").fnid.nunique().to_dict(),
  "seasonal_year_rows":len(panel),"valid_precip_totals":int(panel.precip_total_mm.notna().sum()),
  "complete_spatial_precip_windows":int(panel.window_data_status.eq("COMPLETE").sum()),
  "low_pixel_support_windows":int(panel.window_data_status.eq("LOW_PIXEL_SUPPORT").sum()),
  "incomplete_source_windows":int(panel.window_data_status.eq("INCOMPLETE_WINDOW").sum()),
  "valid_seasonal_z":int(panel.seasonal_precip_z.notna().sum()),
  "crossyear_rows":int(panel.crosses_calendar_year.sum()),
  "crossyear_distinct_source_seasons":int(season_distinct.crosses_calendar_year.sum()),
  "years":44}
 LOG["qa"]={
  "reference_count_max":int(bc.baseline_count.max()),
  "reference_count_min":int(bc.baseline_count.min()),
  "duplicate_crop_season_district_year":int(panel.duplicated(unique).sum()),
  "baseline_mean_recomputed_4_groups_example":bc.head(4).to_dict("records"),
  "2020_sample_cross_year":panel.loc[(panel.harvest_year==2020)&panel.crosses_calendar_year].head(4)[
  ["country_code","crop","jrc_crop_season","calendar_months_included","precip_total_mm"]].to_dict("records")}
 LOG["status"]="COMPLETE"
except Exception as e:
 LOG["status"]="FAILED";LOG["errors"].append(str(e)[:500]);LOG["traceback"]=traceback.format_exc()[-3500:]
save()
print(json.dumps({"status":LOG["status"],"errors":LOG["errors"],"counts":LOG["counts"],"qa":LOG.get("qa")},ensure_ascii=False,indent=2,default=str)[:13000])
if LOG["status"]!="COMPLETE":sys.exit(1)
