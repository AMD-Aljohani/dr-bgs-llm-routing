#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import qmc, t as student_t

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))
import run_smpt_campaign as core  # noqa: E402

SEED = 20260716
LEVEL_COUNT = 19
TRAIN_REPS = 20
SELECT_REPS = 8
HOLDOUT_REPS = 30
TRAIN_HORIZON = 900.0
TRAIN_BURN = 225.0
HOLDOUT_HORIZON = 1200.0
HOLDOUT_BURN = 300.0
CERT_STAGES = (3, 6, 10, 15, 20, 30)
CERT_EPS_REL = 0.05
CERT_DELTA = 0.05
CERT_HORIZON = 1200.0
CERT_BURN = 300.0
FALLBACK_REPS = 20
EPS = 1e-12


def maximin_subset(df: pd.DataFrame, features: List[str], n: int) -> List[str]:
    X = df[features].to_numpy(float)
    lo = X.min(axis=0); hi = X.max(axis=0)
    X = (X - lo) / np.maximum(hi - lo, 1e-12)
    # Start with the point farthest from the center, then greedily maximize minimum distance.
    center = np.full(X.shape[1], 0.5)
    selected = [int(np.argmax(np.linalg.norm(X-center, axis=1)))]
    while len(selected) < n:
        remaining = [i for i in range(len(X)) if i not in selected]
        dmin = []
        for i in remaining:
            dmin.append(min(np.linalg.norm(X[i]-X[j]) for j in selected))
        selected.append(remaining[int(np.argmax(dmin))])
    return df.iloc[selected].scenario_id.tolist()


def existing_development_scenarios() -> List[core.Scenario]:
    scenarios = core.build_scenarios(SEED)
    df = pd.DataFrame([asdict(s) for s in scenarios])
    feats = ['rho','arrival_scv','mean_jump_fraction','tau','qH','beta',
             'jump_cv','cloud_cost_multiplier','deactivation_mean','K']
    fids = maximin_subset(df[df.design=='factorial'].reset_index(drop=True), feats, 12)
    rids = maximin_subset(df[df.design=='lhs'].reset_index(drop=True), feats, 12)
    keep = set(fids+rids)
    return [s for s in scenarios if s.scenario_id in keep]


def fresh_validation_scenarios(seed: int = 20260901, n: int = 12) -> List[core.Scenario]:
    sampler = qmc.LatinHypercube(d=10, seed=seed)
    U = sampler.random(n)
    out=[]
    for j,u in enumerate(U,1):
        K = 30 + 50*u[9]
        mu = 3*K
        rho = 0.55 + 0.35*u[0]
        scv = 1.0 if u[1] < 0.5 else 4.0
        mf = 0.05 + 0.05*u[2]
        tau = math.exp(math.log(.25)+u[3]*(math.log(4)-math.log(.25)))
        qh = .2 + .6*u[4]
        beta = .6 + .8*u[5]
        jcv = .5 + 1.5*u[6]
        ccm = math.exp(math.log(.25)+u[7]*(math.log(4)-math.log(.25)))
        dm = .25 + 1.75*u[8]
        m = mf*K; mH=1.15*m; mL=.85*m
        inp=rho*mu
        out.append(core.Scenario(
            scenario_id=f'V{j:02d}', design='fresh_lhs', K=K, mu_max=mu,
            rho=rho, arrival_scv=scv, mean_jump_fraction=mf, tau=tau,
            qH=qh, beta=beta, jump_cv=jcv, cloud_cost_multiplier=ccm,
            deactivation_mean=dm,
            lambda_H=(qh*inp)/mH, lambda_L=((1-qh)*inp)/mL,
            mean_H=mH, mean_L=mL, cv_H=jcv, cv_L=jcv,
        ))
    return out


def policy_grid(s: core.Scenario):
    levels=np.linspace(.05*s.K,.95*s.K,LEVEL_COUNT)
    pairs=[]; ij=[]
    for i,on in enumerate(levels):
        for j,off in enumerate(levels[:i+1]):
            pairs.append((float(on),float(off))); ij.append((i,j))
    return levels,pairs,ij


def mean_hw(x: np.ndarray, confidence=.95):
    x=np.asarray(x,float); m=float(x.mean())
    if len(x)<2: return m,float('nan')
    hw=float(student_t.ppf((1+confidence)/2,len(x)-1)*x.std(ddof=1)/math.sqrt(len(x)))
    return m,hw


