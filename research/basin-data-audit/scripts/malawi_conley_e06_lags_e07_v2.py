"""Independent geodesic spatial Conley-HAC + temporal lag QA for Malawi maize.
No implied effect of climate or transboundary institution. Repo-root script.
Reads pin-fixed original HarvestStat v1.2 polygon GPKG; outputs only verified source-derived coordinates.
"""
import hashlib, json, pathlib, urllib.request, sys, traceback, datetime, csv
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Geod
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_spatial_e06_e07_v2"; OUT.mkdir(parents=True,exist_ok=True)
old=ROOT/"results"/"malawi_rainfed_weather_yield_v1"/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv"
climfile=ROOT/"results"/"malawi_maize_calendar_sensitivity_v1"/"malawi_maize_4_window_chirps_1981_2024.csv"
SOURCE=json.loads((ROOT/"results"/"harveststat"/"audit_provenance.json").read_text())["inputs"]["harveststat_boundaries"]
WINS=["broad","core","waha_broad","waha_growth"]
LOG={"status":"STARTED","source":SOURCE,"start_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "checks":{},"limits":["historical yields use a modern common admin boundary; historical polygon stability unknown",
       "Conley bandwidths prespecified sensitivity, not valid as confirmed causal standard errors",
       "monthly calendars are nominal not observed yearly crop phenology","do not infer river-water treatment"]}
def check(n,p,details=None):
    LOG["checks"][n]={"pass":bool(p),"details":details}
    if not p:raise AssertionError(n+": "+str(details))
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for part in iter(lambda:f.read(2**20),b""):h.update(part)
    return h.hexdigest()
def twfe(mat,d,t):
    mat=np.asarray(mat,dtype=float).copy()
    if mat.ndim==1:mat=mat[:,None]
    du,di=np.unique(d,return_inverse=True);tu,ti=np.unique(t,return_inverse=True)
    for k in range(500):
        big=0.
        for ix,n in ((di,len(du)),(ti,len(tu))):
            counts=np.bincount(ix,minlength=n)
            for j in range(mat.shape[1]):
                means=np.bincount(ix,weights=mat[:,j],minlength=n)/counts
                mat[:,j]-=means[ix]
                big=max(big,float(np.max(np.abs(means))))
        if big<1e-11:return mat,k+1,big
    raise RuntimeError("FE demeaning did not converge")
def hac(d,t,x,y,geo,cutoff=200,lag=1):
    # geographically kernel-weighted cross-year score covariance; excludes missing district-years
    du=list(sorted(set(d))); tu=list(sorted(set(t)))
    nx=len(du); ny=len(tu);idx={f:i for i,f in enumerate(du)};iy={int(z):i for i,z in enumerate(tu)}
    lat=np.array([geo.loc[f,"lat"] for f in du]);lon=np.array([geo.loc[f,"lon"] for f in du])
    geod=Geod(ellps="WGS84"); dist=np.empty((nx,nx))
    for i in range(nx):
        _,_,meters=geod.inv(np.full(nx,lon[i]),np.full(nx,lat[i]),lon,lat)
        dist[i]=np.asarray(meters)/1000
    W=np.maximum(0,1-dist/cutoff)
    check_inner=np.max(np.abs(W-W.T))<1e-9
    if not check_inner:raise RuntimeError("distance/kernel asymmetric")
    XX=x.T@x; b=np.linalg.solve(XX,x.T@y);e=y-x@b
    scr=np.zeros((ny,nx,x.shape[1]))
    for i in range(len(d)):scr[iy[int(t[i])],idx[d[i]]]+=x[i]*e[i]
    omega=np.zeros((x.shape[1],x.shape[1]))
    for a in range(ny):
        for btime in range(ny):
            dt=abs(tu[btime]-tu[a])
            if dt>lag:continue
            wt=1-dt/(lag+1)
            omega+=wt*scr[a].T@W@scr[btime]
    invXX=np.linalg.inv(XX)
    V=invXX@omega@invXX
    correction=len(y)/(len(y)-(nx+ny-1+x.shape[1]))
    V=V*correction
    return {"beta":b,"se":np.sqrt(np.maximum(0,np.diag(V))),
            "V":V,"omega":omega,"scores":scr,"space":W,"dist":dist,
            "correction":correction,"min_eigen":float(np.linalg.eigvalsh(V).min())}
