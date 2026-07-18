#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import math, numpy as np, pandas as pd
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
ROOT = Path(__file__).resolve().parents[1]; OUT=ROOT/'v7_results'/'optimizer_comparison'; OUT.mkdir(parents=True,exist_ok=True)
SURF=pd.read_csv(ROOT/'results'/'hysteresis_policy_surfaces_all.csv'); SUM=pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv')
SEEDS=range(5); BUDGETS=[12,20,30,44]; EPS=1e-12

def Xcoords(df):
 K=df.alpha_on.max()/.95
 return np.column_stack([df.alpha_on/K,df.alpha_off/K])

def maximin_fill(X,selected,n,seed):
 rng=np.random.default_rng(seed); selected=list(dict.fromkeys(selected))
 if not selected:selected=[int(rng.integers(len(X)))]
 while len(selected)<n:
  rem=np.array([i for i in range(len(X)) if i not in set(selected)],int)
  d=cdist(X[rem],X[selected]).min(axis=1)
  mx=d.max(); ties=rem[np.flatnonzero(np.isclose(d,mx))]
  selected.append(int(rng.choice(ties)))
 return selected

def gp_plain(X,y,se,k,seed):
 seen=maximin_fill(X,[],min(8,k),seed)
 kernel=ConstantKernel(1.,'fixed')*Matern([.2,.2],nu=2.5,length_scale_bounds='fixed')
 while len(seen)<k:
  ids=np.array(seen); yy=y[ids]; scale=max(yy.std(),1e-6); yn=(yy-yy.mean())/scale
  noise=np.maximum(se[ids]/scale,1e-6)**2+1e-6
  gp=GaussianProcessRegressor(kernel=kernel,alpha=noise,optimizer=None,normalize_y=False)
  gp.fit(X[ids],yn)
  rem=np.array([i for i in range(len(X)) if i not in set(seen)])
  mu,sd=gp.predict(X[rem],return_std=True); beta=2+.25*math.log1p(len(seen))
  seen.append(int(rem[np.argmin(mu-beta*sd)]))
 return min(seen,key=lambda i:y[i])

def mech_gp(X,diff,y,se,k,seed):
 # Structural anchors plus low-fidelity minima.
 targets=[(0.05,0.05),(.95,.05),(.95,.95),(.5,.05),(.5,.5)]
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
  beta=2+.25*math.log1p(len(seen)); lcb=pred-beta*scale*sd
  seen.append(int(rem[np.argmin(lcb)]))
 return min(seen,key=lambda i:y[i])

rows=[]
for s in SUM.itertuples():
 df=SURF[SURF.scenario_id==s.scenario_id].sort_values('policy_idx').reset_index(drop=True)
 X=Xcoords(df); y=df.train_objective.to_numpy(); h=df.holdout_objective.to_numpy(); diff=df.diffusion_objective.to_numpy(); se=df.train_objective_ci95_hw.to_numpy()/2.093
 exh=int(s.exhaustive_train_idx); ref=h[exh]
 for k in BUDGETS:
  for seed in SEEDS:
   for method,func in [('GP_BO',gp_plain),('diffusion_residual_GP',mech_gp)]:
    idx=func(X,y,se,k,20260717+seed) if method=='GP_BO' else func(X,diff,y,se,k,20260717+seed)
    rows.append({'scenario_id':s.scenario_id,'method':method,'budget_policies':k,'seed':seed,'selected_idx':idx,'regret':max(0.,(h[idx]-ref)/max(abs(ref),EPS)),'exact':int(idx==exh)})
raw=pd.DataFrame(rows); raw.to_csv(OUT/'mechanistic_gp_runs.csv',index=False)
per=raw.groupby(['scenario_id','method','budget_policies']).agg(median_regret=('regret','median'),p90_seed_regret=('regret',lambda x:x.quantile(.9)),success_1=('regret',lambda x:(x<=.01).mean()),success_5=('regret',lambda x:(x<=.05).mean()),exact=('exact','mean')).reset_index()
per.to_csv(OUT/'mechanistic_gp_by_scenario.csv',index=False)
summ=per.groupby(['method','budget_policies']).agg(median_regret=('median_regret','median'),p90_regret=('median_regret',lambda x:x.quantile(.9)),max_regret=('median_regret','max'),mean_success_1=('success_1','mean'),mean_success_5=('success_5','mean'),mean_exact=('exact','mean')).reset_index()
summ.to_csv(OUT/'mechanistic_gp_summary.csv',index=False)
print(summ.to_string(index=False))