def simulate_policy_array(s, pairs, streams, horizon, burn, seed_base, metrics=False):
    nP=len(pairs); nR=len(streams)
    obj=np.empty((nP,nR),float)
    metric_names=['W','B_H','B_L','cloud_fraction','activation_rate','objective']
    met={k:np.empty((nP,nR),float) for k in metric_names} if metrics else None
    for i,(on,off) in enumerate(pairs):
        for r,st in enumerate(streams):
            z=core.sim_threshold(s,st,horizon,burn,on,off,seed_base+1009*r)
            obj[i,r]=z['objective']
            if metrics:
                for k in metric_names: met[k][i,r]=z[k]
    return obj,met


def candidate_selection(diff_obj: np.ndarray, train_obj: np.ndarray, ij: List[Tuple[int,int]]):
    # Model-informed, geometry-guarded candidate selection.
    index={p:i for i,p in enumerate(ij)}
    order=np.argsort(diff_obj)
    cand=set(map(int,order[:8]))
    guards=[(0,0),(1,0),(18,0),(18,18),(18,17),(9,0),(9,9),(18,9),(10,9)]
    for p in guards:
        if p in index: cand.add(index[p])
    for i in range(LEVEL_COUNT):
        cand.add(index[(i,i)])
    for idx in order[:3]:
        i,j=ij[int(idx)]
        for di,dj in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1)]:
            q=(i+di,j+dj)
            if q in index: cand.add(index[q])
    means={i:float(train_obj[i,:SELECT_REPS].mean()) for i in cand}
    for _ in range(3):
        best=min(means,key=means.get); bi,bj=ij[best]
        new=set()
        for di in range(-2,3):
            for dj in range(-2,3):
                q=(bi+di,bj+dj)
                if q in index: new.add(index[q])
        ids=np.array(sorted(means),int)
        x=diff_obj[ids]; y=np.array([means[i] for i in ids])
        A=np.column_stack([np.ones(len(ids)),x])
        coef=np.linalg.lstsq(A,y,rcond=None)[0]
        pred=coef[0]+coef[1]*diff_obj
        new.update(map(int,np.argsort(pred)[:7]))
        new.update(map(int,order[:12]))
        new=[i for i in new if i not in means]
        if not new: break
        for i in new:
            means[i]=float(train_obj[i,:SELECT_REPS].mean())
        if len(means)>=48: break
    selected=min(means,key=means.get)
    return int(selected),sorted(means),means


def certify_explored_set(s, pairs, candidate_ids, selected_idx, scenario_index, seed_offset=0):
    """Nominal 95% simultaneous 5%-indifference certificate on the explored set.

    The selected policy is fixed using independent selection streams. Certification
    uses paired common-random-number streams. A one-sided Bonferroni correction is
    applied across candidates and planned looks. If the certificate is not achieved,
    the procedure falls back to the lowest 20-replication mean within the explored set.
    Global performance is assessed separately against the exhaustive 190-policy benchmark.
    """
    ids=sorted(set(map(int,candidate_ids)))
    active=set(ids); active.discard(selected_idx)
    samples: Dict[int,List[float]]={i:[] for i in ids}
    total=0; prev=0; stage_reached=0
    comp=max(len(ids)-1,1)
    alpha=CERT_DELTA/(len(CERT_STAGES)*comp)
    for n in CERT_STAGES[:-1]:  # planned looks through 20 reps
        new_streams=[core.generate_stream(
            s,SEED+seed_offset+31_000_000+100_000*scenario_index+149*r,CERT_HORIZON
        ) for r in range(prev,n)]
        eval_ids=[selected_idx]+sorted(active)
        for i in eval_ids:
            on,off=pairs[i]
            for rr,st in enumerate(new_streams,start=prev):
                z=core.sim_threshold(s,st,CERT_HORIZON,CERT_BURN,on,off,
                                     SEED+seed_offset+2_700_000*scenario_index+1009*rr)
                samples[i].append(z['objective']); total+=1
        mean_sel=float(np.mean(samples[selected_idx])); eps_abs=CERT_EPS_REL*abs(mean_sel)
        crit=float(student_t.ppf(1-alpha,n-1))
        clear=[]
        for i in active:
            d=np.asarray(samples[selected_idx])-np.asarray(samples[i])
            u=float(d.mean()+crit*d.std(ddof=1)/math.sqrt(n))
            if u<=eps_abs: clear.append(i)
        for i in clear: active.remove(i)
        prev=n; stage_reached=n
        if not active:
            return {'certified':1,'fallback':0,'final_idx':selected_idx,
                    'stage_reached':stage_reached,'ambiguous_count':0,
                    'simulation_count':total,'samples':samples}
    # Complete every explored policy to 20 replications and select the best.
    target=20
    for r in range(3,target):
        st=core.generate_stream(s,SEED+seed_offset+31_000_000+100_000*scenario_index+149*r,CERT_HORIZON)
        for i in ids:
            if len(samples[i])<=r:
                on,off=pairs[i]
                z=core.sim_threshold(s,st,CERT_HORIZON,CERT_BURN,on,off,
                                     SEED+seed_offset+2_700_000*scenario_index+1009*r)
                samples[i].append(z['objective']); total+=1
    means={i:float(np.mean(samples[i][:target])) for i in ids}
    final_idx=min(means,key=means.get)
    return {'certified':0,'fallback':1,'final_idx':int(final_idx),
            'stage_reached':stage_reached,'ambiguous_count':len(active),
            'simulation_count':total,'samples':samples}


