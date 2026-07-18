#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
SURF = pd.read_csv(ROOT/'results'/'hysteresis_policy_surfaces_all.csv')
SUM = pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv')
OUT = ROOT/'v7_results'/'optimizer_comparison'
OUT.mkdir(parents=True, exist_ok=True)
BUDGET = 20
SEEDS = range(5)
BASE_SEED = 20260717
EPS = 1e-12


def coords(df):
    K = max(df.alpha_on.max()/0.95, EPS)
    return np.column_stack([df.alpha_on/K, df.alpha_off/K])


def random_rs(train, k, seed):
    rng = np.random.default_rng(seed)
    ids = rng.choice(len(train), size=min(k, len(train)), replace=False)
    return int(ids[np.argmin(train[ids])])


def diffusion_topk(diff, train, k):
    ids = np.argsort(diff)[:k]
    return int(ids[np.argmin(train[ids])])


def local_search(df, train, k, seed):
    X = coords(df)
    n = len(df)
    ons = sorted(df.alpha_on.unique())
    offs = sorted(df.alpha_off.unique())
    idx = {(float(r.alpha_on), float(r.alpha_off)): int(r.policy_idx)
           for r in df.itertuples()}
    center = min(range(n), key=lambda i: abs(X[i,0]-.5)+abs(X[i,1]-.4))
    seen = set()
    current = center
    while len(seen) < k:
        seen.add(current)
        row = df.iloc[current]
        oi = ons.index(row.alpha_on)
        fj = offs.index(row.alpha_off)
        neigh = []
        for di, dj in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
            ni, nj = oi+di, fj+dj
            if 0 <= ni < len(ons) and 0 <= nj < len(offs) and offs[nj] <= ons[ni]:
                p = idx.get((float(ons[ni]), float(offs[nj])))
                if p is not None and p not in seen:
                    neigh.append(p)
        for p in neigh:
            if len(seen) >= k:
                break
            seen.add(p)
        best = min(seen, key=lambda i: train[i])
        if best == current or not neigh:
            rem = [i for i in range(n) if i not in seen]
            if not rem:
                break
            d = cdist(X[rem], X[list(seen)]).min(axis=1)
            current = int(rem[np.argmax(d)])
        else:
            current = best
    return int(min(seen, key=lambda i: train[i]))


rows = []
for srow in SUM.itertuples():
    sid = srow.scenario_id
    df = SURF[SURF.scenario_id == sid].sort_values('policy_idx').reset_index(drop=True)
    train = df.train_objective.to_numpy(float)
    hold = df.holdout_objective.to_numpy(float)
    diff = df.diffusion_objective.to_numpy(float)
    idx_exh = int(srow.exhaustive_train_idx)
    ref = hold[idx_exh]

    i = diffusion_topk(diff, train, BUDGET)
    rows.append({'scenario_id':sid, 'method':'diffusion_top20', 'seed':0,
                 'regret':max(0.0, (hold[i]-ref)/max(abs(ref), EPS))})
    for seed in SEEDS:
        i = random_rs(train, BUDGET, BASE_SEED+seed)
        rows.append({'scenario_id':sid, 'method':'random_RS', 'seed':seed,
                     'regret':max(0.0, (hold[i]-ref)/max(abs(ref), EPS))})
        i = local_search(df, train, BUDGET, BASE_SEED+seed)
        rows.append({'scenario_id':sid, 'method':'local_search', 'seed':seed,
                     'regret':max(0.0, (hold[i]-ref)/max(abs(ref), EPS))})

raw = pd.DataFrame(rows)
raw.to_csv(OUT/'fixed20_simple_runs.csv', index=False)
summary = raw.groupby('method').agg(
    median_regret=('regret','median'),
    p90_regret=('regret',lambda x:x.quantile(.9)),
    max_regret=('regret','max'),
    success1=('regret',lambda x:(x<=.01).mean()),
    success5=('regret',lambda x:(x<=.05).mean()),
).reset_index()
summary.to_csv(OUT/'fixed20_simple_summary.csv', index=False)
print(summary.to_string(index=False))
