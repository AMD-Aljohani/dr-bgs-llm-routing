#!/usr/bin/env python3
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import qmc
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel

ROOT = Path(__file__).resolve().parents[1]
RES=ROOT/'results'
OUT=ROOT/'v7_results'/'optimizer_comparison'
OUT.mkdir(parents=True,exist_ok=True)
SURF=pd.read_csv(RES/'hysteresis_policy_surfaces_all.csv')
SUM=pd.read_csv(RES/'hysteresis_summary_all.csv')
SEEDS=range(5)
EPS=1e-12


def coords(df):
    K=max(df.alpha_on.max()/0.95,EPS)
    return np.column_stack([df.alpha_on/K,df.alpha_off/K])


def maximin_initial(X,n,seed):
    rng=np.random.default_rng(seed)
    selected=[int(rng.integers(len(X)))]
    while len(selected)<n:
        rem=np.array([i for i in range(len(X)) if i not in selected],int)
        d=cdist(X[rem],X[selected]).min(axis=1)
        selected.append(int(rem[np.argmax(d)]))
    return selected


def random_rs(train,k,seed):
    rng=np.random.default_rng(seed)
    ids=rng.choice(len(train),size=min(k,len(train)),replace=False)
    return int(ids[np.argmin(train[ids])]),list(map(int,ids))


def diffusion_topk(diff,train,k):
    ids=np.argsort(diff)[:k]
    return int(ids[np.argmin(train[ids])]),list(map(int,ids))


def local_search(df,train,k,seed):
    X=coords(df); n=len(df); rng=np.random.default_rng(seed)
    # Map grid coordinate ranks.
    ons=sorted(df.alpha_on.unique()); offs=sorted(df.alpha_off.unique())
    idx={(float(r.alpha_on),float(r.alpha_off)):int(r.policy_idx) for r in df.itertuples()}
    center=min(range(n),key=lambda i: abs(X[i,0]-.5)+abs(X[i,1]-.4))
    explored=[]; seen=set(); current=center
    while len(seen)<k:
        if current not in seen:
            seen.add(current); explored.append(current)
        row=df.iloc[current]; oi=ons.index(row.alpha_on); fj=offs.index(row.alpha_off)
        neigh=[]
        for di,dj in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
            ni,nj=oi+di,fj+dj
            if 0<=ni<len(ons) and 0<=nj<len(offs) and offs[nj]<=ons[ni]:
                p=idx.get((float(ons[ni]),float(offs[nj])))
                if p is not None and p not in seen: neigh.append(p)
        for p in neigh:
            if len(seen)>=k: break
            seen.add(p); explored.append(p)
        best=min(seen,key=lambda i:train[i])
        if best==current or len(neigh)==0:
            rem=[i for i in range(n) if i not in seen]
            if not rem: break
            # Restart at farthest unexplored point from explored set.
            d=cdist(X[rem],X[list(seen)]).min(axis=1)
            current=int(rem[np.argmax(d)])
        else:
            current=best
    ids=list(seen)
    return int(min(ids,key=lambda i:train[i])),ids


def gp_bo(df,train,train_hw,k,seed):
    X=coords(df); n=len(df); rng=np.random.default_rng(seed)
    init=maximin_initial(X,min(8,k),seed)
    seen=list(init)
    kernel=ConstantKernel(1.0,constant_value_bounds='fixed')*Matern(length_scale=[.2,.2],nu=2.5,length_scale_bounds='fixed')
    while len(seen)<k:
        ids=np.array(seen,int)
        y=train[ids]
        scale=max(np.std(y),1e-6)
        yn=(y-y.mean())/scale
        # Recover approximate standard error from 95% half-width; stabilize.
        se=np.maximum(train_hw[ids]/2.093,1e-6)/scale
        gp=GaussianProcessRegressor(kernel=kernel,alpha=se**2+1e-6,normalize_y=False,optimizer=None,random_state=seed)
        gp.fit(X[ids],yn)
        rem=np.array([i for i in range(n) if i not in set(seen)],int)
        mu,sd=gp.predict(X[rem],return_std=True)
        beta=2.0+0.25*math.log1p(len(seen))
        lcb=mu-beta*sd
        # Small seeded jitter only for exact ties.
        nxt=int(rem[np.argmin(lcb+1e-10*rng.standard_normal(len(rem)))])
        seen.append(nxt)
    return int(min(seen,key=lambda i:train[i])),seen