def pareto_indices(Y: np.ndarray):
    n=len(Y); efficient=np.ones(n,dtype=bool)
    for i in range(n):
        if not efficient[i]: continue
        dominates=np.all(Y<=Y[i]+1e-12,axis=1)&np.any(Y<Y[i]-1e-12,axis=1)
        if dominates.any(): efficient[i]=False
    return np.where(efficient)[0]


def weight_robust_analysis(metrics: Dict[str,np.ndarray], seed: int):
    Y=np.column_stack([
        metrics['W'].mean(axis=1), metrics['B_H'].mean(axis=1),
        metrics['B_L'].mean(axis=1), metrics['cloud_fraction'].mean(axis=1)
    ])
    lo=Y.min(axis=0); hi=Y.max(axis=0); Yn=(Y-lo)/np.maximum(hi-lo,1e-12)
    rng=np.random.default_rng(seed)
    weights=np.vstack([
        np.eye(4),
        np.full((1,4),.25),
        rng.dirichlet(np.ones(4),size=24),
    ])
    costs=Yn@weights.T
    best=np.argmin(costs,axis=0)
    regret=costs-costs.min(axis=0,keepdims=True)
    worst=regret.max(axis=1)
    robust=int(np.argmin(worst))
    return {
        'pareto_count':int(len(pareto_indices(Yn))),
        'distinct_weight_optima':int(len(np.unique(best))),
        'robust_idx':robust,
        'robust_max_additive_regret':float(worst[robust]),
        'equal_weight_idx':int(np.argmin(Yn.mean(axis=1))),
    }


