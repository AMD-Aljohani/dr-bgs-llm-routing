#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMBA_NUM_THREADS', '1')

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get('DRBGS_ROOT', Path(__file__).resolve().parents[1]))
OUT = Path(os.environ.get('V15_OUT', Path(__file__).resolve().parent))
CONFIG_PATH = OUT / 'V15_SEVEN_DAY_CONFIG.json'
sys.path.insert(0, str(ROOT / 'v11_code'))
sys.path.insert(0, str(ROOT / 'code'))
import run_trace_risk_study as v11  # noqa: E402
from run_smpt_campaign import Scenario, diffusion_metrics, sim_threshold  # noqa: E402

MU = 120.0
BETA = 1.0
DEACT = 0.75
EPS = 1e-12

CFG: Dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
K = float(CFG['K'])
BH_LIMIT = float(CFG['protected_blocking_limit'])
BL_LIMIT = float(CFG['eligible_blocking_limit'])
RISK_LIMIT = float(CFG['violation_risk_limit'])
FAMILY_ALPHA = float(CFG['familywise_alpha'])
REQUESTS_PER_REPLAY = int(CFG['requests_per_replay'])
BLOCK_LEN = int(CFG['moving_block_length'])
TRAIN_REPS = int(CFG['training_reps_per_policy'])
SEARCH_BUDGET = int(CFG['search_budget_policies'])

TRACE = pd.read_csv(ROOT / 'trace_data' / 'BurstGPT_first7days.csv')
TRACE = TRACE[TRACE['Total tokens'] > 0].copy()
SEARCH_POOL = TRACE[TRACE['Timestamp'] < int(CFG['search_end_seconds'])].reset_index(drop=True)
CERT_POOL = TRACE[(TRACE['Timestamp'] >= int(CFG['search_end_seconds'])) &
                  (TRACE['Timestamp'] < int(CFG['seven_day_end_seconds']))].reset_index(drop=True)
MEDIAN_TOKENS = float(SEARCH_POOL['Total tokens'].median())


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def policies_for_k(k: float = K) -> List[Tuple[float, float]]:
    levels = np.linspace(0.05 * k, 0.95 * k, 19)
    policies = [(float(on), float(off)) for on in levels for off in levels if off <= on + EPS]
    assert len(policies) == int(CFG['policy_count']) == 190
    return policies


POLICIES = policies_for_k()