rows=[]
for srow in SUM.itertuples():
    sid=srow.scenario_id
    df=SURF[SURF.scenario_id==sid].sort_values('policy_idx').reset_index(drop=True)
    train=df.train_objective.to_numpy(float); hold=df.holdout_objective.to_numpy(float)
    hw=df.train_objective_ci95_hw.to_numpy(float); diff=df.diffusion_objective.to_numpy(float)
    idx_exh=int(srow.exhaustive_train_idx); idx_migr=int(srow.final_idx)
    exh_hold=hold[idx_exh]
    train_budget=max(int(srow.algorithm_simulation_count)-30,20)
    k=max(1,min(len(df),train_budget//20))
    # deterministic methods
    methods=[]
    methods.append(('diffusion_topk',0,*diffusion_topk(diff,train,k)))
    methods.append(('high_fidelity_local_search',0,*local_search(df,train,k,20260717)))
    methods.append(('MIGR_H',0,idx_migr,[]))
    methods.append(('exhaustive',0,idx_exh,list(range(len(df)))))
    for seed in SEEDS:
        methods.append(('random_RS',seed,*random_rs(train,k,20260717+seed)))
        methods.append(('GP_BO',seed,*gp_bo(df,train,hw,k,20260717+seed)))
    for method,seed,idx,visited in methods:
        obj=hold[idx]
        rows.append({
            'scenario_id':sid,'design':srow.design,'method':method,'seed':seed,
            'equal_budget_replications':train_budget,'policy_evaluation_budget':k,
            'selected_idx':idx,'selected_alpha_on':df.iloc[idx].alpha_on,
            'selected_alpha_off':df.iloc[idx].alpha_off,
            'visited_policies':len(visited) if visited else (srow.selection_candidate_count if method=='MIGR_H' else 190),
            'holdout_objective':obj,'exhaustive_holdout_objective':exh_hold,
            'regret_vs_exhaustive':max(0.0,(obj-exh_hold)/max(abs(exh_hold),EPS)),
            'exact_match':int(idx==idx_exh),
        })

raw=pd.DataFrame(rows); raw.to_csv(OUT/'equal_budget_optimizer_runs.csv',index=False)
# Aggregate random methods first across seeds per scenario to avoid overweighting.
per=[]
for (sid,method),g in raw.groupby(['scenario_id','method']):
    per.append({'scenario_id':sid,'method':method,
                'median_regret_across_seeds':g.regret_vs_exhaustive.median(),
                'p90_regret_across_seeds':g.regret_vs_exhaustive.quantile(.9),
                'success_1pct_across_seeds':(g.regret_vs_exhaustive<=.01).mean(),
                'success_5pct_across_seeds':(g.regret_vs_exhaustive<=.05).mean(),
                'exact_match_across_seeds':g.exact_match.mean(),
                'policy_evaluation_budget':g.policy_evaluation_budget.iloc[0]})
per=pd.DataFrame(per); per.to_csv(OUT/'equal_budget_optimizer_by_scenario.csv',index=False)
summary=[]
for method,g in per.groupby('method'):
    summary.append({'method':method,'scenarios':len(g),
                    'median_regret':g.median_regret_across_seeds.median(),
                    'p90_regret':g.median_regret_across_seeds.quantile(.9),
                    'max_median_regret':g.median_regret_across_seeds.max(),
                    'mean_run_success_1pct':g.success_1pct_across_seeds.mean(),
                    'mean_run_success_5pct':g.success_5pct_across_seeds.mean(),
                    'mean_exact_match':g.exact_match_across_seeds.mean(),
                    'median_policy_budget':g.policy_evaluation_budget.median()})
summary=pd.DataFrame(summary).sort_values(['p90_regret','median_regret'])
summary.to_csv(OUT/'equal_budget_optimizer_summary.csv',index=False)
print(summary.to_string(index=False))
