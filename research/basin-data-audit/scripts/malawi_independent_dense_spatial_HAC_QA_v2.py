"""Independent QA: no functions imported from primary E06/E07 code.
Exact FE projection by dense dummy least squares; full observation-pair HAC,
contrasts independent year×district-score-matrix aggregation in main script.
"""
import pathlib,json,numpy as np,pandas as pd
from pyproj import Geod
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"malawi_spatial_e06_e07_v2"
SRC=ROOT/"results"/"malawi_rainfed_weather_yield_v1"/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv"
DATA=OUT/"malawi_conley_bandwidth_time_8models.csv"
LAGS=OUT/"malawi_previous_season_and_lead_placebo_results.csv"
G=OUT/"malawi_23_verified_geometry_centroids.csv"
P=OUT/"malawi_23_exact_source_polygons.geojson"
Q=OUT/"independent_dense_HAC_QA.json"
LOG={"status":"STARTED","method":"direct N-by-N observation-pair kernel; FE by dense dummy matrix; no shared estimator functions",
"checks":[]}
def check(k,ok,info=None):
    LOG["checks"].append({"check":k,"pass":bool(ok),"info":info})
    if not ok:raise AssertionError(k+": "+str(info))
try:
    src=pd.read_csv(SRC)
    dates=pd.read_csv(OUT/"malawi_812_rainfall_previous_next_season_diagnostic.csv")
    chk=pd.read_csv(DATA)
    lgt=pd.read_csv(LAGS)
    geo=pd.read_csv(G).set_index("fnid")
    gj=json.loads(P.read_text())
    feats=gj["features"]
    ids=[f["properties"]["fnid"] for f in feats]
    check("exact_23_geojson_features",len(feats)==23 and len(set(ids))==23)
    check("geojson_same_fid_set",set(ids)==set(geo.index))
    check("original_812_unique",len(src)==812 and not src.duplicated(["fnid","harvest_year"]).any())
    geod=Geod(ellps="WGS84")
    WIN=["broad","core","waha_broad","waha_growth"]
    max_beta=0.;max_se=0.;max_lag_beta=0.;max_lag_se=0.
    interiors=[]
    for name,v in (("strict16",src.loc[src.in_primary_16].copy()),("all23",src.copy())):
        n=len(v); districts=sorted(v.fnid.unique())
        index={s:i for i,s in enumerate(districts)}
        iy=np.array([index[s] for s in v.fnid])
        year=v.harvest_year.to_numpy(dtype=int)
        dt=np.abs(year[:,None]-year[None,:])
        time_w=np.where(dt<=1,1.0-dt/2.0,0.)
        dist_matrices={}
        for pos,columns in (("centroid",("lon","lat")),("representative",("represent_lon","represent_lat"))):
            lons=np.asarray([geo.loc[s,columns[0]] for s in districts],dtype=float)
            lats=np.asarray([geo.loc[s,columns[1]] for s in districts],dtype=float)
            d=np.zeros((len(districts),len(districts)))
            for i in range(len(districts)):
                for j in range(len(districts)):
                    _,_,vkm=geod.inv(lons[i],lats[i],lons[j],lats[j])
                    d[i,j]=vkm/1000
            check("dist_symmetric_"+name+"_"+pos,np.allclose(d,d.T,atol=1e-7))
            dist_matrices[pos]=d
        # Explicit dense dummy fixed effects projection, unlike alternating demeaning in main.
        D=pd.get_dummies(v[["fnid","harvest_year"]].astype(str),drop_first=True,dtype=float)
        D=np.column_stack([np.ones(n),D.to_numpy()])
        rank=np.linalg.matrix_rank(D)
        check("dummy_rank_"+name,rank==(len(districts)+v.harvest_year.nunique()-1),rank)
        yc=v.log_yield.to_numpy()
        yr=yc-D@np.linalg.lstsq(D,yc,rcond=1e-11)[0]
        correction=n/(n-(rank+1))
        wy=np.maximum(0,1.0-dist_matrices["centroid"][iy[:,None],iy[None,:]]/200)*time_w
        wr=np.maximum(0,1.0-dist_matrices["representative"][iy[:,None],iy[None,:]]/200)*time_w
        for window in WIN:
            x=v[window].to_numpy()
            xr=x-D@np.linalg.lstsq(D,x,rcond=1e-11)[0]
            beta=float(xr@yr/(xr@xr)); resid=yr-beta*xr; s=xr*resid
            se=float(np.sqrt(max(0,s@wy@s/(xr@xr)**2*correction)))
            se_interior=float(np.sqrt(max(0,s@wr@s/(xr@xr)**2*correction)))
            ref=chk.loc[(chk["sample"]==name)&(chk.window==window)&
                        (chk.spatial_centroid_cutoff_km==200)&(chk.temporal_lag_years==1)]
            check("single_reference_"+name+"_"+window,len(ref)==1)
            berror=abs(beta-float(ref.beta.iloc[0]));serror=abs(se-float(ref.conley_se_finite_corrected.iloc[0]))
            max_beta=max(max_beta,berror);max_se=max(max_se,serror)
            check("beta_reproduced_"+name+"_"+window,berror<1e-9,berror)
            check("conley_se_reproduced_"+name+"_"+window,serror<1e-9,serror)
            interiors.append({"sample":name,"window":window,"centroid_conley_se":se,
               "representative_point_conley_se":se_interior,
               "relative_difference_pct":100*(se_interior/se-1)})
        # Independent lag regression using fixed FE one-step projection, all climate years from previous script
        z=dates.loc[dates.fnid.isin(districts)].sort_values(["fnid","harvest_year"]).reset_index(drop=True)
        sorted_v=v.sort_values(["fnid","harvest_year"]).reset_index(drop=True)
        check("lagpanel_matches_source_"+name, bool((z.fnid.values==sorted_v.fnid.values).all() and
              (z.harvest_year.values==sorted_v.harvest_year.values).all()))
        dummies=pd.get_dummies(z[["fnid","harvest_year"]].astype(str),drop_first=True,dtype=float)
        DM=np.column_stack([np.ones(len(z)),dummies.to_numpy()])
        yy=z.log_yield.to_numpy();yp=yy-DM@np.linalg.lstsq(DM,yy,rcond=1e-11)[0]
        di2=np.array([index[f] for f in z.fnid])
        dd2=np.abs(z.harvest_year.to_numpy()[:,None]-z.harvest_year.to_numpy()[None,:])
        W=np.maximum(0,1-dist_matrices["centroid"][di2[:,None],di2[None,:]]/200)*np.where(dd2<=1,1-dd2/2,0)
        for w in WIN:
            for typ,var in (("lag1",w+"_lag1"),("lead1_placebo",w+"_lead1")):
                check("no_missing_other_rain_"+name+"_"+w+"_"+typ,not z[var].isna().any())
                Z=z[[w,var]].to_numpy()
                A=Z-DM@np.linalg.lstsq(DM,Z,rcond=1e-11)[0]
                b=np.linalg.lstsq(A,yp,rcond=1e-11)[0];ee=yp-A@b
                S=A*ee[:,None];xx=np.linalg.inv(A.T@A)
                cov=(xx@(S.T@W@S)@xx)*(len(z)/(len(z)-(np.linalg.matrix_rank(DM)+2)))
                ss=np.sqrt(np.maximum(0,np.diag(cov)))
                ref=lgt.loc[(lgt["sample"]==name)&(lgt.window==w)&(lgt.specification==typ)]
                check("one_lag_row_"+name+"_"+w+"_"+typ,len(ref)==1)
                eb=max(abs(b[0]-ref.beta_current.iloc[0]),abs(b[1]-ref.beta_previous_or_future.iloc[0]))
                es=max(abs(ss[0]-ref.conley_se_current_200km_lag1.iloc[0]),
                       abs(ss[1]-ref.conley_se_other_200km_lag1.iloc[0]))
                max_lag_beta=max(max_lag_beta,eb);max_lag_se=max(max_lag_se,es)
                check("lag_beta_reproduced_"+name+"_"+w+"_"+typ,eb<1e-9,eb)
                check("lag_conley_reproduced_"+name+"_"+w+"_"+typ,es<1e-9,es)
    pd.DataFrame(interiors).to_csv(OUT/"centroid_vs_representative_se_independent.csv",index=False)
    LOG["max_abs_beta_difference"]=max_beta; LOG["max_abs_conley_se_difference"]=max_se
    LOG["max_abs_lag_beta_difference"]=max_lag_beta; LOG["max_abs_lag_se_difference"]=max_lag_se
    LOG["checks_count"]=len(LOG["checks"])
    LOG["status"]="PASS"
except Exception as ex:
    LOG["status"]="FAILED";LOG["error"]=repr(ex)
Q.write_text(json.dumps(LOG,ensure_ascii=False,indent=2,default=lambda v: v.item() if isinstance(v,np.generic) else str(v))+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in LOG.items() if k!="checks"},ensure_ascii=False))
if LOG["status"]!="PASS":raise RuntimeError(LOG.get("error","independent QA FAILED"))
