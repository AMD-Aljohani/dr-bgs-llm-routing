#!/usr/bin/env python3
"""Trace-derived, independently certified V11 study.

The script uses a compact public BurstGPT slice. Arrival gaps and token counts are
trace-derived; privacy labels, moving-block resampling, and phase durations are
synthetic. Search and certification streams are chronologically separated.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.stats import beta as beta_dist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from run_smpt_campaign import Scenario, diffusion_metrics, sim_threshold  # noqa: E402

TRACE = ROOT / "trace_data" / "BurstGPT_first100_public.csv"
OUT = ROOT / "v11_results"
OUT.mkdir(parents=True, exist_ok=True)

K = 40.0
MU = 120.0
BETA = 1.0
DEACT = 0.75
GRID_LEVELS = np.linspace(0.05 * K, 0.95 * K, 19)
POLICIES = [(float(on), float(off)) for on in GRID_LEVELS for off in GRID_LEVELS if off <= on + 1e-12]
assert len(POLICIES) == 190

RHO_VALUES = (0.70, 0.90)
QH_VALUES = (0.20, 0.50, 0.80)
TAU_VALUES = (0.50, 2.00)
TRAIN_REPS = 12
HOLDOUT_REPS = 30
CERT_REPS = 150
REQUESTS_PER_REPLAY = 560
BLOCK_LEN = 8
SEARCH_BUDGET = 20
SEEDS = tuple(range(5))
BH_LIMIT = 0.02
BL_LIMIT = 0.05
RISK_H = 0.10
RISK_L = 0.10
FAMILY_ALPHA = 0.05
EPS = 1e-12


def cp_upper(x: int, n: int, alpha: float) -> float:
    if n <= 0:
        return 1.0
    if x >= n:
        return 1.0
    return float(beta_dist.ppf(1.0 - alpha, x + 1, n - x))


def policy_coords() -> np.ndarray:
    return np.array([[on / K, off / K] for on, off in POLICIES], dtype=float)


def maximin_fill(X: np.ndarray, selected: Iterable[int], n: int, seed: int) -> List[int]:
    rng = np.random.default_rng(seed)
    selected = list(dict.fromkeys(int(i) for i in selected))
    if not selected:
        selected = [int(rng.integers(len(X)))]
    while len(selected) < n:
        selected_set = set(selected)
        rem = np.array([i for i in range(len(X)) if i not in selected_set], dtype=int)
        d = cdist(X[rem], X[selected]).min(axis=1)
        ties = rem[np.flatnonzero(np.isclose(d, d.max()))]
        selected.append(int(rng.choice(ties)))
    return selected


def search_score(m: Dict[str, float]) -> float:
    return (
        m["cloud_fraction"]
        + 0.15 * m["W"]
        + 50.0 * max(m["B_H"] - BH_LIMIT, 0.0)
        + 20.0 * max(m["B_L"] - BL_LIMIT, 0.0)
    )


def op_cost(m: Dict[str, float]) -> float:
    return m["cloud_fraction"] + 0.15 * m["W"]


def select_from_indices(surface: pd.DataFrame, indices: Iterable[int]) -> int:
    ids = list(dict.fromkeys(int(i) for i in indices))
    sub = surface.iloc[ids]
    feasible = sub[(sub.train_B_H <= BH_LIMIT) & (sub.train_B_L <= BL_LIMIT)]
    if len(feasible):
        return int(feasible.sort_values(["train_op_cost", "policy_idx"]).iloc[0].policy_idx)
    return int(sub.sort_values(["train_score", "policy_idx"]).iloc[0].policy_idx)


def guarded_search(surface: pd.DataFrame, residual: bool, seed: int) -> Tuple[int, List[int]]:
    X = policy_coords()
    y = surface.train_score.to_numpy(float)
    se = surface.train_score_se.to_numpy(float)
    diff = surface.diffusion_score.to_numpy(float)
    targets = [(0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.50, 0.05), (0.50, 0.50)]
    anchors = [int(np.argmin(np.linalg.norm(X - np.array(t), axis=1))) for t in targets]
    if residual:
        anchors += list(map(int, np.argsort(diff)[:3]))
    seen = maximin_fill(X, anchors, min(max(8, len(set(anchors))), SEARCH_BUDGET), seed)
    kernel = ConstantKernel(1.0, "fixed") * Matern([0.2, 0.2], nu=2.5, length_scale_bounds="fixed")
    while len(seen) < SEARCH_BUDGET:
        ids = np.array(seen, dtype=int)
        if residual:
            A = np.column_stack([np.ones(len(ids)), diff[ids]])
            coef = np.linalg.lstsq(A, y[ids], rcond=None)[0]
            trend = coef[0] + coef[1] * diff
            train = y[ids] - trend[ids]
        else:
            trend = np.zeros(len(y), dtype=float)
            train = y[ids]
        center = float(train.mean())
        scale = max(float(train.std()), 1e-6)
        z = (train - center) / scale
        noise = np.maximum(se[ids] / scale, 1e-6) ** 2 + 1e-6
        gp = GaussianProcessRegressor(kernel=kernel, alpha=noise, optimizer=None, normalize_y=False)
        gp.fit(X[ids], z)
        rem = np.array([i for i in range(len(X)) if i not in set(seen)], dtype=int)
        mu, sd = gp.predict(X[rem], return_std=True)
        pred = trend[rem] + center + scale * mu
        beta_t = 2.0 + 0.25 * math.log1p(len(seen))
        lcb = pred - beta_t * scale * sd
        seen.append(int(rem[np.argmin(lcb)]))
    return select_from_indices(surface, seen), seen


def load_trace() -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    df = pd.read_csv(TRACE)
    df = df[df["Total tokens"] > 0].copy().reset_index(drop=True)
    assert len(df) == 95
    train = df.iloc[:60].copy().reset_index(drop=True)
    cert = df.iloc[60:].copy().reset_index(drop=True)
    med = float(train["Total tokens"].median())
    return train, cert, med


def pool_arrays(pool: pd.DataFrame, median_tokens: float) -> Tuple[np.ndarray, np.ndarray]:
    ts = pool["Timestamp"].to_numpy(float)
    gaps = np.diff(ts)
    positive = gaps[gaps > 0]
    first_gap = float(np.median(positive)) if len(positive) else 1.0
    gaps = np.r_[first_gap, np.maximum(gaps, 0.0)]
    tokens = pool["Total tokens"].to_numpy(float)
    jumps = 3.0 * tokens / median_tokens
    jumps = np.clip(jumps, 0.10, 0.25 * K)
    return gaps, jumps


def block_bootstrap_stream(pool: pd.DataFrame, median_tokens: float, rho: float, qh: float, seed: int):
    rng = np.random.default_rng(seed)
    gaps, base_jumps = pool_arrays(pool, median_tokens)
    n_pool = len(gaps)
    out_gaps: List[float] = []
    out_jumps: List[float] = []
    while len(out_gaps) < REQUESTS_PER_REPLAY:
        start = int(rng.integers(n_pool))
        for k in range(BLOCK_LEN):
            idx = (start + k) % n_pool
            out_gaps.append(float(gaps[idx]))
            out_jumps.append(float(base_jumps[idx]))
            if len(out_gaps) >= REQUESTS_PER_REPLAY:
                break
    gaps_a = np.asarray(out_gaps, float)
    jumps = np.asarray(out_jumps, float)
    desired_horizon = float(jumps.sum() / (rho * MU))
    scale = desired_horizon / max(float(gaps_a.sum()), EPS)
    times = np.cumsum(gaps_a * scale)
    horizon = float(times[-1] * 1.05)
    burn = float(0.20 * horizon)
    classes = (rng.random(len(times)) >= qh).astype(np.int8)  # 0=H, 1=L
    uniforms = rng.random(len(times))
    return times, classes, jumps, uniforms, horizon, burn


def build_scenario(sid: str, rho: float, qh: float, tau: float, median_tokens: float, train_pool: pd.DataFrame) -> Scenario:
    _, train_jumps = pool_arrays(train_pool, median_tokens)
    mean_jump = float(train_jumps.mean())
    cv = float(train_jumps.std(ddof=1) / max(mean_jump, EPS))
    total_input = rho * MU
    return Scenario(
        scenario_id=sid,
        design="burstgpt_trace_slice",
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


def simulate_policy(s: Scenario, pool: pd.DataFrame, median_tokens: float, rho: float, qh: float,
                    policy_idx: int, rep_seed: int) -> Dict[str, float]:
    stream = block_bootstrap_stream(pool, median_tokens, rho, qh, rep_seed)
    times, classes, jumps, uniforms, horizon, burn = stream
    metrics = sim_threshold(
        s,
        (times, classes, jumps, uniforms),
        horizon,
        burn,
        POLICIES[policy_idx][0],
        POLICIES[policy_idx][1],
        seed=rep_seed + 911,
    )
    metrics["score"] = search_score(metrics)
    metrics["op_cost"] = op_cost(metrics)
    return metrics


def build_surface(s: Scenario, train_pool: pd.DataFrame, median_tokens: float, rho: float, qh: float, scenario_seed: int) -> pd.DataFrame:
    streams = [block_bootstrap_stream(train_pool, median_tokens, rho, qh, scenario_seed + 1009 * r) for r in range(TRAIN_REPS)]
    rows = []
    for idx, (on, off) in enumerate(POLICIES):
        vals = []
        for r, st in enumerate(streams):
            times, classes, jumps, uniforms, horizon, burn = st
            m = sim_threshold(s, (times, classes, jumps, uniforms), horizon, burn, on, off,
                              seed=scenario_seed + 500_000 + 1009 * r)
            m["score"] = search_score(m)
            m["op_cost"] = op_cost(m)
            vals.append(m)
        def mean(name: str) -> float:
            return float(np.mean([v[name] for v in vals]))
        def se(name: str) -> float:
            a = np.asarray([v[name] for v in vals], float)
            return float(a.std(ddof=1) / math.sqrt(len(a)))
        dm = diffusion_metrics(s, on, off, N=161)
        rows.append({
            "scenario_id": s.scenario_id,
            "policy_idx": idx,
            "alpha_on": on,
            "alpha_off": off,
            "train_score": mean("score"),
            "train_score_se": se("score"),
            "train_op_cost": mean("op_cost"),
            "train_W": mean("W"),
            "train_B_H": mean("B_H"),
            "train_B_L": mean("B_L"),
            "train_cloud_fraction": mean("cloud_fraction"),
            "diffusion_score": search_score(dm),
            "diffusion_W": dm["W"],
            "diffusion_B_H": dm["B_H"],
            "diffusion_B_L": dm["B_L"],
            "diffusion_cloud_fraction": dm["cloud_fraction"],
        })
    return pd.DataFrame(rows)


def evaluate_policy(s: Scenario, pool: pd.DataFrame, median_tokens: float, rho: float, qh: float,
                    policy_idx: int, seeds: Iterable[int]) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        m = simulate_policy(s, pool, median_tokens, rho, qh, policy_idx, int(seed))
        rows.append(m)
    return pd.DataFrame(rows)


def main() -> None:
    train_pool, cert_pool, median_tokens = load_trace()
    trace_stats = {
        "rows_source": 100,
        "positive_rows": 95,
        "training_rows": 60,
        "certification_rows": 35,
        "training_median_total_tokens": median_tokens,
        "training_mean_total_tokens": float(train_pool["Total tokens"].mean()),
        "certification_mean_total_tokens": float(cert_pool["Total tokens"].mean()),
        "training_timestamp_span_s": float(train_pool.Timestamp.iloc[-1] - train_pool.Timestamp.iloc[0]),
        "certification_timestamp_span_s": float(cert_pool.Timestamp.iloc[-1] - cert_pool.Timestamp.iloc[0]),
    }
    (OUT / "trace_slice_stats.json").write_text(json.dumps(trace_stats, indent=2))

    all_surfaces = []
    run_rows = []
    cert_cache: Dict[Tuple[str, int], Dict[str, float]] = {}
    hold_cache: Dict[Tuple[str, int], Dict[str, float]] = {}
    scenario_counter = 0
    for rho in RHO_VALUES:
        for qh in QH_VALUES:
            for tau in TAU_VALUES:
                scenario_counter += 1
                sid = f"BG{scenario_counter:02d}"
                s = build_scenario(sid, rho, qh, tau, median_tokens, train_pool)
                scen_seed = 2026071800 + 10000 * scenario_counter
                surface = build_surface(s, train_pool, median_tokens, rho, qh, scen_seed)
                surface["rho"] = rho
                surface["qH"] = qh
                surface["tau"] = tau
                all_surfaces.append(surface)
                exhaustive_idx = select_from_indices(surface, range(len(surface)))

                methods = {
                    "DR-BGS": True,
                    "Guarded-GP": False,
                }
                for method, residual in methods.items():
                    for init_seed in SEEDS:
                        selected_idx, seen = guarded_search(surface, residual=residual,
                                                           seed=20260718 + init_seed)
                        key_h = (sid, selected_idx)
                        if key_h not in hold_cache:
                            hold = evaluate_policy(
                                s, cert_pool, median_tokens, rho, qh, selected_idx,
                                [scen_seed + 2_000_000 + 1009 * r for r in range(HOLDOUT_REPS)],
                            )
                            hold_cache[key_h] = {k: float(hold[k].mean()) for k in ["op_cost", "score", "W", "B_H", "B_L", "cloud_fraction"]}
                        key_ref = (sid, exhaustive_idx)
                        if key_ref not in hold_cache:
                            hold = evaluate_policy(
                                s, cert_pool, median_tokens, rho, qh, exhaustive_idx,
                                [scen_seed + 2_000_000 + 1009 * r for r in range(HOLDOUT_REPS)],
                            )
                            hold_cache[key_ref] = {k: float(hold[k].mean()) for k in ["op_cost", "score", "W", "B_H", "B_L", "cloud_fraction"]}
                        if key_h not in cert_cache:
                            cert = evaluate_policy(
                                s, cert_pool, median_tokens, rho, qh, selected_idx,
                                [scen_seed + 4_000_000 + 1009 * r for r in range(CERT_REPS)],
                            )
                            vh = int((cert.B_H > BH_LIMIT).sum())
                            vl = int((cert.B_L > BL_LIMIT).sum())
                            alpha_each = FAMILY_ALPHA / 2.0
                            uh = cp_upper(vh, CERT_REPS, alpha_each)
                            ul = cp_upper(vl, CERT_REPS, alpha_each)
                            cert_cache[key_h] = {
                                "viol_H": vh,
                                "viol_L": vl,
                                "upper_H": uh,
                                "upper_L": ul,
                                "certified": int(uh <= RISK_H and ul <= RISK_L),
                                "cert_mean_B_H": float(cert.B_H.mean()),
                                "cert_mean_B_L": float(cert.B_L.mean()),
                                "cert_mean_W": float(cert.W.mean()),
                                "cert_mean_cloud": float(cert.cloud_fraction.mean()),
                            }
                        h = hold_cache[key_h]
                        ref = hold_cache[key_ref]
                        cert_result = cert_cache[key_h]
                        excess = max(0.0, (h["op_cost"] - ref["op_cost"]) / max(abs(ref["op_cost"]), EPS))
                        run_rows.append({
                            "scenario_id": sid,
                            "rho": rho,
                            "qH": qh,
                            "tau": tau,
                            "method": method,
                            "init_seed": init_seed,
                            "selected_idx": selected_idx,
                            "selected_alpha_on": POLICIES[selected_idx][0],
                            "selected_alpha_off": POLICIES[selected_idx][1],
                            "exhaustive_train_idx": exhaustive_idx,
                            "evaluated_policies": len(seen),
                            "holdout_op_cost": h["op_cost"],
                            "holdout_B_H": h["B_H"],
                            "holdout_B_L": h["B_L"],
                            "holdout_cloud_fraction": h["cloud_fraction"],
                            "holdout_excess": excess,
                            **cert_result,
                        })
                print(f"completed {sid}: rho={rho}, qH={qh}, tau={tau}")

    surfaces = pd.concat(all_surfaces, ignore_index=True)
    runs = pd.DataFrame(run_rows)
    surfaces.to_csv(OUT / "trace_policy_surfaces.csv", index=False)
    runs.to_csv(OUT / "trace_risk_runs.csv", index=False)

    summary = runs.groupby("method").agg(
        runs=("certified", "size"),
        certified_runs=("certified", "sum"),
        certified_fraction=("certified", "mean"),
        median_holdout_excess=("holdout_excess", "median"),
        p90_holdout_excess=("holdout_excess", lambda x: float(x.quantile(0.9))),
        max_holdout_excess=("holdout_excess", "max"),
        median_cloud_fraction=("holdout_cloud_fraction", "median"),
        max_upper_H=("upper_H", "max"),
        max_upper_L=("upper_L", "max"),
        abstentions=("certified", lambda x: int((x == 0).sum())),
    ).reset_index()
    summary["search_plus_cert_reps"] = SEARCH_BUDGET * TRAIN_REPS + CERT_REPS
    summary["exhaustive_plus_cert_reps"] = len(POLICIES) * TRAIN_REPS + CERT_REPS
    summary["replication_reduction"] = 1.0 - summary.search_plus_cert_reps / summary.exhaustive_plus_cert_reps
    summary.to_csv(OUT / "trace_risk_summary.csv", index=False)

    scenario_summary = runs.groupby(["scenario_id", "rho", "qH", "tau", "method"]).agg(
        certified_fraction=("certified", "mean"),
        max_excess=("holdout_excess", "max"),
        median_excess=("holdout_excess", "median"),
        max_upper_H=("upper_H", "max"),
        max_upper_L=("upper_L", "max"),
    ).reset_index()
    scenario_summary.to_csv(OUT / "trace_risk_by_scenario.csv", index=False)

    key = {
        "trace_stats": trace_stats,
        "policy_count": len(POLICIES),
        "scenarios": scenario_counter,
        "methods": list(summary.method),
        "search_budget": SEARCH_BUDGET,
        "train_reps": TRAIN_REPS,
        "cert_reps": CERT_REPS,
        "BH_limit": BH_LIMIT,
        "BL_limit": BL_LIMIT,
        "risk_H": RISK_H,
        "risk_L": RISK_L,
        "family_alpha": FAMILY_ALPHA,
        "summary": summary.to_dict(orient="records"),
    }
    (OUT / "V11_KEY_RESULTS.json").write_text(json.dumps(key, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
