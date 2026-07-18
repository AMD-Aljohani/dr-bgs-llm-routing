#!/usr/bin/env python3
from __future__ import annotations
import glob, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT=ROOT/'v7_results'/'robust_pareto'; OUT.mkdir(parents=True,exist_ok=True)
base=pd.read_csv(ROOT/'results'/'hysteresis_policy_surfaces_all.csv')
fresh=pd.concat([pd.read_csv(p) for p in sorted(glob.glob(str(ROOT/'v7_results/fresh59/T*_policy_surface.csv')))],ignore_index=True)
allp=pd.concat([base,fresh],ignore_index=True)
allp.to_csv(OUT/'all_95_policy_surfaces.csv',index=False)

# Full step-0.1 simplex grid has 286 profiles; equal weights add one more.
W=[]
for a in range(11):
 for b in range(11-a):
  for c in range(11-a-b):
   d=10-a-b-c
   W.append([a/10,b/10,c/10,d/10])
W=np.vstack([np.array(W,float),np.full((1,4),0.25)])
pd.DataFrame(W,columns=['w_W','w_BH','w_BL','w_cloud']).to_csv(OUT/'weight_profiles_287.csv',index=False)

def pareto(Y):
 n=len(Y); eff=np.ones(n,bool)
 for i in range(n):
  if not eff[i]: continue
  dom=np.all(Y<=Y[i]+1e-12,axis=1)&np.any(Y<Y[i]-1e-12,axis=1)
  if dom.any(): eff[i]=False
 return np.where(eff)[0]

rows=[]; pareto_rows=[]
for sid,g in allp.groupby('scenario_id'):
 g=g.sort_values('policy_idx').reset_index(drop=True)
 Y=g[['holdout_W','holdout_B_H','holdout_B_L','holdout_cloud_fraction']].to_numpy(float)
 lo=Y.min(axis=0); hi=Y.max(axis=0); Yn=(Y-lo)/np.maximum(hi-lo,1e-12)
 costs=Yn@W.T
 bestcost=costs.min(axis=0); bestidx=np.argmin(costs,axis=0)
 regret=costs-bestcost[None,:]
 worst=regret.max(axis=1); avg=regret.mean(axis=1)
 robust=int(np.argmin(worst)); eq_profile=int(np.where(np.all(np.isclose(W,.25),axis=1))[0][0]); equal=int(bestidx[eq_profile])
 pidx=pareto(Yn)
 distinct=len(np.unique(bestidx))
 eq_worst=float(worst[equal]); robust_worst=float(worst[robust])
 eq_profile_cost_penalty=float(costs[robust,eq_profile]-bestcost[eq_profile])
 # stakeholder-profile regret of equal and robust policies
 equal_bad5=float((regret[equal]>.05).mean()); robust_bad5=float((regret[robust]>.05).mean())
 rows.append({
  'scenario_id':sid,'design':g.design.iloc[0],'policy_count':len(g),
  'pareto_count':len(pidx),'pareto_fraction':len(pidx)/len(g),
  'distinct_optima_287':distinct,'equal_weight_idx':equal,'robust_idx':robust,
  'robust_is_pareto':int(robust in set(pidx)),'robust_differs_from_equal':int(robust!=equal),
  'equal_weight_max_normalized_regret':eq_worst,
  'robust_max_normalized_regret':robust_worst,
  'max_regret_reduction':(eq_worst-robust_worst)/max(eq_worst,1e-12),
  'robust_equal_weight_penalty':eq_profile_cost_penalty,
  'equal_profile_fraction_regret_gt_5pct':equal_bad5,
  'robust_profile_fraction_regret_gt_5pct':robust_bad5,
  'equal_alpha_on':g.iloc[equal].alpha_on,'equal_alpha_off':g.iloc[equal].alpha_off,
  'robust_alpha_on':g.iloc[robust].alpha_on,'robust_alpha_off':g.iloc[robust].alpha_off,
 })
 for i in pidx:
  pareto_rows.append({'scenario_id':sid,'policy_idx':int(i),'alpha_on':g.iloc[i].alpha_on,'alpha_off':g.iloc[i].alpha_off,**{f'norm_{k}':Yn[i,j] for j,k in enumerate(['W','BH','BL','cloud'])}})

res=pd.DataFrame(rows); res.to_csv(OUT/'robust_pareto_by_scenario.csv',index=False)
pd.DataFrame(pareto_rows).to_csv(OUT/'pareto_policy_sets.csv',index=False)
summary={
 'scenario_count':len(res), 'weight_profile_count':len(W),
 'median_pareto_count':float(res.pareto_count.median()),
 'p90_pareto_count':float(res.pareto_count.quantile(.9)),
 'median_distinct_optima':float(res.distinct_optima_287.median()),
 'p90_distinct_optima':float(res.distinct_optima_287.quantile(.9)),
 'robust_differs_from_equal_fraction':float(res.robust_differs_from_equal.mean()),
 'robust_is_pareto_fraction':float(res.robust_is_pareto.mean()),
 'median_equal_weight_max_regret':float(res.equal_weight_max_normalized_regret.median()),
 'median_robust_max_regret':float(res.robust_max_normalized_regret.median()),
 'median_max_regret_reduction':float(res.max_regret_reduction.median()),
 'median_equal_weight_penalty_of_robust':float(res.robust_equal_weight_penalty.median()),
 'median_equal_fraction_profiles_over_5pct':float(res.equal_profile_fraction_regret_gt_5pct.median()),
 'median_robust_fraction_profiles_over_5pct':float(res.robust_profile_fraction_regret_gt_5pct.median()),
}
(OUT/'robust_pareto_summary.json').write_text(json.dumps(summary,indent=2))
pd.DataFrame([summary]).to_csv(OUT/'robust_pareto_summary.csv',index=False)
print(json.dumps(summary,indent=2))