try:
    panel=pd.read_csv(old);panel["harvest_year"]=panel.harvest_year.astype(int)
    check("812_source_rows",len(panel)==812)
    check("no_duplicate_fnid_year",not panel.duplicated(["fnid","harvest_year"]).any())
    ids=sorted(panel.fnid.unique());strict_ids=sorted(panel.loc[panel.in_primary_16,"fnid"].unique())
    check("23_16_ids",len(ids)==23 and len(strict_ids)==16,(len(ids),len(strict_ids)))
    local=OUT/"_SOURCE_DO_NOT_COMMIT.gpkg"
    if not local.exists():urllib.request.urlretrieve(SOURCE["url"],local)
    check("original_gpkg_bytes",local.stat().st_size==SOURCE["size_bytes"],local.stat().st_size)
    check("original_gpkg_sha",sha(local)==SOURCE["sha256"],sha(local))
    gg=gpd.read_file(local)
    check("geo_crs_defined",gg.crs is not None,str(gg.crs))
    check("geo_fnid_unique",gg.fnid.is_unique)
    sub=gg.loc[gg.fnid.isin(ids)].copy()
    check("exact_all_23_fnids",len(sub)==23 and set(sub.fnid)==set(ids),list(set(ids)-set(sub.fnid)))
    check("only_malawi_source_polygons",set(sub.country_code)=={"MW"},sub.country_code.unique().tolist())
    check("source_polygons_valid",bool(sub.geometry.is_valid.all()))
    check("source_polygons_not_empty",not sub.geometry.is_empty.any())
    check("original_equal_area_nonzero",bool(sub.to_crs("EPSG:6933").area.gt(0).all()))
    sub=sub.sort_values("fnid")
    equal=sub.to_crs("EPSG:6933")
    cents=gpd.GeoSeries(equal.geometry.centroid,crs="EPSG:6933").to_crs("EPSG:4326")
    reps=gpd.GeoSeries(equal.geometry.representative_point(),crs="EPSG:6933").to_crs("EPSG:4326")
    meta=pd.DataFrame({"fnid":sub.fnid.to_list(),"lon":cents.x.to_list(),"lat":cents.y.to_list(),
         "represent_lon":reps.x.to_list(),"represent_lat":reps.y.to_list(),
         "area_km2_EPSG6933":(equal.area/1e6).to_list(),
         "in_strict16":[x in strict_ids for x in sub.fnid]})
    meta.to_csv(OUT/"malawi_23_verified_geometry_centroids.csv",index=False)
    sub.to_crs("EPSG:4326").to_file(OUT/"malawi_23_exact_source_polygons.geojson",driver="GeoJSON")
    geo=meta.set_index("fnid")
    check("all_geocentroids_in_geographic_bounds",bool(geo.lon.between(32,36).all() and geo.lat.between(-18,-9).all()))
    geo2=geo.rename(columns={"lat":"centroid_lat","lon":"centroid_lon","represent_lat":"lat","represent_lon":"lon"})
    # Independent geodesic centroid-vs-representative-point neighborhood distances
    dist_report=[]
    for cohort,used in (("strict16",strict_ids),("all23",ids)):
        for method,g in [("centroid",geo),("interior_point",geo2)]:
            vals=[]
            geod=Geod(ellps="WGS84")
            for i,u in enumerate(used):
                for v in used[i+1:]:
                    _,_,d=geod.inv(g.loc[u,"lon"],g.loc[u,"lat"],g.loc[v,"lon"],g.loc[v,"lat"])
                    vals.append(d/1000)
            dist_report.append({"cohort":cohort,"method":method,"n_pairs":len(vals),
               "distance_min_km":min(vals),"distance_median_km":float(np.median(vals)),
               "pairs_below_100km":sum(v<100 for v in vals),
               "pairs_below_200km":sum(v<200 for v in vals),
               "pairs_below_300km":sum(v<300 for v in vals)})
    pd.DataFrame(dist_report).to_csv(OUT/"polygon_distance_sensitivity.csv",index=False)
    # full climate windows: t-1, t+1 must be computed on ALL climate rows, never shift over yield-year gaps.
    cc=pd.read_csv(climfile)
    check("climate_unique_key",not cc.duplicated(["fnid","harvest_year","window"]).any())
    check("all_four_windows_available",set(WINS).issubset(set(cc.window)))
    cc=cc.loc[cc.fnid.isin(ids)&cc.window.isin(WINS),["fnid","harvest_year","window","seasonal_z"]]
    wide=cc.pivot(index=["fnid","harvest_year"],columns="window",values="seasonal_z").reset_index()
    chk=panel[["fnid","harvest_year"]+WINS].merge(wide,on=["fnid","harvest_year"],suffixes=("_panel","_source"),validate="one_to_one")
    maxdiff=max(float(np.max(np.abs(chk[f"{w}_panel"]-chk[f"{w}_source"]))) for w in WINS)
    check("climate_reconciles_source_and_model",maxdiff<1e-9,maxdiff)
    lag0=wide.rename(columns={w:f"{w}_lag1" for w in WINS}).copy()
    lag0["harvest_year"]+=1
    lead0=wide.rename(columns={w:f"{w}_lead1" for w in WINS}).copy()
    lead0["harvest_year"]-=1
    lagpanel=panel.merge(lag0[["fnid","harvest_year"]+[f"{w}_lag1" for w in WINS]],on=["fnid","harvest_year"],how="left",validate="one_to_one")
    lagpanel=lagpanel.merge(lead0[["fnid","harvest_year"]+[f"{w}_lead1" for w in WINS]],on=["fnid","harvest_year"],how="left",validate="one_to_one")
    check("lag_source_nonmissing",bool(lagpanel[[f"{w}_lag1" for w in WINS]].notna().all().all()))
    lagpanel.to_csv(OUT/"malawi_812_rainfall_previous_next_season_diagnostic.csv",index=False)
    conley=[]; lagresults=[]
    refbeta={("strict16","broad"):0.1030478053413435,("all23","broad"):0.08559128253891249}
    for cohort,p in (("strict16",lagpanel.loc[lagpanel.in_primary_16].copy()),("all23",lagpanel.copy())):
        check("cohort_rows_"+cohort,len(p)==(584 if cohort=="strict16" else 812))
        d=p.fnid.to_numpy();tt=p.harvest_year.to_numpy()
        for w in WINS:
            X,its,err=twfe(p[[w]].to_numpy(),d,tt)
            Y,_,_=twfe(p.log_yield.to_numpy(),d,tt);Y=Y[:,0]
            b=float(np.linalg.solve(X.T@X,X.T@Y)[0])
            if (cohort,w) in refbeta:check("beta_matches_original_"+cohort,abs(b-refbeta[(cohort,w)])<1e-9,b)
            for cutoff in (100,200,300):
                for tl in (0,1,2):
                    res=hac(d,tt,X,Y,geo,cutoff=cutoff,lag=tl)
                    se=float(res["se"][0])
                    check("conley_finite_"+cohort+"_"+w+"_"+str(cutoff)+"_"+str(tl),np.isfinite(se) and se>0)
                    conley.append({"sample":cohort,"window":w,"n":len(p),"districts":len(set(d)),"years":len(set(tt)),
                    "beta":b,"spatial_centroid_cutoff_km":cutoff,"temporal_lag_years":tl,
                    "conley_se_finite_corrected":se,"t_descriptive":b/se,"small_sample_multiplier":res["correction"],
                    "min_cov_eigen":res["min_eigen"],"geometry_version":"HarvestStat v1.2 pinned",
                    "no_causal_claim":True})
            # robust reference at 200km/1 year plus interior representative point and brute force validation
            r=hac(d,tt,X,Y,geo,cutoff=200,lag=1)
            rr=hac(d,tt,X,Y,geo2,cutoff=200,lag=1)
            check("centroid_interior_ratio_"+cohort+"_"+w, np.isfinite(rr["se"][0]/r["se"][0]))
            if cohort=="strict16" and w=="broad":
                # Independent brute-force pairwise score cross-products (not score-matrix shortcut).
                geod=Geod(ellps="WGS84");s=(X[:,0]*(Y-X[:,0]*b));omega=0.
                for i in range(len(p)):
                    dt=np.abs(tt-tt[i]);ix=np.flatnonzero(dt<=1)
                    ui=geo.loc[d[i]]
                    for j in ix:
                        vj=geo.loc[d[j]]
                        _,_,km=geod.inv(ui.lon,ui.lat,vj.lon,vj.lat)
                        sw=max(0.,1-km/1000/200)
                        omega+=s[i]*s[j]*sw*(1-abs(tt[i]-tt[j])/2)
                independent=omega/(float((X.T@X)[0,0])**2)*r["correction"]
                check("independent_pairwise_conley_omega",abs(independent-r["V"][0,0])<1e-10,abs(independent-r["V"][0,0]))
            for typ,var in (("lag1",f"{w}_lag1"),("lead1_placebo",f"{w}_lead1")):
                ok=p[var].notna()
                q=p.loc[ok];dd=q.fnid.to_numpy(); yy=q.harvest_year.to_numpy()
                xx,_,_=twfe(q[[w,var]].to_numpy(),dd,yy)
                ytemp,_,_=twfe(q.log_yield.to_numpy(),dd,yy);yt=ytemp[:,0]
                r2=hac(dd,yy,xx,yt,geo,cutoff=200,lag=1)
                lagresults.append({"sample":cohort,"window":w,"specification":typ,"n":len(q),
                "beta_current":float(r2["beta"][0]),"beta_previous_or_future":float(r2["beta"][1]),
                "conley_se_current_200km_lag1":float(r2["se"][0]),
                "conley_se_other_200km_lag1":float(r2["se"][1]),
                "interpretation":"previous season correlation, not measured biophysical lag" if typ=="lag1"
                   else "future-rain falsification screen; a nonzero result indicates model uncertainty",
                "cause_treaty_effect":False})
    pd.DataFrame(conley).to_csv(OUT/"malawi_conley_bandwidth_time_8models.csv",index=False)
    pd.DataFrame(lagresults).to_csv(OUT/"malawi_previous_season_and_lead_placebo_results.csv",index=False)
    LOG["geometry"]={"n_source_polygons":len(sub),"sha256":SOURCE["sha256"],"strict_16":strict_ids,
                      "modern_polygon_applied_to_1983_2020":True}
    LOG["counts"]={"conley_specifications":len(conley),"lead_lag_specifications":len(lagresults),
                     "max_reconciled_climate_difference":maxdiff}
    LOG["status"]="PASS"
except Exception as ex:
    LOG["status"]="FAILED";LOG["exception"]=str(ex);LOG["traceback"]=traceback.format_exc()[-6000:]
finally:
    (OUT/"spatial_and_year_source_QA.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":LOG["status"],"counts":LOG.get("counts"),"exception":LOG.get("exception"),
       "checks":len(LOG["checks"])},ensure_ascii=False))
    sys.exit(0 if LOG["status"]=="PASS" else 1)
