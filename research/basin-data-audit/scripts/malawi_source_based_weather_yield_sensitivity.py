"""Diagnostic sample sensitivity for Source-audited Malawi rainfed maize TWFE.
Selection of samples is based on raw FDW provenance, not sign or significance.
No causal rainfall or treaty interpretation. Source match by district+year has
unresolved historical boundary mapping, not used as independent geographic proof.
"""
import pathlib, json, sys, traceback
import numpy as np, pandas as pd
R=pathlib.Path(__file__).resolve().parents[1]
S=R/"results"/"malawi_rainfed_weather_yield_v1"/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv"
M=R/"results"/"malawi_apes_fdw_source_audit_v1"/"historical_APES_FDW_vs_HarvestStat_by_district_year_unharmonized_identity.csv"
O=R/"results"/"malawi_apes_fdw_source_audit_v1"
OUT=O/"malawi_source_based_weather_yield_sensitivity.csv"
QA=O/"malawi_source_based_weather_yield_QA.json"
L={"status":"STARTED","checks":[],"warnings":["Different subsets are not independently randomized; changes in coefficients do not imply treatment effect",
 "Area/production matching old geography does not validate historical 2018 polygon",
 "No treaty variables, no instrument, no field-level planting or rainfall"]}
def check(name,condition,info=None):
 L["checks"].append({"name":name,"pass":bool(condition),"info":info})
 if not condition:raise AssertionError(name+": "+str(info))
def FE(v,g1,g2):
 out=np.asarray(v,float).copy()
 if out.ndim==1:out=out[:,None]
 for it in range(250):
  mx=0.
  for g in (g1,g2):
   keys,ind=np.unique(g,return_inverse=True)
   n=np.bincount(ind)
   for j in range(out.shape[1]):
    mean=np.bincount(ind,weights=out[:,j])/n
    out[:,j]-=mean[ind]
    mx=max(mx,float(np.max(np.abs(mean))))
  if mx<1e-12:return out
 raise RuntimeError("FE demeaning not converged")
def robust(v,window):
 d=v.fnid.to_numpy();t=v.harvest_year.to_numpy()
 x=FE(v[window].to_numpy(),d,t)[:,0];y=FE(v.log_yield.to_numpy(),d,t)[:,0]
 xx=float(x@x);beta=float((x@y)/xx)
 scr=x*(y-beta*x);N=len(v);nD=v.fnid.nunique();nT=v.harvest_year.nunique()
 K=nD+nT
 def cl(g):
  ids,n=np.unique(g,return_inverse=True);s=np.bincount(n,weights=scr)
  return float(s@s)/xx**2 * (len(ids)/(len(ids)-1))*((N-1)/(N-K))
 vD=cl(d);vT=cl(t);vDT=cl(np.array([a+"_"+str(b) for a,b in zip(d,t)]))
 return {"n":N,"districts":nD,"years":nT,"beta":beta,"district_se":np.sqrt(vD),
 "year_se":np.sqrt(vT),"two_way_se":np.sqrt(max(vD+vT-vDT,0))}
try:
 a=pd.read_csv(S);b=pd.read_csv(M)
 check("whole_model_panel_812",len(a)==812)
 check("name_based_915",len(b)==915)
 b=b.loc[b.season_name.eq("Main")&b["system"].eq("Rainfed (PS)")].copy()
 check("name_based_812",len(b)==812)
 check("model_keys_unique",not a.duplicated(["fnid","harvest_year"]).any())
 check("source_keys_unique",not b.duplicated(["fnid_harmonized","harvest_year"]).any())
 a=a.merge(b[["fnid_harmonized","harvest_year","has_raw_key","reported_yield_exact","area_prod_agree"]],
           left_on=["fnid","harvest_year"],right_on=["fnid_harmonized","harvest_year"],validate="one_to_one")
 check("full_join_812",len(a)==812)
 s=a.loc[a.in_primary_16].copy()
 check("main_16_584",len(s)==584 and s.fnid.nunique()==16)
 cohorts={
 "strict16_all":s,
 "strict16_exact_FDW_yield":s.loc[s.reported_yield_exact].copy(),
 "strict16_exact_FDW_area_production":s.loc[s.area_prod_agree].copy(),
 "strict16_1998_2020":s.loc[s.harvest_year.ge(1998)].copy(),
 "strict16_2018_2020_too_short":s.loc[s.harvest_year.ge(2018)].copy()
 }
 expected={"strict16_all":584,"strict16_exact_FDW_yield":570,
    "strict16_exact_FDW_area_production":437,"strict16_1998_2020":362,
    "strict16_2018_2020_too_short":42}
 for k,v in cohorts.items():check("cohort_count_"+k,len(v)==expected[k],len(v))
 win=("broad","core","waha_broad","waha_growth")
 rows=[]
 for k,v in cohorts.items():
  for w in win:
   z=robust(v,w);rows.append({"sample":k,"window":w,**z,
         "restricted_subset_not_random":True,"not_treaty_effect":True})
 df=pd.DataFrame(rows)
 df.to_csv(OUT,index=False)
 beta=df.loc[(df["sample"]=="strict16_all") & (df.window=="broad"),"beta"].iloc[0]
 check("reproduces_prior_584_main_beta",abs(beta-0.1030478053413435)<1e-10,beta)
 # Numerically independent dummy-matrix FWL against alternating demeaning.
 z=cohorts["strict16_exact_FDW_area_production"]
 Xdummy=pd.get_dummies(z[["fnid","harvest_year"]].astype(str),drop_first=True,dtype=float)
 D=np.column_stack([np.ones(len(z)),Xdummy.to_numpy()])
 x=z.broad.to_numpy();y=z.log_yield.to_numpy()
 rx=x-D@np.linalg.lstsq(D,x,rcond=None)[0]
 ry=y-D@np.linalg.lstsq(D,y,rcond=None)[0]
 separate=float(rx@ry/(rx@rx))
 calc=float(df.loc[(df["sample"]=="strict16_exact_FDW_area_production") & (df.window=="broad"),"beta"].iloc[0])
 check("independent_lstsq_437_coefficient",abs(separate-calc)<1e-10,
       {"first":calc,"dense":separate,"abs_error":abs(calc-separate)})
 L["counts"]={"cohorts":expected,"models":len(df),"all_four_positive_for_four_primary_samples":
   bool(df.loc[~df["sample"].eq("strict16_2018_2020_too_short"),"beta"].gt(0).all())}
 L["status"]="PASS"
except Exception as e:
 L["status"]="FAILED";L["error"]=str(e);L["traceback"]=traceback.format_exc()[-5000:]
QA.write_text(json.dumps(L,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf8")
print(json.dumps({k:v for k,v in L.items() if k!="checks"},ensure_ascii=False))
sys.exit(0 if L["status"]=="PASS" else 1)
