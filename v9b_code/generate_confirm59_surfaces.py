#!/usr/bin/env python3
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as migr

SCENARIO_SEED = 2026170718
SIMULATION_SEED_OFFSET = 1_800_000_000
N = 59


def scenarios():
    rng = np.random.default_rng(SCENARIO_SEED)
    U = rng.random((N, 10))
    out = []
    for j, u in enumerate(U, 1):
        K = 30 + 50*u[9]
        mu = 3*K
        rho = .55 + .35*u[0]
        scv = 1.0 if u[1] < .5 else 4.0
        mf = .05 + .05*u[2]
        tau = math.exp(math.log(.25) + u[3]*(math.log(4)-math.log(.25)))
        qh = .2 + .6*u[4]
        beta = .6 + .8*u[5]
        jcv = .5 + 1.5*u[6]
        ccm = math.exp(math.log(.25) + u[7]*(math.log(4)-math.log(.25)))
        dm = .25 + 1.75*u[8]
        m = mf*K
        mH = 1.15*m
        mL = .85*m
        inp = rho*mu
        out.append(core.Scenario(
            scenario_id=f'C{j:02d}', design='confirmatory_iid59_v9b', K=K,
            mu_max=mu, rho=rho, arrival_scv=scv,
            mean_jump_fraction=mf, tau=tau, qH=qh, beta=beta,
            jump_cv=jcv, cloud_cost_multiplier=ccm,
            deactivation_mean=dm, lambda_H=(qh*inp)/mH,
            lambda_L=((1-qh)*inp)/mL, mean_H=mH, mean_L=mL,
            cv_H=jcv, cv_L=jcv,
        ))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--count', type=int)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    ss = scenarios()[args.start:args.start+args.count]
    if ss:
        st = core.generate_stream(ss[0], 1, 5.0)
        core.sim_threshold(ss[0], st, 5.0, 1.0,
                           .5*ss[0].K, .4*ss[0].K, 1)
    rows = []
    for local, s in enumerate(ss):
        gi = args.start + local + 1
        row = migr.run_scenario(s, gi, out, SIMULATION_SEED_OFFSET)
        rows.append(row)
        print(f'[{gi:02d}/59] {s.scenario_id} '
              f'save={row["work_reduction"]:.1%} '
              f'regret={row["holdout_regret_vs_exhaustive"]:.2%}',
              flush=True)
    pd.DataFrame(rows).to_csv(out/f'summary_chunk_{args.start:02d}.csv', index=False)


if __name__ == '__main__':
    main()
