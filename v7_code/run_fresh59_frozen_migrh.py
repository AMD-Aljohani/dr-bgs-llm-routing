#!/usr/bin/env python3
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
import pandas as pd
from scipy.stats import qmc

V7 = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(V7/'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as migr

DESIGN_SEED=20261017
SEED_OFFSET=900_000_000
N=59

def scenarios(n=N, seed=DESIGN_SEED):
    sampler=qmc.LatinHypercube(d=10, seed=seed)
    U=sampler.random(n)
    out=[]
    for j,u in enumerate(U,1):
        K=30+50*u[9]; mu=3*K
        rho=.55+.35*u[0]
        scv=1.0 if u[1] < .5 else 4.0
        mf=.05+.05*u[2]
        tau=math.exp(math.log(.25)+u[3]*(math.log(4)-math.log(.25)))
        qh=.2+.6*u[4]
        beta=.6+.8*u[5]
        jcv=.5+1.5*u[6]
        ccm=math.exp(math.log(.25)+u[7]*(math.log(4)-math.log(.25)))
        dm=.25+1.75*u[8]
        m=mf*K; mH=1.15*m; mL=.85*m; inp=rho*mu
        out.append(core.Scenario(
            scenario_id=f'T{j:02d}', design='frozen_fresh59', K=K, mu_max=mu,
            rho=rho, arrival_scv=scv, mean_jump_fraction=mf, tau=tau,
            qH=qh, beta=beta, jump_cv=jcv, cloud_cost_multiplier=ccm,
            deactivation_mean=dm, lambda_H=(qh*inp)/mH,
            lambda_L=((1-qh)*inp)/mL, mean_H=mH, mean_L=mL,
            cv_H=jcv, cv_L=jcv))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--start',type=int,default=0); ap.add_argument('--count',type=int,default=None); ap.add_argument('--output',required=True)
    a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    ss=scenarios(); ss=ss[a.start:a.start+a.count if a.count is not None else None]
    rows=[]
    # JIT warm-up per process
    if ss:
        st=core.generate_stream(ss[0],12345,5.0)
        core.sim_threshold(ss[0],st,5.0,1.0,.5*ss[0].K,.4*ss[0].K,12345)
    for local,s in enumerate(ss):
        global_idx=a.start+local+1
        row=migr.run_scenario(s,global_idx,out,SEED_OFFSET)
        rows.append(row)
        print(f'[{global_idx:02d}/59] {s.scenario_id}: save={row["work_reduction"]:.1%}, regret={row["holdout_regret_vs_exhaustive"]:.2%}, cert={row["certified"]}',flush=True)
    pd.DataFrame(rows).to_csv(out/f'summary_chunk_{a.start:02d}.csv',index=False)

if __name__=='__main__': main()
