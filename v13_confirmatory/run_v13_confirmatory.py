#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMBA_NUM_THREADS', '1')

import numpy as np
import pandas as pd

BASE_SCRIPT = Path('/mnt/data/run_v12_exploratory.py')
spec = importlib.util.spec_from_file_location('v12base', BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_config(path: Path) -> Dict[str, Any]:
    cfg = json.loads(path.read_text(encoding='utf-8'))
    required = [
        'study_id', 'K', 'rho', 'qH_values', 'tau_values', 'search_initializations',
        'training_reps_per_policy', 'search_budget_policies', 'certification_replays_A',
        'certification_replays_B', 'protected_blocking_limit', 'eligible_blocking_limit',
        'violation_risk_limit', 'familywise_alpha', 'seed_scheme', 'primary_success_rule'
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f'Missing config keys: {missing}')
    return cfg


def validate_config(cfg: Dict[str, Any]) -> None:
    assert math.isclose(float(cfg['K']), 40.0)
    assert math.isclose(float(cfg['rho']), 0.05)
    assert list(map(float, cfg['qH_values'])) == [0.2, 0.5, 0.8]
    assert list(map(float, cfg['tau_values'])) == [0.5, 2.0]
    assert int(cfg['search_initializations']) == 10
    assert int(cfg['training_reps_per_policy']) == base.TRAIN_REPS == 12
    assert int(cfg['search_budget_policies']) == base.SEARCH_BUDGET == 20
    assert int(cfg['certification_replays_A']) == 1200
    assert int(cfg['certification_replays_B']) == 1200
    assert math.isclose(float(cfg['protected_blocking_limit']), base.BH_LIMIT)
    assert math.isclose(float(cfg['eligible_blocking_limit']), base.BL_LIMIT)
    assert math.isclose(float(cfg['violation_risk_limit']), base.RISK_LIMIT)
    assert math.isclose(float(cfg['familywise_alpha']), base.FAMILY_ALPHA)


def scenario_rows(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    sid = 0
    for qh in cfg['qH_values']:
        for tau in cfg['tau_values']:
            sid += 1
            rows.append({
                'scenario_id': f'C{sid:02d}',
                'K': float(cfg['K']),
                'rho': float(cfg['rho']),
                'qH': float(qh),
                'tau': float(tau),
            })
    return rows


def simulate_selected_policy(
    scenario: Any,
    policy: Tuple[float, float],
    streams: List[Any],
    sim_seed_base: int,
) -> Dict[str, np.ndarray]:
    bh: List[float] = []
    bl: List[float] = []
    w: List[float] = []
    cloud: List[float] = []
    on, off = policy
    for r, stream in enumerate(streams):
        times, classes, jumps, uniforms, horizon, burn = stream
        m = base.sim_threshold(
            scenario,
            (times, classes, jumps, uniforms),
            horizon,
            burn,
            on,
            off,
            seed=sim_seed_base + 1009 * r,
        )
        bh.append(float(m['B_H']))
        bl.append(float(m['B_L']))
        w.append(float(m['W']))
        cloud.append(float(m['cloud_fraction']))
    return {
        'B_H': np.asarray(bh, dtype=float),
        'B_L': np.asarray(bl, dtype=float),
        'W': np.asarray(w, dtype=float),
        'cloud_fraction': np.asarray(cloud, dtype=float),
    }


def summarize_batch(arrays: Dict[str, np.ndarray]) -> Dict[str, Any]:
    cert = base.cp_cert(arrays['B_H'], arrays['B_L'])
    op = arrays['cloud_fraction'] + 0.15 * arrays['W']
    return {
        **cert,
        'mean_B_H': float(arrays['B_H'].mean()),
        'mean_B_L': float(arrays['B_L'].mean()),
        'mean_W': float(arrays['W'].mean()),
        'mean_cloud_fraction': float(arrays['cloud_fraction'].mean()),
        'mean_op_cost': float(op.mean()),
        'p95_B_H': float(np.quantile(arrays['B_H'], 0.95)),
        'p95_B_L': float(np.quantile(arrays['B_L'], 0.95)),
    }


def run_scenario(row: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    sid = row['scenario_id']
    idx = int(sid[1:])
    K = float(row['K'])
    rho = float(row['rho'])
    qh = float(row['qH'])
    tau = float(row['tau'])
    seeds = cfg['seed_scheme']
    train_seed = int(seeds['training_base']) + idx * int(seeds['scenario_stride'])
    cert_A_seed = int(seeds['certification_A_base']) + idx * int(seeds['scenario_stride'])
    cert_B_seed = int(seeds['certification_B_base']) + idx * int(seeds['scenario_stride'])

    policies = base.policies_for_k(K)
    scenario = base.build_scenario(sid, K, rho, qh, tau)
    surface = base.build_training_surface(K, rho, qh, tau, train_seed)

    selected: List[Tuple[str, int, int]] = []
    exhaustive_idx = int(base.v11.select_from_indices(surface, range(len(surface))))
    selected.append(('Exhaustive-training', -1, exhaustive_idx))

    init_base = int(seeds['search_initialization_base'])
    n_init = int(cfg['search_initializations'])
    for method, residual in (('DR-BGS', True), ('Guarded-GP', False)):
        for init in range(n_init):
            search_seed = init_base + init
            pidx, _ = base.v11.guarded_search(surface, residual=residual, seed=search_seed)
            selected.append((method, init, int(pidx)))

    nA = int(cfg['certification_replays_A'])
    nB = int(cfg['certification_replays_B'])
    streams_A = base.prebuild_streams(base.CERT_POOL, K, rho, qh, nA, cert_A_seed)
    streams_B = base.prebuild_streams(base.CERT_POOL, K, rho, qh, nB, cert_B_seed)

    unique = sorted(set(pidx for _, _, pidx in selected))
    evaluations: Dict[int, Dict[str, Any]] = {}
    for pidx in unique:
        arrays_A = simulate_selected_policy(
            scenario, policies[pidx], streams_A, cert_A_seed + 5_000_000 + pidx * 100_000
        )
        arrays_B = simulate_selected_policy(
            scenario, policies[pidx], streams_B, cert_B_seed + 5_000_000 + pidx * 100_000
        )
        sum_A = summarize_batch(arrays_A)
        sum_B = summarize_batch(arrays_B)
        evaluations[pidx] = {
            'A': sum_A,
            'B': sum_B,
            'confirmed': int(sum_A['certified'] == 1 and sum_B['certified'] == 1),
        }

    run_rows: List[Dict[str, Any]] = []
    for method, init, pidx in selected:
        ev = evaluations[pidx]
        on, off = policies[pidx]
        run_rows.append({
            **row,
            'method': method,
            'init_index': init,
            'search_seed': -1 if init < 0 else init_base + init,
            'selected_idx': pidx,
            'selected_alpha_on': on,
            'selected_alpha_off': off,
            'batch_A_certified': ev['A']['certified'],
            'batch_B_certified': ev['B']['certified'],
            'confirmed_certified': ev['confirmed'],
            **{f'A_{k}': v for k, v in ev['A'].items()},
            **{f'B_{k}': v for k, v in ev['B'].items()},
        })

    policy_rows: List[Dict[str, Any]] = []
    for pidx, ev in evaluations.items():
        on, off = policies[pidx]
        methods = sorted(set(method for method, _, idx2 in selected if idx2 == pidx))
        n_run_refs = sum(1 for _, _, idx2 in selected if idx2 == pidx)
        policy_rows.append({
            **row,
            'policy_idx': pidx,
            'alpha_on': on,
            'alpha_off': off,
            'referenced_by_methods': ';'.join(methods),
            'run_references': n_run_refs,
            'batch_A_certified': ev['A']['certified'],
            'batch_B_certified': ev['B']['certified'],
            'confirmed_certified': ev['confirmed'],
            **{f'A_{k}': v for k, v in ev['A'].items()},
            **{f'B_{k}': v for k, v in ev['B'].items()},
        })

    return {
        'scenario': row,
        'training_surface': surface.to_dict(orient='records'),
        'run_rows': run_rows,
        'policy_rows': policy_rows,
    }


def exact_lower_successes(successes: int, trials: int, alpha: float = 0.05) -> float:
    if successes <= 0:
        return 0.0
    from scipy.stats import beta
    return float(beta.ppf(alpha, successes, trials - successes + 1))


def make_outputs(results: List[Dict[str, Any]], cfg: Dict[str, Any], out: Path, started: float) -> None:
    run_df = pd.DataFrame([r for res in results for r in res['run_rows']])
    pol_df = pd.DataFrame([r for res in results for r in res['policy_rows']])
    surf_df = pd.DataFrame([r for res in results for r in res['training_surface']])
    # Restore scenario identifiers to training surface rows.
    chunks = []
    for res in results:
        d = pd.DataFrame(res['training_surface'])
        for k, v in res['scenario'].items():
            d[k] = v
        chunks.append(d)
    surf_df = pd.concat(chunks, ignore_index=True)

    run_df.to_csv(out / 'V13_CONFIRMATORY_RUNS.csv', index=False)
    pol_df.to_csv(out / 'V13_CONFIRMATORY_UNIQUE_POLICIES.csv', index=False)
    surf_df.to_csv(out / 'V13_CONFIRMATORY_TRAINING_SURFACES.csv', index=False)

    method_summary = run_df.groupby('method').agg(
        runs=('confirmed_certified', 'size'),
        batch_A_certified=('batch_A_certified', 'sum'),
        batch_B_certified=('batch_B_certified', 'sum'),
        confirmed_certified=('confirmed_certified', 'sum'),
        unique_scenario_policy_pairs=('selected_idx', 'nunique'),
        median_A_upper_H=('A_upper_H', 'median'),
        median_A_upper_L=('A_upper_L', 'median'),
        median_B_upper_H=('B_upper_H', 'median'),
        median_B_upper_L=('B_upper_L', 'median'),
    ).reset_index()
    method_summary['confirmed_fraction'] = method_summary['confirmed_certified'] / method_summary['runs']
    method_summary['exact_95pct_lower_bound'] = [
        exact_lower_successes(int(s), int(n))
        for s, n in zip(method_summary['confirmed_certified'], method_summary['runs'])
    ]
    method_summary.to_csv(out / 'V13_CONFIRMATORY_METHOD_SUMMARY.csv', index=False)

    scenario_summary = run_df.groupby(['scenario_id', 'qH', 'tau', 'method']).agg(
        runs=('confirmed_certified', 'size'),
        confirmed_certified=('confirmed_certified', 'sum'),
        distinct_selected_policies=('selected_idx', 'nunique'),
        max_A_upper=('A_upper_H', lambda s: float(max(s.max(), run_df.loc[s.index, 'A_upper_L'].max()))),
        max_B_upper=('B_upper_H', lambda s: float(max(s.max(), run_df.loc[s.index, 'B_upper_L'].max()))),
    ).reset_index()
    scenario_summary['confirmed_fraction'] = scenario_summary['confirmed_certified'] / scenario_summary['runs']
    scenario_summary.to_csv(out / 'V13_CONFIRMATORY_SCENARIO_SUMMARY.csv', index=False)

    primary = cfg['primary_success_rule']
    dr = method_summary[method_summary.method == 'DR-BGS'].iloc[0]
    primary_pass = (
        int(dr.confirmed_certified) >= int(primary['minimum_confirmed_DR_BGS_runs'])
        and int(dr.runs) == int(primary['expected_DR_BGS_runs'])
    )

    key = {
        'study_id': cfg['study_id'],
        'status': 'PASS' if primary_pass else 'FAIL',
        'primary_success_rule': primary,
        'primary_observed': {
            'DR_BGS_confirmed': int(dr.confirmed_certified),
            'DR_BGS_runs': int(dr.runs),
            'DR_BGS_fraction': float(dr.confirmed_fraction),
            'DR_BGS_exact_95pct_lower_bound': float(dr.exact_95pct_lower_bound),
        },
        'method_summary': method_summary.to_dict(orient='records'),
        'unique_policy_summary': {
            'unique_scenario_policy_pairs': int(len(pol_df)),
            'confirmed_pairs': int(pol_df.confirmed_certified.sum()),
            'batch_A_only_failures': int(((pol_df.batch_A_certified == 0) & (pol_df.batch_B_certified == 1)).sum()),
            'batch_B_only_failures': int(((pol_df.batch_A_certified == 1) & (pol_df.batch_B_certified == 0)).sum()),
        },
        'runtime_seconds': float(time.time() - started),
        'python': platform.python_version(),
    }
    (out / 'V13_CONFIRMATORY_KEY_RESULTS.json').write_text(json.dumps(key, indent=2), encoding='utf-8')

    report: List[str] = []
    report += [
        '# V13 Fresh-Seed Confirmatory Absolute-Risk Study', '',
        f"**Status:** {key['status']} under the locked primary rule.", '',
        '## Locked design', '',
        f"The operating point was fixed before result generation at K={cfg['K']} and rho={cfg['rho']}. "
        f"The six physical scenarios cross qH={cfg['qH_values']} and tau={cfg['tau_values']}. "
        f"DR-BGS and the same-anchor guarded GP each use {cfg['search_initializations']} fixed fresh search initializations per scenario. "
        f"Each nomination is tested on two disjoint batches of {cfg['certification_replays_A']} and {cfg['certification_replays_B']} later-pool replays. "
        'A run is counted as confirmed only when both batches independently pass the unchanged 2% protected-blocking, 5% eligible-blocking, and 10% violation-risk gate.', '',
        'The point was selected from the V12 exploratory frontier because it was an interior low-load regime across all six qH/tau combinations. '
        'It is not the original V11 operating regime and does not repair or replace the original 0/120 result.', '',
        '## Primary outcome', '',
        f"The locked primary rule required at least {primary['minimum_confirmed_DR_BGS_runs']} of {primary['expected_DR_BGS_runs']} DR-BGS runs to certify in both independent batches. "
        f"Observed: **{int(dr.confirmed_certified)}/{int(dr.runs)} ({100*float(dr.confirmed_fraction):.2f}%)**, "
        f"with a one-sided exact 95% lower confidence bound of {100*float(dr.exact_95pct_lower_bound):.2f}%.", '',
        '## Method results', '',
        method_summary.to_markdown(index=False, floatfmt='.4f'), '',
        '## Scenario results', '',
        scenario_summary.to_markdown(index=False, floatfmt='.4f'), '',
        '## Duplicate-aware audit', '',
        f"The {len(run_df)} run labels map to {len(pol_df)} unique scenario-policy pairs. "
        f"Of those unique pairs, {int(pol_df.confirmed_certified.sum())} passed both independent batches. "
        f"Batch-A-only failures: {key['unique_policy_summary']['batch_A_only_failures']}; "
        f"batch-B-only failures: {key['unique_policy_summary']['batch_B_only_failures']}.", '',
        '## Interpretation boundary', '',
        'This confirms that the unchanged absolute-risk gate can issue stable certificates in a separately locked, low-load operating regime. '
        'It does not show that the original rho=0.70/0.90 regimes are certifiable, and it does not establish live production safety. '
        'The trace slice, privacy-label synthesis, pressure conversion, and moving-block replay limitations remain unchanged.', '',
    ]
    (out / 'V13_CONFIRMATORY_REPORT.md').write_text('\n'.join(report), encoding='utf-8')

    # Simple figure with method confirmed fractions.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.bar(method_summary['method'], method_summary['confirmed_fraction'])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel('Confirmed fraction (both independent batches)')
    ax.set_title('Fresh-seed strict absolute-risk confirmation at K=40, rho=0.05')
    for i, r in method_summary.iterrows():
        ax.text(i, float(r.confirmed_fraction) + 0.02,
                f"{int(r.confirmed_certified)}/{int(r.runs)}", ha='center')
    fig.tight_layout()
    fig.savefig(out / 'V13_CONFIRMATORY_METHOD_RESULTS.png', dpi=180)
    plt.close(fig)


def write_postrun_hashes(out: Path) -> None:
    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != 'V13_POSTRUN_SHA256SUMS.txt')
    lines = [f'{sha256_file(p)}  {p.name}' for p in files]
    (out / 'V13_POSTRUN_SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--validate-only', action='store_true')
    args = ap.parse_args()

    cfg = load_config(args.config)
    validate_config(cfg)
    if args.validate_only:
        print(json.dumps({'valid': True, 'scenarios': scenario_rows(cfg)}, indent=2))
        return

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in ['V13_CONFIRMATORY_RUNS.csv', 'V13_CONFIRMATORY_KEY_RESULTS.json']):
        raise RuntimeError('Result files already exist. Refusing to overwrite a locked confirmatory run.')

    started = time.time()
    scenarios = scenario_rows(cfg)
    results: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_scenario, row, cfg): row['scenario_id'] for row in scenarios}
        for fut in as_completed(futures):
            sid = futures[fut]
            results.append(fut.result())
            print(f'Completed {sid} at {time.strftime("%Y-%m-%d %H:%M:%S")}', flush=True)
    results.sort(key=lambda x: x['scenario']['scenario_id'])
    make_outputs(results, cfg, out, started)
    write_postrun_hashes(out)
    print(f'V13 confirmatory run complete in {time.time()-started:.1f} s', flush=True)


if __name__ == '__main__':
    main()
