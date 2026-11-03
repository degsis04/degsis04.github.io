#!/usr/bin/env node
"use strict";
/**
 * Stage26: Malawi rainfed-maize fixed-effects inference diagnostic.
 * Node built-ins only. Run from repository root:
 * node research/basin-data-audit/scripts/malawi_stage26_spatiotemporal_qa.js
 *
 * This is descriptive rainfed maize ~ district rainfall association.
 * NOT a Conley spatial-HAC test, a treaty effect or river-flow model.
 */
const fs = require("fs"), path = require("path"), assert = require("assert");
const root = path.join(process.cwd(), "research", "basin-data-audit");
const file = path.join(root, "results", "malawi_rainfed_weather_yield_v1", "malawi_812_MAIN_RAINFED_exploratory_weather_yield_input.csv");
const outdir = path.join(root, "results", "malawi_spatiotemporal_stage26");
const raw = fs.readFileSync(file, "utf8").trim().split(/\r?\n/);
const head = raw.shift().split(",");
assert.deepStrictEqual(head, ["fnid","harvest_year","jrc_region","yield","area","production","log_yield","in_primary_16","broad","core","waha_broad","waha_growth"]);
const data = raw.map(s => {
  const z = s.split(",");
  assert(z.length === 12, "unexpected CSV columns");
  return {d:z[0], yr:Number(z[1]), region:z[2], y:Number(z[6]), strict:z[7]==="True", x:[Number(z[8]),Number(z[9]),Number(z[10]),Number(z[11])]};
});
assert(data.length===812 && data.filter(z=>z.strict).length===584);
const windows=["JRC broad","JRC core","Waha broad","Waha growth"];
const historical={
 strict16:{beta:[.1030478053413435,.09042224650479153,.09597296485188828,.10309369831640744],
 district:[.02167981939358401,.02168808212162871,.022787176220070916,.022184062928604236],
 year:[.038033610614331616,.038471822161530826,.04101556002388118,.04059400942686978]},
 all23:{beta:[.08559128253891249,.07654598666845064,.080410362831288,.08553250045396177],
 district:[.018347199627439227,.01740151381094341,.018658118433723444,.01868628484604984],
 year:[.026908123596744143,.02677168587672234,.02828244106992645,.02778619671586709]}};