def run_scenario(s: core.Scenario, scenario_index: int, outdir: Path, seed_offset: int):
    t0=time.time(); levels,pairs,ij=policy_grid(s); M=len(pairs)
    # Diffusion low-fidelity surface.
    diff_rows=[]
    for i,(on,off) in enumerate(pairs):
        z=core.diffusion_metrics(s,on,off,N=161)
        diff_rows.append({'policy_idx':i,'alpha_on':on,'alpha_off':off,**z})
    diff_df=pd.DataFrame(diff_rows); diff_obj=diff_df.objective.to_numpy()

    train_streams=[core.generate_stream(s,SEED+seed_offset+11_000_000+100_000*scenario_index+137*r,TRAIN_HORIZON)
                   for r in range(TRAIN_REPS)]
    hold_streams=[core.generate_stream(s,SEED+seed_offset+21_000_000+100_000*scenario_index+139*r,HOLDOUT_HORIZON)
                  for r in range(HOLDOUT_REPS)]
    train_obj,_=simulate_policy_array(s,pairs,train_streams,TRAIN_HORIZON,TRAIN_BURN,
                                      SEED+seed_offset+700_000*scenario_index)
    hold_obj,hold_met=simulate_policy_array(s,pairs,hold_streams,HOLDOUT_HORIZON,HOLDOUT_BURN,
                                            SEED+seed_offset+1_700_000*scenario_index,metrics=True)

    # Diagonal single-threshold benchmark on the same streams.
    diagonal=[(float(a),float(a)) for a in levels]
    single_train,_=simulate_policy_array(s,diagonal,train_streams,TRAIN_HORIZON,TRAIN_BURN,
                                         SEED+seed_offset+3_700_000*scenario_index)
    single_hold,single_met=simulate_policy_array(s,diagonal,hold_streams,HOLDOUT_HORIZON,HOLDOUT_BURN,
                                                 SEED+seed_offset+4_700_000*scenario_index,metrics=True)

    idx_exh=int(np.argmin(train_obj.mean(axis=1)))
    idx_hold_oracle=int(np.argmin(hold_obj.mean(axis=1)))
    idx_single=int(np.argmin(single_train.mean(axis=1)))
    selected_idx,candidates,selection_means=candidate_selection(diff_obj,train_obj,ij)
    cert=certify_explored_set(s,pairs,candidates,selected_idx,scenario_index,seed_offset=seed_offset)
    final_idx=int(cert['final_idx'])

    hold_mean=hold_obj.mean(axis=1)
    exh_hold=float(hold_mean[idx_exh]); oracle_hold=float(hold_mean[idx_hold_oracle])
    final_hold=float(hold_mean[final_idx]); single_hold_obj=float(single_hold.mean(axis=1)[idx_single])
    regret_exh=max(0.0,(final_hold-exh_hold)/max(abs(exh_hold),EPS))
    regret_oracle=max(0.0,(final_hold-oracle_hold)/max(abs(oracle_hold),EPS))
    hyst_gain=(single_hold_obj-exh_hold)/max(abs(single_hold_obj),EPS)
    adaptive_gain=(single_hold_obj-final_hold)/max(abs(single_hold_obj),EPS)

    selection_work=len(candidates)*SELECT_REPS
    algorithm_work=selection_work+int(cert['simulation_count'])+HOLDOUT_REPS
    exhaustive_work=M*TRAIN_REPS+HOLDOUT_REPS
    work_reduction=1-algorithm_work/exhaustive_work

    robust=weight_robust_analysis(hold_met,SEED+seed_offset+scenario_index)

    policy_rows=[]
    for i,(on,off) in enumerate(pairs):
        row={
            'scenario_id':s.scenario_id,'design':s.design,'policy_idx':i,
            'alpha_on':on,'alpha_off':off,'gap_fraction':(on-off)/s.K,
            'diffusion_objective':diff_obj[i],
            'train_objective':float(train_obj[i].mean()),
            'train_objective_ci95_hw':mean_hw(train_obj[i])[1],
            'holdout_objective':float(hold_obj[i].mean()),
            'holdout_objective_ci95_hw':mean_hw(hold_obj[i])[1],
        }
        for k in ['W','B_H','B_L','cloud_fraction','activation_rate']:
            row['holdout_'+k]=float(hold_met[k][i].mean())
        policy_rows.append(row)
    pd.DataFrame(policy_rows).to_csv(outdir/f'{s.scenario_id}_policy_surface.csv',index=False)

    summary={
        **asdict(s), 'policy_count':M,
        'diffusion_best_idx':int(np.argmin(diff_obj)),
        'exhaustive_train_idx':idx_exh,'holdout_oracle_idx':idx_hold_oracle,
        'single_train_idx':idx_single,'selection_idx':selected_idx,'final_idx':final_idx,
        'selection_candidate_count':len(candidates),
        'certified':cert['certified'],'fallback':cert['fallback'],
        'certificate_stage_reps':cert['stage_reached'],
        'certificate_ambiguous_count':cert['ambiguous_count'],
        'certificate_simulation_count':cert['simulation_count'],
        'algorithm_simulation_count':algorithm_work,
        'exhaustive_simulation_count':exhaustive_work,
        'work_reduction':work_reduction,
        'holdout_regret_vs_exhaustive':regret_exh,
        'holdout_regret_vs_oracle':regret_oracle,
        'hysteresis_gain_vs_best_single':hyst_gain,
        'adaptive_gain_vs_best_single':adaptive_gain,
        'exhaustive_holdout_objective':exh_hold,
        'adaptive_holdout_objective':final_hold,
        'single_holdout_objective':single_hold_obj,
        'selected_alpha_on':pairs[final_idx][0],
        'selected_alpha_off':pairs[final_idx][1],
        'exhaustive_alpha_on':pairs[idx_exh][0],
        'exhaustive_alpha_off':pairs[idx_exh][1],
        **robust,
        'elapsed_seconds':time.time()-t0,
    }
    Path(outdir/f'{s.scenario_id}_summary.json').write_text(json.dumps(summary,indent=2))
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--design',choices=['development','fresh'],required=True)
    ap.add_argument('--start',type=int,default=0)
    ap.add_argument('--count',type=int,default=None)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    scenarios=existing_development_scenarios() if args.design=='development' else fresh_validation_scenarios()
    scenarios=scenarios[args.start: args.start+args.count if args.count is not None else None]
    rows=[]
    seed_offset=0 if args.design=='development' else 500_000_000
    for local,s in enumerate(scenarios):
        global_idx=args.start+local+1
        row=run_scenario(s,global_idx,out,seed_offset)
        rows.append(row)
        print(f"[{args.design} {global_idx:02d}] {s.scenario_id}: cert={row['certified']} "
              f"fallback={row['fallback']} save={row['work_reduction']:.1%} "
              f"regret={row['holdout_regret_vs_exhaustive']:.2%} "
              f"hyst_gain={row['hysteresis_gain_vs_best_single']:.2%}",flush=True)
    pd.DataFrame(rows).to_csv(out/f'summary_{args.design}_{args.start:02d}.csv',index=False)

if __name__=='__main__':
    main()
