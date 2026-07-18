#!/usr/bin/env python3
"""Component ablation for the V8 optimizer comparison.

The four variants separate structural initialization from residual calibration:
  * standard GP: random/maximin initialization, direct response model;
  * guarded GP: structural/diffusion-ranked anchors, direct response model;
  * residual GP: random/maximin initialization, diffusion-residual model;
  * DR-BGS: structural/diffusion-ranked anchors plus diffusion-residual model.

All variants use the same policy budget, fixed kernel, training means, and
independent holdout reference surfaces.
"""
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel

ROOT = Path(__file__).resolve().parents[1]
SURF = pd.read_csv(ROOT/'results'/'hysteresis_policy_surfaces_all.csv')
SUM = pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv')
OUT = ROOT/'v8_results'/'component_ablation'
OUT.mkdir(parents=True, exist_ok=True)
SEEDS = range(5)
BUDGETS = (12, 20)
EPS = 1e-12


def coords(df):
    K = df.alpha_on.max()/0.95
    return np.column_stack([df.alpha_on/K, df.alpha_off/K])


def maximin_fill(X, selected, n, seed):
    rng = np.random.default_rng(seed)
    selected = list(dict.fromkeys(selected))
    if not selected:
        selected = [int(rng.integers(len(X)))]
    chosen = set(selected)
    while len(selected) < n:
        rem = np.array([i for i in range(len(X)) if i not in chosen], int)
        d = cdist(X[rem], X[selected]).min(axis=1)
        mx = d.max()
        ties = rem[np.flatnonzero(np.isclose(d, mx))]
        nxt = int(rng.choice(ties))
        selected.append(nxt); chosen.add(nxt)
    return selected


def structural_anchors(X, diffusion):
    targets = [(0.05,0.05),(0.95,0.05),(0.95,0.95),(0.50,0.05),(0.50,0.50)]
    anchors = [int(np.argmin(np.linalg.norm(X-np.array(t), axis=1))) for t in targets]
    anchors += list(map(int, np.argsort(diffusion)[:3]))
    return anchors


def select_policy(X, diffusion, y, se, budget, seed, residual, guards):
    initial = structural_anchors(X, diffusion) if guards else []
    seen = maximin_fill(X, initial,
                        min(max(8, len(set(initial))), budget), seed)
    chosen = set(seen)
    kernel = ConstantKernel(1.0, 'fixed')*Matern(
        [0.2,0.2], nu=2.5, length_scale_bounds='fixed')
    while len(seen) < budget:
        ids = np.asarray(seen, int)
        if residual:
            A = np.column_stack([np.ones(len(ids)), diffusion[ids]])
            coef = np.linalg.lstsq(A, y[ids], rcond=None)[0]
            trend = coef[0] + coef[1]*diffusion
            target = y[ids] - trend[ids]
        else:
            trend = np.full(len(X), y[ids].mean())
            target = y[ids] - y[ids].mean()
        scale = max(float(target.std()), 1e-6)
        noise = np.maximum(se[ids]/scale, 1e-6)**2 + 1e-6
        gp = GaussianProcessRegressor(
            kernel=kernel, alpha=noise, optimizer=None, normalize_y=False)
        gp.fit(X[ids], target/scale)
        rem = np.array([i for i in range(len(X)) if i not in chosen], int)
        mu, sd = gp.predict(X[rem], return_std=True)
        beta_t = 2.0 + 0.25*math.log1p(len(seen))
        acquisition = trend[rem] + scale*mu - beta_t*scale*sd
        nxt = int(rem[np.argmin(acquisition)])
        seen.append(nxt); chosen.add(nxt)
    return int(min(seen, key=lambda i: y[i]))


def main():
    variants = [
        ('standard_GP', False, False),
        ('guarded_GP', False, True),
        ('residual_GP', True, False),
        ('DR_BGS', True, True),
    ]
    rows = []
    for s in SUM.itertuples():
        df = SURF[SURF.scenario_id == s.scenario_id].sort_values(
            'policy_idx').reset_index(drop=True)
        X = coords(df)
        y = df.train_objective.to_numpy(float)
        hold = df.holdout_objective.to_numpy(float)
        diffusion = df.diffusion_objective.to_numpy(float)
        se = df.train_objective_ci95_hw.to_numpy(float)/2.093
        reference_idx = int(s.exhaustive_train_idx)
        reference = float(hold[reference_idx])
        for budget in BUDGETS:
            for seed in SEEDS:
                for name, residual, guards in variants:
                    idx = select_policy(X, diffusion, y, se, budget,
                                        20260717+seed, residual, guards)
                    regret = max(0.0, (float(hold[idx])-reference)/
                                 max(abs(reference), EPS))
                    rows.append({
                        'scenario_id': s.scenario_id,
                        'budget': budget,
                        'seed': seed,
                        'method': name,
                        'selected_idx': idx,
                        'regret_vs_exhaustive_training_workflow': regret,
                        'exact_training_policy_recovery': int(idx == reference_idx),
                    })
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT/'component_ablation_runs.csv', index=False)
    summary = raw.groupby(['budget','method']).agg(
        median_regret=('regret_vs_exhaustive_training_workflow','median'),
        p90_regret=('regret_vs_exhaustive_training_workflow',lambda x:x.quantile(.9)),
        maximum_regret=('regret_vs_exhaustive_training_workflow','max'),
        runs_within_1pct=('regret_vs_exhaustive_training_workflow',lambda x:(x<=.01).mean()),
        runs_within_5pct=('regret_vs_exhaustive_training_workflow',lambda x:(x<=.05).mean()),
        exact_training_policy_recovery=('exact_training_policy_recovery','mean'),
    ).reset_index()
    summary.to_csv(OUT/'component_ablation_summary.csv', index=False)
    print(summary.to_string(index=False))

if __name__ == '__main__':
    main()