function mean(a){return a.reduce((s,v)=>s+v,0)/a.length;}
function residualize(vector,district,year){
  const z=vector.slice();
  for(let iter=0;iter<200;iter++){
    let max=0;
    for(const groups of [district,year]){
      const sum=new Map(),n=new Map();
      for(let i=0;i<z.length;i++){const g=groups[i];sum.set(g,(sum.get(g)||0)+z[i]);n.set(g,(n.get(g)||0)+1);}
      for(let i=0;i<z.length;i++){const avg=sum.get(groups[i])/n.get(groups[i]);z[i]-=avg;max=Math.max(max,Math.abs(avg));}
    }
    if(max<1e-12) return z;
  }
  throw Error("FWL within-transformation did not converge");
}
function model(rows,w,runExtra=true){
  const n=rows.length,d=rows.map(z=>z.d),t=rows.map(z=>z.yr);
  const Gd=new Set(d).size,Gt=new Set(t).size,k=Gd+Gt;
  const x=residualize(rows.map(z=>z.x[w]),d,t),y=residualize(rows.map(z=>z.y),d,t);
  const xx=x.reduce((s,z)=>s+z*z,0);
  const beta=x.reduce((s,z,i)=>s+z*y[i],0)/xx;
  if(!runExtra)return {beta};
  const sc=x.map((z,i)=>z*(y[i]-beta*z));
  function clustered(group){
    const s=new Map(); for(let i=0;i<n;i++)s.set(group[i],(s.get(group[i])||0)+sc[i]);
    const G=s.size,raw=[...s.values()].reduce((a,v)=>a+v*v,0)/(xx*xx);
    return raw*(G/(G-1))*((n-1)/(n-k));
  }
  const vd=clustered(d),vt=clustered(t),vjoint=clustered(d.map((z,i)=>z+"/"+t[i]));
  const vtwo=vd+vt-vjoint;
  assert(vtwo>0);
  const yearScores=new Map();
  for(let i=0;i<n;i++)yearScores.set(t[i],(yearScores.get(t[i])||0)+sc[i]);
  const ordered=[...yearScores].sort((a,b)=>a[0]-b[0]).map(z=>z[1]);
  function scoreHAC(lag){
    let v=ordered.reduce((s,z)=>s+z*z,0);
    for(let l=1;l<=lag;l++){
      let cross=0;
      for(let i=l;i<ordered.length;i++)cross+=ordered[i]*ordered[i-l];
      v+=2*(1-l/(lag+1))*cross;
    }
    assert(v>0);
    return Math.sqrt(v)/xx;
  }
  const years=[...new Set(t)].sort((a,b)=>a-b);
  const loyo=years.map(yr=>model(rows.filter(r=>r.yr!==yr),w,false).beta);
  const drop3=[],drop5=[];
  for(let start=1983;start<=2018;start++)drop3.push(model(rows.filter(r=>r.yr<start||r.yr>=start+3),w,false).beta);
  for(let start=1983;start<=2016;start++)drop5.push(model(rows.filter(r=>r.yr<start||r.yr>=start+5),w,false).beta);
  assert(loyo.length===38 && drop3.length===36 && drop5.length===34);
  assert([...loyo,...drop3,...drop5].every(v=>v>0));
  return {
    n,nDistrict:Gd,nYears:Gt,beta,seDistrict:Math.sqrt(vd),seYear:Math.sqrt(vt),
    seTwoWay:Math.sqrt(vtwo),yearScoreHAC2:scoreHAC(2),yearScoreHAC3:scoreHAC(3),yearScoreHAC4:scoreHAC(4),
    LOYO_min:Math.min(...loyo),LOYO_max:Math.max(...loyo),
    drop3_min:Math.min(...drop3),drop3_max:Math.max(...drop3),
    drop5_min:Math.min(...drop5),drop5_max:Math.max(...drop5)
  };
}
const r=[];
for(const [cohort,dat] of [["strict16",data.filter(x=>x.strict)],["all23",data]]){
  for(let i=0;i<4;i++){
    const z=model(dat,i);
    assert(Math.abs(z.beta-historical[cohort].beta[i])<1e-10,"beta failed independent baseline");
    assert(Math.abs(z.seDistrict-historical[cohort].district[i])<1e-10,"district SE failed independent baseline");
    assert(Math.abs(z.seYear-historical[cohort].year[i])<1e-10,"year SE failed independent baseline");
    r.push({cohort,window:windows[i],...z});
  }
}
const strict=data.filter(x=>x.strict),grouped=new Map();
for(const d of strict){if(!grouped.has(d.d))grouped.set(d.d,[]);grouped.get(d.d).push(d);}
const ids=[...grouped.keys()];const pairs=[];
function corr(x,y){
  const mx=mean(x),my=mean(y);
  let xx=0,yy=0,xy=0;
  for(let i=0;i<x.length;i++){const a=x[i]-mx,b=y[i]-my;xy+=a*b;xx+=a*a;yy+=b*b;}
  return xy/Math.sqrt(xx*yy);
}
for(let a=0;a<ids.length;a++)for(let b=a+1;b<ids.length;b++){
  const x1=grouped.get(ids[a]),x2=grouped.get(ids[b]);
  const byyear=new Map(x2.map(v=>[v.yr,v]));
  const common=x1.filter(v=>byyear.has(v.yr));
  if(common.length>=20)pairs.push({sameRegion:x1[0].region===x2[0].region,r:corr(common.map(z=>z.x[0]),common.map(z=>byyear.get(z.yr).x[0]))});
}
assert(pairs.length===120 && pairs.every(p=>p.r>0));
const qa={status:"PASS_ALGORITHMIC_WITH_SPATIAL_GATE_OPEN",source_file:path.relative(root,file),
 source_n:data.length,models:r.length,checks:{
  baseline_beta_se_8_out_of_8:"PASS", two_way_positive_variance_8_out_of_8:"PASS",
  leave_one_year_out_38_per_model:"ALL_POSITIVE",
  drop_any_contiguous_3yr_36_per_model:"ALL_POSITIVE",
  drop_any_contiguous_5yr_34_per_model:"ALL_POSITIVE",
  strict16_rainfall_pairs_positive:120,
  mean_pair_rainfall_r:mean(pairs.map(p=>p.r)),
  mean_within_region_r:mean(pairs.filter(p=>p.sameRegion).map(p=>p.r)),
  mean_between_regions_r:mean(pairs.filter(p=>!p.sameRegion).map(p=>p.r))},
 caveats:["No original polygons/centroids: no Conley/adjacency spatial-HAC estimate.",
 "Two-way cluster accounts arbitrary same-year cross-sectional and within-district serial residual dependence, not all cross-district inter-year dependence.",
 "Score HAC is Bartlett/Newey-West on year-aggregated FWL scores, without finite-sample re-scaling; it is sensitivity only.",
 "The independent 16/23 district clusters are few; standard p values not confirmatory.",
 "No treaty variable, no river flow or intake, no causal interpretation.",
 "Within-region rainfall pair correlations are diagnostic, not formal Moran's I."]};
fs.mkdirSync(outdir,{recursive:true});
fs.writeFileSync(path.join(outdir,"stage26_8model_spatiotemporal_se.csv"),
 [["cohort","window","n","nDistrict","nYears","beta","seDistrict","seYear","seTwoWay","yearScoreHAC2","yearScoreHAC3","yearScoreHAC4","LOYO_min","LOYO_max","drop3_min","drop3_max","drop5_min","drop5_max"].join(","),
  ...r.map(z=>Object.values(z).join(","))].join("\n")+"\n");
fs.writeFileSync(path.join(outdir,"stage26_QA.json"),JSON.stringify(qa,null,2)+"\n");
console.log(JSON.stringify({qa,r},null,2));
