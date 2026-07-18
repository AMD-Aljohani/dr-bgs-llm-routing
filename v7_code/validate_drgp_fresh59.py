#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import glob, math, numpy as np, pandas as pd
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
ROOT = Path(__file__).resolve().parents[1]; OUT=ROOT/'v7_results'/'fresh59_drgp'; OUT.mkdir(parents=True,exist_ok=True)
SEEDS=range(5); BUDGET=20; EPS=1e-12

def coords(df):
 K=df.alpha_on.max()/.95
 return np.column_stack([df.alpha_on/K,df.alpha_off/K])

def maximin_fill(X,selected,n,seed):
 rng=np.random.default_rng(seed); selected=list(dict.fromkeys(selected))
 if not selected:selected=[int(rng.integers(len(X)))]
 while len(selected)<n:
  rem=np.array([i for i in range(len(X)) if i not in set(selected)],int)
  d=cdist(X[rem],X[selected]).min(axis=1); mx=d.max(); ties=rem[np.flatnonzero(np.isclose(d,mx))]
  selected.append(int(rng.choice(ties)))
 return selected

def drgp(X,diff,y,se,k,seed):
 targets=[(.05,.05),(.95,.05),(.95,.95),(.5,.05),(.5,.5)]
 anchors=[int(np.argmin(np.linalg.norm(X-np.array(t),axis=1))) for t in targets]
 anchors+=list(map(int,np.argsort(diff)[:3]))
 seen=maximin_fill(X,anchors,min(max(8,len(set(anchors))),k),seed)
 kernel=ConstantKernel(1.,'fixed')*Matern([.2,.2],nu=2.5,length_scale_bounds='fixed')
 while len(seen)<k:
  ids=np.array(seen); A=np.column_stack([np.ones(len(ids)),diff[ids]])
  coef=np.linalg.lstsq(A,y[ids],rcond=None)[0]; trend=coef[0]+coef[1]*diff
  resid=y[ids]-trend[ids]; scale=max(resid.std(),1e-6); rn=resid/scale
  noise=np.maximum(se[ids]/scale,1e-6)**2+1e-6
  gp=GaussianProcessRegressor(kernel=kernel,alpha=noise,optimizer=None,normalize_y=False)
  gp.fit(X[ids],rn)
  rem=np.array([i for i in range(len(X)) if i not in set(seen)])
  mu,sd=gp.predict(X[rem],return_std=True); pred=trend[rem]+scale*mu
  beta=2+.25*math.log1p(len(seen)); seen.append(int(rem[np.argmin(pred-beta*scale*sd)]))
 return min(seen,key=lambda i:y[i])

rows=[]
for p in sorted(glob.glob(str(ROOT/'v7_results/fresh59/T*_policy_surface.csv'))):
 df=pd.read_csv(p).sort_values('policy_idx').reset_index(drop=True); sid=df.scenario_id.iloc[0]
 X=coords(df); y=df.train_objective.to_numpy(); h=df.holdout_objective.to_numpy(); d=df.diffusion_objective.to_numpy(); se=df.train_objective_ci95_hw.to_numpy()/2.093
 idx_exh=int(np.argmin(y)); ref=h[idx_exh]
 for seed in SEEDS:
  idx=drgp(X,d,y,se,BUDGET,20260717+seed)
  rows.append({'scenario_id':sid,'seed':seed,'selected_idx':idx,'exhaustive_idx':idx_exh,'holdout_objective':h[idx],'reference_objective':ref,'regret':max(0.,(h[idx]-ref)/max(abs(ref),EPS)),'exact':int(idx==idx_exh)})
raw=pd.DataFrame(rows); raw.to_csv(OUT/'fresh59_drgp_runs.csv',index=False)
per=raw.groupby('scenario_id').agg(median_regret=('regret','median'),max_seed_regret=('regret','max'),success_1=('regret',lambda x:(x<=.01).mean()),success_5=('regret',lambda x:(x<=.05).mean()),exact=('exact','mean')).reset_index()
per.to_csv(OUT/'fresh59_drgp_by_scenario.csv',index=False)
summary={'scenarios':len(per),'runs':len(raw),'budget_policies':BUDGET,'work_reduction_vs_exhaustive':1-(BUDGET*20+30)/(190*20+30),'median_scenario_regret':float(per.median_regret.median()),'p90_scenario_regret':float(per.median_regret.quantile(.9)),'max_scenario_median_regret':float(per.median_regret.max()),'all_run_max_regret':float(raw.regret.max()),'all_run_success_1pct':float((raw.regret<=.01).mean()),'all_run_success_5pct':float((raw.regret<=.05).mean()),'all_scenarios_all_seeds_within_5pct':bool((per.max_seed_regret<=.05).all()),'mean_exact_match':float(raw.exact.mean())}
pd.DataFrame([summary]).to_csv(OUT/'fresh59_drgp_summary.csv',index=False)
print(summary)
