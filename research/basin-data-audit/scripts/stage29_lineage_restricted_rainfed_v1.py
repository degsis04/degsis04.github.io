"""Stage29 pre-specified reduced-district robustness on source-lineage-defined cohorts.
This is descriptive weather/yield association only, not evidence on institutions.
Retains no recreated panel; all numbers source check with QA.
"""
import pathlib,json,datetime,sys,traceback
import numpy as np,pandas as pd
R=pathlib.Path(__file__).resolve().parents[1]
O=R/"results"/"stage29_admin_lineage_design_gate";O.mkdir(exist_ok=True,parents=True)
D=R/"results"/"malawi_rainfed_weather_yield_v1"/"malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv"
SOURCE=O/"strict16_critical_district_decision_table.csv"
L={"status":"STARTED","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
   "checks":{},"limitations":["Removing districts alters climate mix and sample composition; not a randomized intervention",
     "10 independent district IDs is too few for precise large-sample cluster inference",
     "Source lineage direct raw numeric agreement does not validate historical physical polygon geometry",
     "No institutional factor in these models"]}
def ch(k,b,v=None):
 L["checks"][k]={"pass":bool(b),"info":v}
 if not b:raise AssertionError(k+": "+str(v))
def demean(a,ds,ts):
 a=np.asarray(a,float).copy()
 if a.ndim==1:a=a[:,None]
 for i in range(500):
  maxerror=0.
  for v in (ds,ts):
   u,ix=np.unique(v,return_inverse=True);cnt=np.bincount(ix)
   for j in range(a.shape[1]):
    m=np.bincount(ix,weights=a[:,j])/cnt
    a[:,j]-=m[ix];maxerror=max(maxerror,float(np.max(abs(m))))
  if maxerror<1e-11:return a
 raise RuntimeError("demean fail")
def ols(v,w):
 d=v.fnid.to_numpy();t=v.harvest_year.to_numpy()
 x=demean(v[w].to_numpy(),d,t)[:,0];y=demean(v.log_yield.to_numpy(),d,t)[:,0]
 den=float(x@x)
 b=float((x@y)/den)
 scr=x*(y-b*x)
 N=len(d);G=len(set(d));T=len(set(t));K=G+T
 def meat(group):
  u,i=np.unique(group,return_inverse=True)
  r=np.bincount(i,weights=scr)
  return float(r@r)/den**2 * (len(u)/(len(u)-1))*((N-1)/(N-K))
 sd=meat(d);st=meat(t);sdt=meat(np.array([a+"_"+str(q) for a,q in zip(d,t)]))
 return {"beta":b,"se_district":float(np.sqrt(max(0,sd))),"se_two_way":float(np.sqrt(max(0,sd+st-sdt))),
         "n":N,"n_districts":G,"n_years":T,"status":"DESCRIPTIVE_NOT_CAUSAL"}
try:
 v=pd.read_csv(D);meta=pd.read_csv(SOURCE)
 ch("model_812",len(v)==812)
 ch("metadata_16",len(meta)==16)
 panel=v.loc[v.in_primary_16].merge(meta[["fnid","risk_rank"]],on="fnid",validate="many_to_one")
 ch("strict16_584",len(panel)==584)
 cohorts={
  "strict16_all":panel,
  "exclude_b alaka".replace(" ",""):panel.loc[~panel.fnid.eq("MW2018A20318")],
  "low_source_reconstruction_risk_10_districts":panel.loc[panel.risk_rank.eq("LOW_MATCHING_ORIGINAL_VALUES")],
  "five_scalar_transfer_districts_only":panel.loc[panel.risk_rank.eq("MODERATE_AREA_PROD_TRANSFORMED")],
 }
 ch("10_low_districts",cohorts["low_source_reconstruction_risk_10_districts"].fnid.nunique()==10)
 ch("5_scalar_districts",cohorts["five_scalar_transfer_districts_only"].fnid.nunique()==5)
 wins=["broad","core","waha_broad","waha_growth"]
 result=[]
 for cname,df in cohorts.items():
  for w in wins: result.append({"sample":cname,"window":w,**ols(df,w)})
 o=pd.DataFrame(result)
 o.to_csv(O/"stage29_rainfed_maize_boundary_lineage_region_sensitivity.csv",index=False)
 ch("baseline_beta_reproduce",abs(o.loc[(o["sample"]=="strict16_all")&(o.window=="broad"),"beta"].iloc[0]-0.1030478053413435)<1e-10)
 L["samples"]={key:{"rows":len(df),"districts":df.fnid.nunique(),"years":df.harvest_year.nunique()}
  for key,df in cohorts.items()}
 L["all_four_beta_values"]={k:{w:float(q.beta.iloc[0]) for w,q in grp.groupby("window")}
  for k,grp in o.groupby("sample")}
 L["status"]="PASS"
except Exception as e:
 L["status"]="FAILED";L["error"]=repr(e);L["traceback"]=traceback.format_exc()[-3500:]
(O/"stage29_lineage_restricted_model_QA.json").write_text(json.dumps(L,indent=2,ensure_ascii=False,default=str)+"\n")
print(json.dumps({k:v for k,v in L.items() if k in ("status","samples","all_four_beta_values","error")},ensure_ascii=False))
sys.exit(0 if L["status"]=="PASS" else 1)