def pool_arrays(pool: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    ts = pool['Timestamp'].to_numpy(float)
    gaps = np.diff(ts)
    positive = gaps[gaps > 0]
    first_gap = float(np.median(positive)) if len(positive) else 1.0
    gaps = np.r_[first_gap, np.maximum(gaps, 0.0)]
    tokens = pool['Total tokens'].to_numpy(float)
    jumps = np.clip(3.0 * tokens / MEDIAN_TOKENS, 0.10, 0.25 * K)
    return gaps, jumps


SEARCH_GAPS, SEARCH_JUMPS = pool_arrays(SEARCH_POOL)
CERT_GAPS, CERT_JUMPS = pool_arrays(CERT_POOL)


def block_bootstrap_stream(pool_name: str, rho: float, qh: float, seed: int):
    rng = np.random.default_rng(seed)
    gaps, base_jumps = (SEARCH_GAPS, SEARCH_JUMPS) if pool_name == 'search' else (CERT_GAPS, CERT_JUMPS)
    n_pool = len(gaps)
    out_gaps: List[float] = []
    out_jumps: List[float] = []
    while len(out_gaps) < REQUESTS_PER_REPLAY:
        start = int(rng.integers(n_pool))
        take = min(BLOCK_LEN, REQUESTS_PER_REPLAY - len(out_gaps))
        idx = (start + np.arange(take)) % n_pool
        out_gaps.extend(gaps[idx].astype(float).tolist())
        out_jumps.extend(base_jumps[idx].astype(float).tolist())
    gaps_a = np.asarray(out_gaps, dtype=float)
    jumps = np.asarray(out_jumps, dtype=float)
    desired_horizon = float(jumps.sum() / (rho * MU))
    scale = desired_horizon / max(float(gaps_a.sum()), EPS)
    times = np.cumsum(gaps_a * scale)
    horizon = float(times[-1] * 1.05)
    burn = float(0.20 * horizon)
    classes = (rng.random(len(times)) >= qh).astype(np.int8)  # 0=H, 1=L
    uniforms = rng.random(len(times))
    return times, classes, jumps, uniforms, horizon, burn


def prebuild_streams(pool_name: str, rho: float, qh: float, n: int, seed_base: int):
    return [block_bootstrap_stream(pool_name, rho, qh, seed_base + 1009 * r) for r in range(n)]


def build_scenario(sid: str, rho: float, qh: float, tau: float) -> Scenario:
    mean_jump = float(SEARCH_JUMPS.mean())
    cv = float(SEARCH_JUMPS.std(ddof=1) / max(mean_jump, EPS))
    total_input = rho * MU
    return Scenario(
        scenario_id=sid,
        design='v15_burstgpt_seven_day',
        K=K,
        mu_max=MU,
        rho=rho,
        arrival_scv=4.0,
        mean_jump_fraction=mean_jump / K,
        tau=tau,
        qH=qh,
        beta=BETA,
        jump_cv=cv,
        cloud_cost_multiplier=1.0,
        deactivation_mean=DEACT,
        lambda_H=(qh * total_input) / mean_jump,
        lambda_L=((1.0 - qh) * total_input) / mean_jump,
        mean_H=mean_jump,
        mean_L=mean_jump,
        cv_H=cv,
        cv_L=cv,
        cW=0.15,
        cB=50.0,
        cL=20.0,
        cC=1.0,
    )


def search_score(m: Dict[str, float]) -> float:
    return (m['cloud_fraction'] + 0.15 * m['W']
            + 50.0 * max(m['B_H'] - BH_LIMIT, 0.0)
            + 20.0 * max(m['B_L'] - BL_LIMIT, 0.0))


def op_cost(m: Dict[str, float]) -> float:
    return m['cloud_fraction'] + 0.15 * m['W']


def build_training_surface(sid: str, rho: float, qh: float, tau: float, seed_base: int) -> pd.DataFrame:
    s = build_scenario(sid, rho, qh, tau)
    streams = prebuild_streams('search', rho, qh, TRAIN_REPS, seed_base)
    rows: List[Dict[str, Any]] = []
    for pidx, (on, off) in enumerate(POLICIES):
        vals: List[Dict[str, float]] = []
        for r, st in enumerate(streams):
            times, classes, jumps, uniforms, horizon, burn = st
            m = sim_threshold(s, (times, classes, jumps, uniforms), horizon, burn, on, off,
                              seed=seed_base + 500_000 + 1009 * r)
            m['score'] = search_score(m)
            m['op_cost'] = op_cost(m)
            vals.append(m)
        def mean(name: str) -> float:
            return float(np.mean([v[name] for v in vals]))
        def se(name: str) -> float:
            a = np.asarray([v[name] for v in vals], dtype=float)
            return float(a.std(ddof=1) / math.sqrt(len(a)))
        dm = diffusion_metrics(s, on, off, N=161)
        rows.append({
            'scenario_id': sid, 'policy_idx': pidx, 'alpha_on': on, 'alpha_off': off,
            'train_score': mean('score'), 'train_score_se': se('score'),
            'train_op_cost': mean('op_cost'), 'train_W': mean('W'),
            'train_B_H': mean('B_H'), 'train_B_L': mean('B_L'),
            'train_cloud_fraction': mean('cloud_fraction'),
            'diffusion_score': search_score(dm), 'diffusion_W': dm['W'],
            'diffusion_B_H': dm['B_H'], 'diffusion_B_L': dm['B_L'],
            'diffusion_cloud_fraction': dm['cloud_fraction'],
        })
    return pd.DataFrame(rows)


def cp_cert(bh: np.ndarray, bl: np.ndarray) -> Dict[str, Any]:
    n = int(len(bh))
    vh = int(np.sum(bh > BH_LIMIT))
    vl = int(np.sum(bl > BL_LIMIT))
    uh = float(v11.cp_upper(vh, n, FAMILY_ALPHA / 2.0))
    ul = float(v11.cp_upper(vl, n, FAMILY_ALPHA / 2.0))
    return {'n': n, 'viol_H': vh, 'viol_L': vl, 'upper_H': uh, 'upper_L': ul,
            'certified': int(uh <= RISK_LIMIT and ul <= RISK_LIMIT)}


def simulate_policies(s: Scenario, rho: float, qh: float, policy_indices: Sequence[int],
                      streams: Sequence[Any], sim_seed_base: int) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for pidx in policy_indices:
        on, off = POLICIES[pidx]
        bh = np.empty(len(streams), dtype=float)
        bl = np.empty(len(streams), dtype=float)
        w = np.empty(len(streams), dtype=float)
        cloud = np.empty(len(streams), dtype=float)
        for r, st in enumerate(streams):
            times, classes, jumps, uniforms, horizon, burn = st
            m = sim_threshold(s, (times, classes, jumps, uniforms), horizon, burn, on, off,
                              seed=sim_seed_base + pidx * 100_003 + 1009 * r)
            bh[r] = m['B_H']; bl[r] = m['B_L']; w[r] = m['W']; cloud[r] = m['cloud_fraction']
        cert = cp_cert(bh, bl)
        out[pidx] = {
            **cert,
            'mean_B_H': float(bh.mean()), 'mean_B_L': float(bl.mean()),
            'mean_W': float(w.mean()), 'mean_cloud_fraction': float(cloud.mean()),
            'mean_op_cost': float((cloud + 0.15 * w).mean()),
            'p95_B_H': float(np.quantile(bh, 0.95)), 'p95_B_L': float(np.quantile(bl, 0.95)),
        }
    return out


def high_scenario_rows() -> List[Dict[str, Any]]:
    rows = []
    i = 0
    for rho in CFG['high_load_rho_values']:
        for qh in CFG['qH_values']:
            for tau in CFG['tau_values']:
                i += 1
                rows.append({'scenario_id': f'R15H{i:02d}', 'rho': float(rho), 'qH': float(qh), 'tau': float(tau)})
    return rows


def low_scenario_rows() -> List[Dict[str, Any]]:
    rows = []
    i = 0
    for qh in CFG['qH_values']:
        for tau in CFG['tau_values']:
            i += 1
            rows.append({'scenario_id': f'R15L{i:02d}', 'rho': float(CFG['low_load_rho']),
                         'qH': float(qh), 'tau': float(tau)})
    return rows


def high_worker(row: Dict[str, Any]) -> Dict[str, Any]:
    idx = int(row['scenario_id'][-2:])
    seeds = CFG['seed_scheme']
    train_seed = int(seeds['high_training_base']) + idx * int(seeds['scenario_stride'])
    cert_seed = int(seeds['high_certification_base']) + idx * int(seeds['scenario_stride'])
    surface = build_training_surface(row['scenario_id'], row['rho'], row['qH'], row['tau'], train_seed)
    s = build_scenario(row['scenario_id'], row['rho'], row['qH'], row['tau'])
    streams = prebuild_streams('cert', row['rho'], row['qH'], int(CFG['high_load_certification_replays']), cert_seed)
    evaluations = simulate_policies(s, row['rho'], row['qH'], range(190), streams, cert_seed + 20_000_000)
    exhaustive_idx = int(v11.select_from_indices(surface, range(190)))
    selected: List[Tuple[str, int, int]] = [('Exhaustive-training', -1, exhaustive_idx)]
    init_base = int(seeds['search_initialization_base'])
    for method, residual in [('DR-BGS', True), ('Guarded-GP', False)]:
        for init in range(int(CFG['high_load_search_initializations'])):
            pidx, _ = v11.guarded_search(surface, residual=residual, seed=init_base + init)
            selected.append((method, init, int(pidx)))
    policy_rows = []
    for pidx, ev in evaluations.items():
        policy_rows.append({**row, 'policy_idx': pidx, 'alpha_on': POLICIES[pidx][0],
                            'alpha_off': POLICIES[pidx][1], **ev})
    method_rows = []
    for method, init, pidx in selected:
        method_rows.append({**row, 'method': method, 'init_index': init, 'selected_idx': pidx,
                            'alpha_on': POLICIES[pidx][0], 'alpha_off': POLICIES[pidx][1],
                            **evaluations[pidx]})
    return {'row': row, 'surface': surface.to_dict('records'), 'policy_rows': policy_rows,
            'method_rows': method_rows}


def low_worker(row: Dict[str, Any]) -> Dict[str, Any]:
    idx = int(row['scenario_id'][-2:])
    seeds = CFG['seed_scheme']
    train_seed = int(seeds['low_training_base']) + idx * int(seeds['scenario_stride'])
    cert_a_seed = int(seeds['low_certification_A_base']) + idx * int(seeds['scenario_stride'])
    cert_b_seed = int(seeds['low_certification_B_base']) + idx * int(seeds['scenario_stride'])
    surface = build_training_surface(row['scenario_id'], row['rho'], row['qH'], row['tau'], train_seed)
    selected: List[Tuple[str, int, int]] = []
    exhaustive_idx = int(v11.select_from_indices(surface, range(190)))
    selected.append(('Exhaustive-training', -1, exhaustive_idx))
    init_base = int(seeds['search_initialization_base']) + 1000
    for method, residual in [('DR-BGS', True), ('Guarded-GP', False)]:
        for init in range(int(CFG['low_load_search_initializations'])):
            pidx, _ = v11.guarded_search(surface, residual=residual, seed=init_base + init)
            selected.append((method, init, int(pidx)))
    unique = sorted(set(pidx for _, _, pidx in selected))
    s = build_scenario(row['scenario_id'], row['rho'], row['qH'], row['tau'])
    streams_a = prebuild_streams('cert', row['rho'], row['qH'], int(CFG['low_load_certification_replays_A']), cert_a_seed)
    streams_b = prebuild_streams('cert', row['rho'], row['qH'], int(CFG['low_load_certification_replays_B']), cert_b_seed)
    eval_a = simulate_policies(s, row['rho'], row['qH'], unique, streams_a, cert_a_seed + 20_000_000)
    eval_b = simulate_policies(s, row['rho'], row['qH'], unique, streams_b, cert_b_seed + 20_000_000)
    policy_rows = []
    for pidx in unique:
        methods = sorted(set(m for m, _, j in selected if j == pidx))
        confirmed = int(eval_a[pidx]['certified'] and eval_b[pidx]['certified'])
        policy_rows.append({**row, 'policy_idx': pidx, 'alpha_on': POLICIES[pidx][0],
                            'alpha_off': POLICIES[pidx][1], 'methods': ';'.join(methods),
                            'run_references': sum(1 for _, _, j in selected if j == pidx),
                            'confirmed': confirmed,
                            **{f'A_{k}': v for k, v in eval_a[pidx].items()},
                            **{f'B_{k}': v for k, v in eval_b[pidx].items()}})
    method_rows = []
    for method, init, pidx in selected:
        confirmed = int(eval_a[pidx]['certified'] and eval_b[pidx]['certified'])
        method_rows.append({**row, 'method': method, 'init_index': init, 'selected_idx': pidx,
                            'alpha_on': POLICIES[pidx][0], 'alpha_off': POLICIES[pidx][1],
                            'confirmed': confirmed,
                            **{f'A_{k}': v for k, v in eval_a[pidx].items()},
                            **{f'B_{k}': v for k, v in eval_b[pidx].items()}})
    return {'row': row, 'surface': surface.to_dict('records'), 'policy_rows': policy_rows,
            'method_rows': method_rows}


def run_parallel(rows: List[Dict[str, Any]], worker, workers: int, label: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(worker, row): row['scenario_id'] for row in rows}
        done = 0
        for fut in as_completed(futures):
            sid = futures[fut]
            results.append(fut.result())
            done += 1
            log(f'{label}: completed {done}/{len(rows)} ({sid})')
    return sorted(results, key=lambda x: x['row']['scenario_id'])


def save_outputs(high: List[Dict[str, Any]], low: List[Dict[str, Any]], started: float) -> None:
    high_policy = pd.DataFrame([r for x in high for r in x['policy_rows']])
    high_method = pd.DataFrame([r for x in high for r in x['method_rows']])
    high_surface = pd.DataFrame([r for x in high for r in x['surface']])
    low_policy = pd.DataFrame([r for x in low for r in x['policy_rows']])
    low_method = pd.DataFrame([r for x in low for r in x['method_rows']])
    low_surface = pd.DataFrame([r for x in low for r in x['surface']])
    high_policy.to_csv(OUT / 'V15_HIGH_LOAD_ALL_POLICY_CERTIFICATION.csv', index=False)
    high_method.to_csv(OUT / 'V15_HIGH_LOAD_METHOD_RUNS.csv', index=False)
    high_surface.to_csv(OUT / 'V15_HIGH_LOAD_TRAINING_SURFACES.csv', index=False)
    low_policy.to_csv(OUT / 'V15_LOW_LOAD_UNIQUE_POLICIES.csv', index=False)
    low_method.to_csv(OUT / 'V15_LOW_LOAD_METHOD_RUNS.csv', index=False)
    low_surface.to_csv(OUT / 'V15_LOW_LOAD_TRAINING_SURFACES.csv', index=False)

    high_scenario = high_policy.groupby(['scenario_id', 'rho', 'qH', 'tau']).agg(
        policies=('policy_idx', 'size'), certified_policies=('certified', 'sum'),
        min_mean_B_H=('mean_B_H', 'min'), min_mean_B_L=('mean_B_L', 'min'),
        min_max_upper=('upper_H', lambda s: np.nan),
    ).reset_index()
    # joint best diagnostics require policy-level max, not separate minima.
    joint = high_policy.assign(max_mean_ratio=np.maximum(high_policy.mean_B_H / BH_LIMIT,
                                                          high_policy.mean_B_L / BL_LIMIT),
                               max_upper=np.maximum(high_policy.upper_H, high_policy.upper_L))
    jidx = joint.groupby('scenario_id').max_mean_ratio.idxmin()
    best = joint.loc[jidx, ['scenario_id', 'policy_idx', 'alpha_on', 'alpha_off', 'mean_B_H',
                            'mean_B_L', 'upper_H', 'upper_L', 'max_mean_ratio', 'max_upper']]
    high_scenario = high_scenario.drop(columns=['min_max_upper']).merge(best, on='scenario_id', how='left')
    high_scenario.to_csv(OUT / 'V15_HIGH_LOAD_SCENARIO_SUMMARY.csv', index=False)

    high_method_summary = high_method.groupby('method').agg(
        run_labels=('certified', 'size'), certified_labels=('certified', 'sum'),
        physical_scenarios=('scenario_id', 'nunique'),
        unique_scenario_policy_pairs=('selected_idx', lambda s: 0),
    ).reset_index()
    unique_counts = high_method.groupby('method').apply(
        lambda g: g[['scenario_id', 'selected_idx']].drop_duplicates().shape[0],
        include_groups=False).rename('unique_scenario_policy_pairs').reset_index()
    high_method_summary = high_method_summary.drop(columns=['unique_scenario_policy_pairs']).merge(unique_counts, on='method')
    high_method_summary.to_csv(OUT / 'V15_HIGH_LOAD_METHOD_SUMMARY.csv', index=False)

    low_method_summary = low_method.groupby('method').agg(
        run_labels=('confirmed', 'size'), confirmed_labels=('confirmed', 'sum'),
        physical_scenarios=('scenario_id', 'nunique'),
    ).reset_index()
    low_unique_method = []
    for method, g in low_method.groupby('method'):
        u = g[['scenario_id', 'selected_idx', 'confirmed', 'A_upper_H', 'A_upper_L', 'B_upper_H', 'B_upper_L']].drop_duplicates(['scenario_id', 'selected_idx'])
        low_unique_method.append({
            'method': method, 'unique_scenario_policy_pairs': int(len(u)),
            'unique_pairs_confirmed': int(u.confirmed.sum()),
            'max_upper_bound': float(np.maximum.reduce([u.A_upper_H, u.A_upper_L, u.B_upper_H, u.B_upper_L]).max()),
        })
    low_method_summary = low_method_summary.merge(pd.DataFrame(low_unique_method), on='method')
    low_method_summary.to_csv(OUT / 'V15_LOW_LOAD_METHOD_SUMMARY.csv', index=False)

    cross_union = low_method[['scenario_id', 'selected_idx']].drop_duplicates().shape[0]
    cross_confirmed = low_policy[low_policy.confirmed == 1][['scenario_id', 'policy_idx']].drop_duplicates().shape[0]
    high_cert_total = int(high_policy.certified.sum())
    stats = {
        'study_id': CFG['study_id'],
        'status': 'completed',
        'runtime_seconds': time.time() - started,
        'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__, 'pandas': pd.__version__},
        'trace': {
            'seven_day_rows_all': int(len(pd.read_csv(ROOT / 'trace_data' / 'BurstGPT_first7days.csv'))),
            'positive_rows': int(len(TRACE)), 'search_rows': int(len(SEARCH_POOL)),
            'certification_rows': int(len(CERT_POOL)), 'training_median_tokens': MEDIAN_TOKENS,
            'search_span_seconds': float(SEARCH_POOL.Timestamp.iloc[-1] - SEARCH_POOL.Timestamp.iloc[0]),
            'certification_span_seconds': float(CERT_POOL.Timestamp.iloc[-1] - CERT_POOL.Timestamp.iloc[0]),
        },
        'high_load': {
            'policy_scenario_pairs': int(len(high_policy)), 'certified_policy_scenario_pairs': high_cert_total,
            'scenarios_with_any_certified_policy': int((high_scenario.certified_policies > 0).sum()),
            'method_summary': high_method_summary.to_dict('records'),
            'scenario_summary': high_scenario.to_dict('records'),
        },
        'low_load': {
            'method_summary': low_method_summary.to_dict('records'),
            'cross_method_distinct_scenario_policy_pairs': int(cross_union),
            'cross_method_distinct_pairs_confirmed': int(cross_confirmed),
            'batch_reversals': int(np.sum(low_policy.A_certified != low_policy.B_certified)),
        },
        'claim_boundary': CFG['claim_boundary'],
    }
    (OUT / 'V15_KEY_RESULTS.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')

    report = []
    report.append('# V15 Seven-Day BurstGPT Robustness Results\n')
    report.append('## Trace basis\n')
    report.append(f"The fixed seven-day window contains {stats['trace']['positive_rows']:,} positive-token rows. The first five days provide {stats['trace']['search_rows']:,} search rows and the later two days provide {stats['trace']['certification_rows']:,} certification rows. Privacy labels and replay construction remain synthetic.\n")
    report.append('## Original high-load regimes\n')
    report.append(f"Across all 190 policies and 12 scenarios, {high_cert_total} of {len(high_policy):,} policy-scenario combinations passed the unchanged 2%/5% absolute gate.\n")
    report.append(high_scenario.to_markdown(index=False, floatfmt='.5f'))
    report.append('\n\nMethod nominations:\n')
    report.append(high_method_summary.to_markdown(index=False))
    report.append('\n\n## Separately locked low-load confirmation\n')
    report.append(low_method_summary.to_markdown(index=False, floatfmt='.5f'))
    report.append(f"\n\nAfter cross-method deduplication, {cross_confirmed} of {cross_union} distinct scenario-policy pairs passed both disjoint 1,200-replay batches. Batch-to-batch reversals: {stats['low_load']['batch_reversals']}.\n")
    report.append('## Interpretation\n')
    report.append('This larger-slice replication tests robustness to a substantially broader chronological workload basis. Exact risk bounds remain conditional on the declared block-bootstrap generator and do not constitute live-system safety guarantees. The V11 compact-slice results remain reported as the original study rather than being replaced.\n')
    (OUT / 'V15_RESULTS_REPORT.md').write_text('\n'.join(report), encoding='utf-8')

    # Figures
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(high_scenario))
    ax.plot(x, high_scenario.max_upper, marker='o')
    ax.axhline(RISK_LIMIT, linestyle='--')
    ax.set_xticks(x, high_scenario.scenario_id, rotation=45, ha='right')
    ax.set_ylabel('Best policy: largest exact upper risk bound')
    ax.set_xlabel('Seven-day high-load scenario')
    ax.set_title('Exhaustive strict-risk audit on the seven-day trace window')
    fig.tight_layout()
    fig.savefig(OUT / 'V15_HIGH_LOAD_EXHAUSTIVE_AUDIT.png', dpi=180)
    fig.savefig(OUT / 'V15_HIGH_LOAD_EXHAUSTIVE_AUDIT.pdf')
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    plot = low_method_summary.sort_values('method')
    ax.bar(plot.method, plot.unique_pairs_confirmed)
    ax.scatter(plot.method, plot.unique_scenario_policy_pairs, marker='_', s=500)
    ax.set_ylabel('Unique scenario-policy pairs')
    ax.set_title('Seven-day low-load two-batch confirmation')
    ax.tick_params(axis='x', rotation=15)
    fig.tight_layout()
    fig.savefig(OUT / 'V15_LOW_LOAD_CONFIRMATION.png', dpi=180)
    fig.savefig(OUT / 'V15_LOW_LOAD_CONFIRMATION.pdf')
    plt.close(fig)

    # Post-result checksums.
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'V15_POST_RESULT_SHA256SUMS.txt')
    (OUT / 'V15_POST_RESULT_SHA256SUMS.txt').write_text(
        ''.join(f'{sha256_file(p)}  {p.name}\n' for p in files), encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()
    assert len(SEARCH_POOL) == 11810, len(SEARCH_POOL)
    assert len(CERT_POOL) == 6086, len(CERT_POOL)
    started = time.time()
    log(f'Root: {ROOT}')
    log(f'Search rows: {len(SEARCH_POOL):,}; certification rows: {len(CERT_POOL):,}')
    high = run_parallel(high_scenario_rows(), high_worker, args.workers, 'High-load')
    low = run_parallel(low_scenario_rows(), low_worker, args.workers, 'Low-load')
    save_outputs(high, low, started)
    log(f'Completed V15 in {(time.time()-started)/60:.2f} minutes')


if __name__ == '__main__':
    main()
