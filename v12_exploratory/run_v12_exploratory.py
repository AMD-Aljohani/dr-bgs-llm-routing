#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("DRBGS_ROOT", "/mnt/data/drbgs_v13/dr-bgs-llm-routing-github-v1.3.0"))
OUT = Path(os.environ.get("V12_OUT", "/mnt/data/V12_exploratory_certification_runs"))
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "v11_code"))
sys.path.insert(0, str(ROOT / "code"))
import run_trace_risk_study as v11  # noqa: E402
from run_smpt_campaign import Scenario, diffusion_metrics, sim_threshold  # noqa: E402

MU = 120.0
BETA = 1.0
DEACT = 0.75
BH_LIMIT = 0.02
BL_LIMIT = 0.05
RISK_LIMIT = 0.10
FAMILY_ALPHA = 0.05
REQUESTS_PER_REPLAY = 560
BLOCK_LEN = 8
SEARCH_BUDGET = 20
TRAIN_REPS = 12
INIT_SEEDS = tuple(range(5))
EPS = 1e-12

BH_GRID = (0.02, 0.03, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35)
BL_GRID = (0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35)
K_GRID = (40.0, 60.0, 80.0, 100.0, 120.0, 160.0, 200.0, 240.0)
RHO_GRID = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40,
            0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90)
QH_GRID = (0.20, 0.50, 0.80)
TAU_BASE_GRID = (0.50, 2.00)
TAU_SWEEP_GRID = (0.10, 0.25, 0.50, 1.00, 2.00)
EVIDENCE_N = (50, 100, 150, 300, 600, 1200)

TRACE = pd.read_csv(ROOT / "trace_data" / "BurstGPT_first100_public.csv")
TRACE = TRACE[TRACE["Total tokens"] > 0].copy().reset_index(drop=True)
TRAIN_POOL = TRACE.iloc[:60].copy().reset_index(drop=True)
CERT_POOL = TRACE.iloc[60:].copy().reset_index(drop=True)
MEDIAN_TOKENS = float(TRAIN_POOL["Total tokens"].median())


def log(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def policies_for_k(K: float) -> List[Tuple[float, float]]:
    levels = np.linspace(0.05 * K, 0.95 * K, 19)
    pol = [(float(on), float(off)) for on in levels for off in levels if off <= on + 1e-12]
    assert len(pol) == 190
    return pol


def pool_arrays(pool: pd.DataFrame, K: float) -> Tuple[np.ndarray, np.ndarray]:
    ts = pool["Timestamp"].to_numpy(float)
    gaps = np.diff(ts)
    positive = gaps[gaps > 0]
    first_gap = float(np.median(positive)) if len(positive) else 1.0
    gaps = np.r_[first_gap, np.maximum(gaps, 0.0)]
    tokens = pool["Total tokens"].to_numpy(float)
    jumps = 3.0 * tokens / MEDIAN_TOKENS
    jumps = np.clip(jumps, 0.10, 0.25 * K)
    return gaps, jumps


def block_bootstrap_stream(pool: pd.DataFrame, K: float, rho: float, qh: float, seed: int):
    rng = np.random.default_rng(seed)
    gaps, base_jumps = pool_arrays(pool, K)
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


def build_scenario(sid: str, K: float, rho: float, qh: float, tau: float) -> Scenario:
    _, train_jumps = pool_arrays(TRAIN_POOL, K)
    mean_jump = float(train_jumps.mean())
    cv = float(train_jumps.std(ddof=1) / max(mean_jump, EPS))
    total_input = rho * MU
    return Scenario(
        scenario_id=sid,
        design="v12_exploratory_burstgpt",
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
    return (m["cloud_fraction"] + 0.15 * m["W"]
            + 50.0 * max(m["B_H"] - BH_LIMIT, 0.0)
            + 20.0 * max(m["B_L"] - BL_LIMIT, 0.0))


def op_cost(m: Dict[str, float]) -> float:
    return m["cloud_fraction"] + 0.15 * m["W"]


def prebuild_streams(pool: pd.DataFrame, K: float, rho: float, qh: float,
                     nreps: int, seed_base: int):
    return [block_bootstrap_stream(pool, K, rho, qh, seed_base + 1009 * r) for r in range(nreps)]


def simulate_matrix(K: float, rho: float, qh: float, tau: float, nreps: int,
                    seed_base: int, pool_name: str = "cert"):
    pool = CERT_POOL if pool_name == "cert" else TRAIN_POOL
    policies = policies_for_k(K)
    s = build_scenario("explore", K, rho, qh, tau)
    streams = prebuild_streams(pool, K, rho, qh, nreps, seed_base)
    bh = np.empty((len(policies), nreps), dtype=np.float64)
    bl = np.empty_like(bh)
    w = np.empty_like(bh)
    cloud = np.empty_like(bh)
    for pidx, (on, off) in enumerate(policies):
        for r, st in enumerate(streams):
            times, classes, jumps, uniforms, horizon, burn = st
            m = sim_threshold(s, (times, classes, jumps, uniforms), horizon, burn,
                              on, off, seed=seed_base + 500_000 + 1009 * r)
            bh[pidx, r] = m["B_H"]
            bl[pidx, r] = m["B_L"]
            w[pidx, r] = m["W"]
            cloud[pidx, r] = m["cloud_fraction"]
    return policies, bh, bl, w, cloud


def cp_cert(bh_vals: np.ndarray, bl_vals: np.ndarray, bh_limit: float = BH_LIMIT,
            bl_limit: float = BL_LIMIT) -> Dict[str, float]:
    n = int(len(bh_vals))
    vh = int(np.sum(bh_vals > bh_limit))
    vl = int(np.sum(bl_vals > bl_limit))
    alpha_each = FAMILY_ALPHA / 2.0
    uh = v11.cp_upper(vh, n, alpha_each)
    ul = v11.cp_upper(vl, n, alpha_each)
    return {
        "n": n,
        "viol_H": vh,
        "viol_L": vl,
        "upper_H": uh,
        "upper_L": ul,
        "certified": int(uh <= RISK_LIMIT and ul <= RISK_LIMIT),
    }


def build_training_surface(K: float, rho: float, qh: float, tau: float,
                           seed_base: int) -> pd.DataFrame:
    policies = policies_for_k(K)
    s = build_scenario("training", K, rho, qh, tau)
    streams = prebuild_streams(TRAIN_POOL, K, rho, qh, TRAIN_REPS, seed_base)
    rows = []
    for pidx, (on, off) in enumerate(policies):
        vals = []
        for r, st in enumerate(streams):
            times, classes, jumps, uniforms, horizon, burn = st
            m = sim_threshold(s, (times, classes, jumps, uniforms), horizon, burn,
                              on, off, seed=seed_base + 500_000 + 1009 * r)
            m["score"] = search_score(m)
            m["op_cost"] = op_cost(m)
            vals.append(m)
        def mean(name: str) -> float:
            return float(np.mean([x[name] for x in vals]))
        def se(name: str) -> float:
            a = np.asarray([x[name] for x in vals], float)
            return float(a.std(ddof=1) / math.sqrt(len(a)))
        dm = diffusion_metrics(s, on, off, N=161)
        rows.append({
            "scenario_id": "training",
            "policy_idx": pidx,
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


def campaign1_worker(args):
    sid, rho, qh, tau, nreps = args
    seed_base = 2026080100 + int(sid[2:]) * 1_000_000
    policies, bh, bl, w, cloud = simulate_matrix(40.0, rho, qh, tau, nreps, seed_base, "cert")
    policy_rows = []
    slo_rows = []
    for pidx, (on, off) in enumerate(policies):
        c = cp_cert(bh[pidx], bl[pidx])
        policy_rows.append({
            "scenario_id": sid, "rho": rho, "qH": qh, "tau": tau,
            "policy_idx": pidx, "alpha_on": on, "alpha_off": off,
            "mean_B_H": float(bh[pidx].mean()),
            "mean_B_L": float(bl[pidx].mean()),
            "mean_W": float(w[pidx].mean()),
            "mean_cloud_fraction": float(cloud[pidx].mean()),
            "mean_op_cost": float((cloud[pidx] + 0.15*w[pidx]).mean()),
            **c,
        })
        for bhlim in BH_GRID:
            vh = int(np.sum(bh[pidx] > bhlim))
            uh = v11.cp_upper(vh, nreps, FAMILY_ALPHA / 2)
            for bllim in BL_GRID:
                vl = int(np.sum(bl[pidx] > bllim))
                ul = v11.cp_upper(vl, nreps, FAMILY_ALPHA / 2)
                slo_rows.append({
                    "scenario_id": sid, "rho": rho, "qH": qh, "tau": tau,
                    "policy_idx": pidx, "BH_limit": bhlim, "BL_limit": bllim,
                    "viol_H": vh, "viol_L": vl, "upper_H": uh, "upper_L": ul,
                    "certified": int(uh <= RISK_LIMIT and ul <= RISK_LIMIT),
                })
    return policy_rows, slo_rows


def run_campaign1(workers: int, nreps: int = 150) -> None:
    out_policy = OUT / "campaign1_all_policy_strict.csv"
    out_slo = OUT / "campaign1_policy_slo_frontier.csv"
    if out_policy.exists() and out_slo.exists():
        log("Campaign 1 outputs already exist; skipping.")
        return
    tasks = []
    i = 0
    for rho in (0.70, 0.90):
        for qh in QH_GRID:
            for tau in TAU_BASE_GRID:
                i += 1
                tasks.append((f"BG{i:02d}", rho, qh, tau, nreps))
    policy_rows, slo_rows = [], []
    log(f"Campaign 1: exhaustive later-pool audit of 190 policies × {len(tasks)} scenarios × {nreps} replays.")
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(campaign1_worker, t): t[0] for t in tasks}
        for fut in as_completed(futs):
            sid = futs[fut]
            p, s = fut.result()
            policy_rows.extend(p); slo_rows.extend(s)
            log(f"Campaign 1 completed {sid}.")
    pdf = pd.DataFrame(policy_rows).sort_values(["scenario_id", "policy_idx"])
    sdf = pd.DataFrame(slo_rows).sort_values(["scenario_id", "BH_limit", "BL_limit", "policy_idx"])
    pdf.to_csv(out_policy, index=False)
    sdf.to_csv(out_slo, index=False)

    strict = pdf.groupby(["scenario_id", "rho", "qH", "tau"]).agg(
        certifiable_policies=("certified", "sum"),
        min_mean_B_H=("mean_B_H", "min"),
        min_mean_B_L=("mean_B_L", "min"),
        min_upper_H=("upper_H", "min"),
        min_upper_L=("upper_L", "min"),
    ).reset_index()
    ratio = pdf.assign(max_mean_ratio=np.maximum(pdf.mean_B_H/BH_LIMIT, pdf.mean_B_L/BL_LIMIT))
    mins = ratio.loc[ratio.groupby("scenario_id").max_mean_ratio.idxmin(),
                     ["scenario_id", "policy_idx", "alpha_on", "alpha_off", "max_mean_ratio", "mean_B_H", "mean_B_L"]]
    strict = strict.merge(mins, on="scenario_id", how="left")
    strict.to_csv(OUT / "campaign1_strict_scenario_summary.csv", index=False)

    frontier = sdf.groupby(["scenario_id", "rho", "qH", "tau", "BH_limit", "BL_limit"]).agg(
        certifiable_policies=("certified", "sum")
    ).reset_index()
    frontier.to_csv(OUT / "campaign1_slo_frontier_summary.csv", index=False)

    # Attach the existing V11 method nominations to the exhaustive frontier.
    v11runs = pd.read_csv(ROOT / "v11_results" / "trace_risk_runs.csv")
    method_front = v11runs[["scenario_id", "method", "init_seed", "selected_idx"]].merge(
        sdf, left_on=["scenario_id", "selected_idx"], right_on=["scenario_id", "policy_idx"], how="left")
    method_sum = method_front.groupby(["method", "BH_limit", "BL_limit"]).agg(
        certified_runs=("certified", "sum"), runs=("certified", "size")
    ).reset_index()
    method_sum["certified_fraction"] = method_sum.certified_runs / method_sum.runs
    method_sum.to_csv(OUT / "campaign1_method_slo_frontier.csv", index=False)
    log("Campaign 1 finished.")


def coarse_worker(args):
    K, rho, qh, tau, nreps, tag = args
    seed_base = 2026081000 + int(round(K*10))*100_000 + int(round(rho*100))*1_000 + int(round(qh*10))*100 + int(round(tau*100))
    policies, bh, bl, w, cloud = simulate_matrix(K, rho, qh, tau, nreps, seed_base, "cert")
    mean_bh = bh.mean(axis=1); mean_bl = bl.mean(axis=1)
    mean_op = (cloud + 0.15*w).mean(axis=1)
    feasible = (mean_bh <= BH_LIMIT) & (mean_bl <= BL_LIMIT)
    ratio = np.maximum(mean_bh/BH_LIMIT, mean_bl/BL_LIMIT)
    best_risk = int(np.argmin(np.column_stack([ratio, mean_op])[:,0]))
    if feasible.any():
        ids = np.flatnonzero(feasible)
        best_feasible = int(ids[np.argmin(mean_op[ids])])
    else:
        best_feasible = -1
    return {
        "tag": tag, "K": K, "rho": rho, "qH": qh, "tau": tau, "screen_reps": nreps,
        "mean_feasible_policies": int(feasible.sum()),
        "min_mean_B_H": float(mean_bh.min()), "min_mean_B_L": float(mean_bl.min()),
        "min_max_mean_ratio": float(ratio.min()),
        "best_risk_policy_idx": best_risk,
        "best_feasible_policy_idx": best_feasible,
        "best_risk_mean_B_H": float(mean_bh[best_risk]),
        "best_risk_mean_B_L": float(mean_bl[best_risk]),
        "best_risk_mean_op_cost": float(mean_op[best_risk]),
    }


def intervention_index(base_rho: float, base_tau: float, K: float, rho: float, tau: float) -> float:
    cap = max(K/40.0 - 1.0, 0.0)
    load = max((base_rho-rho)/base_rho, 0.0)
    delay = max((base_tau-tau)/base_tau, 0.0)
    return cap + load + delay


def choose_candidate_configs(coarse: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sidn = 0
    for base_rho in (0.70, 0.90):
        for qh in QH_GRID:
            for base_tau in TAU_BASE_GRID:
                sidn += 1
                sid = f"BG{sidn:02d}"
                labels: Dict[Tuple[float,float,float,float], List[str]] = {}
                def add(row, label):
                    if row is None: return
                    key = (float(row.K), float(row.rho), float(row.qH), float(row.tau))
                    labels.setdefault(key, []).append(label)

                sub = coarse[(coarse.qH == qh) & (coarse.tau == base_tau) &
                             (coarse.K >= 40.0) & (coarse.rho <= base_rho) &
                             (coarse.tag == "joint_K_rho")].copy()
                sub["intervention_index"] = [intervention_index(base_rho, base_tau, r.K, r.rho, r.tau) for r in sub.itertuples()]
                feasible = sub[sub.mean_feasible_policies > 0]
                # Baseline is always included.
                base = sub[(sub.K == 40.0) & np.isclose(sub.rho, base_rho)]
                add(base.iloc[0] if len(base) else None, "baseline")
                load = feasible[feasible.K == 40.0].sort_values(["rho"], ascending=False)
                add(load.iloc[0] if len(load) else None, "load_only_first_feasible")
                cap = feasible[np.isclose(feasible.rho, base_rho)].sort_values(["K"])
                add(cap.iloc[0] if len(cap) else None, "capacity_only_first_feasible")
                if len(feasible):
                    close = feasible.sort_values(["intervention_index", "K", "rho"], ascending=[True, True, False]).iloc[0]
                else:
                    close = sub.sort_values(["min_max_mean_ratio", "intervention_index"]).iloc[0]
                add(close, "closest_grid_candidate")
                # Neighboring points around the closest candidate.
                ordered = sub.sort_values(["intervention_index", "K", "rho"], ascending=[True, True, False]).reset_index(drop=True)
                pos = int(np.argmin(np.abs(ordered.intervention_index.to_numpy()-float(close.intervention_index))))
                if pos > 0: add(ordered.iloc[pos-1], "near_boundary_harder")
                if pos + 1 < len(ordered): add(ordered.iloc[pos+1], "interior_safer")

                # Delay-only diagnostic at baseline K and rho.
                ds = coarse[(coarse.tag == "tau_sweep") & (coarse.K == 40.0) &
                            np.isclose(coarse.rho, base_rho) & (coarse.qH == qh) &
                            (coarse.tau <= base_tau)].copy()
                dfeas = ds[ds.mean_feasible_policies > 0].sort_values("tau", ascending=False)
                add(dfeas.iloc[0] if len(dfeas) else (ds.sort_values("min_max_mean_ratio").iloc[0] if len(ds) else None),
                    "delay_only_candidate")

                for (K,rho,qh2,tau), labs in labels.items():
                    src = coarse[(coarse.K==K)&np.isclose(coarse.rho,rho)&(coarse.qH==qh2)&np.isclose(coarse.tau,tau)].sort_values("tag").iloc[0]
                    rows.append({
                        "original_scenario_id": sid, "base_rho": base_rho, "base_tau": base_tau,
                        "K": K, "rho": rho, "qH": qh2, "tau": tau,
                        "candidate_labels": ";".join(sorted(set(labs))),
                        "coarse_mean_feasible_policies": int(src.mean_feasible_policies),
                        "coarse_min_max_mean_ratio": float(src.min_max_mean_ratio),
                        "intervention_index": intervention_index(base_rho, base_tau, K, rho, tau),
                    })
    return pd.DataFrame(rows).drop_duplicates(["original_scenario_id","K","rho","qH","tau"])


def refine_worker(row_dict):
    sid = row_dict["original_scenario_id"]
    K = float(row_dict["K"]); rho=float(row_dict["rho"]); qh=float(row_dict["qH"]); tau=float(row_dict["tau"])
    seed_base = 2026082000 + int(sid[2:])*10_000_000 + int(round(K*10))*10_000 + int(round(rho*100))*100 + int(round(tau*10))
    policies, bh, bl, w, cloud = simulate_matrix(K, rho, qh, tau, 30, seed_base, "cert")
    mean_bh=bh.mean(axis=1); mean_bl=bl.mean(axis=1); mean_w=w.mean(axis=1); mean_cloud=cloud.mean(axis=1)
    mean_op=(cloud+0.15*w).mean(axis=1)
    viol_rate=np.maximum((bh>BH_LIMIT).mean(axis=1),(bl>BL_LIMIT).mean(axis=1))
    ratio=np.maximum(mean_bh/BH_LIMIT,mean_bl/BL_LIMIT)
    candidate_ids=set()
    for arr in [np.argsort(viol_rate)[:8], np.argsort(ratio)[:8], np.argsort(mean_bh)[:3], np.argsort(mean_bl)[:3]]:
        candidate_ids.update(map(int,arr))
    feasible=(mean_bh<=BH_LIMIT)&(mean_bl<=BL_LIMIT)
    if feasible.any():
        ids=np.flatnonzero(feasible); candidate_ids.add(int(ids[np.argmin(mean_op[ids])]))
    candidate_ids=sorted(candidate_ids)

    # Exact 150-replay candidate evaluation on fresh streams.
    ncert=150
    streams=prebuild_streams(CERT_POOL,K,rho,qh,ncert,seed_base+20_000_000)
    s=build_scenario("refine",K,rho,qh,tau)
    exact: Dict[int, Dict[str,float]]={}
    for pidx in candidate_ids:
        bhv=[]; blv=[]; wv=[]; cv=[]
        on,off=policies[pidx]
        for r,st in enumerate(streams):
            times,classes,jumps,uniforms,horizon,burn=st
            m=sim_threshold(s,(times,classes,jumps,uniforms),horizon,burn,on,off,
                            seed=seed_base+25_000_000+1009*r)
            bhv.append(m["B_H"]); blv.append(m["B_L"]); wv.append(m["W"]); cv.append(m["cloud_fraction"])
        bhv=np.asarray(bhv); blv=np.asarray(blv); wv=np.asarray(wv); cv=np.asarray(cv)
        c=cp_cert(bhv,blv)
        exact[pidx]={**c,"mean_B_H":float(bhv.mean()),"mean_B_L":float(blv.mean()),
                     "mean_W":float(wv.mean()),"mean_cloud_fraction":float(cv.mean()),
                     "mean_op_cost":float((cv+0.15*wv).mean())}

    surface=build_training_surface(K,rho,qh,tau,seed_base+30_000_000)
    selected=[]
    exhaustive=v11.select_from_indices(surface,range(len(surface)))
    selected.append(("Exhaustive-training",-1,exhaustive))
    for method,residual in (("DR-BGS",True),("Guarded-GP",False)):
        for init in INIT_SEEDS:
            idx,_=v11.guarded_search(surface,residual=residual,seed=20260718+init)
            selected.append((method,init,idx))
    # Evaluate method-selected policies using the same exact streams; add if absent.
    for _,_,pidx in selected:
        if pidx in exact: continue
        bhv=[]; blv=[]; wv=[]; cv=[]; on,off=policies[pidx]
        for r,st in enumerate(streams):
            times,classes,jumps,uniforms,horizon,burn=st
            m=sim_threshold(s,(times,classes,jumps,uniforms),horizon,burn,on,off,
                            seed=seed_base+25_000_000+1009*r)
            bhv.append(m["B_H"]); blv.append(m["B_L"]); wv.append(m["W"]); cv.append(m["cloud_fraction"])
        bhv=np.asarray(bhv); blv=np.asarray(blv); wv=np.asarray(wv); cv=np.asarray(cv)
        exact[pidx]={**cp_cert(bhv,blv),"mean_B_H":float(bhv.mean()),"mean_B_L":float(blv.mean()),
                     "mean_W":float(wv.mean()),"mean_cloud_fraction":float(cv.mean()),
                     "mean_op_cost":float((cv+0.15*wv).mean())}

    candidate_rows=[]
    for pidx in candidate_ids:
        e=exact[pidx]
        candidate_rows.append({**row_dict,"policy_idx":pidx,"alpha_on":policies[pidx][0],"alpha_off":policies[pidx][1],
                               "screen_mean_B_H":float(mean_bh[pidx]),"screen_mean_B_L":float(mean_bl[pidx]),
                               "screen_violation_rate":float(viol_rate[pidx]),"screen_mean_ratio":float(ratio[pidx]),
                               **e})
    method_rows=[]
    for method,init,pidx in selected:
        e=exact[pidx]
        method_rows.append({**row_dict,"method":method,"init_seed":init,"selected_idx":pidx,
                            "selected_alpha_on":policies[pidx][0],"selected_alpha_off":policies[pidx][1],**e})
    config_summary={**row_dict,
        "screen_feasible_policies":int(feasible.sum()),
        "candidate_policies_tested":len(candidate_ids),
        "candidate_certified_policies":int(sum(exact[i]["certified"] for i in candidate_ids)),
        "best_candidate_upper":float(min(max(exact[i]["upper_H"],exact[i]["upper_L"]) for i in candidate_ids)),
        "method_certified_runs":int(sum(exact[p]["certified"] for _,_,p in selected)),
        "method_runs":len(selected),
    }
    return config_summary,candidate_rows,method_rows


def run_campaign2(workers: int, coarse_reps: int = 6) -> None:
    coarse_file=OUT/"campaign2_coarse_operating_envelope.csv"
    candidates_file=OUT/"campaign2_candidate_configs.csv"
    refine_file=OUT/"campaign2_refined_config_summary.csv"
    if not coarse_file.exists():
        tasks=[]
        for K in K_GRID:
            for rho in RHO_GRID:
                for qh in QH_GRID:
                    for tau in TAU_BASE_GRID:
                        tasks.append((K,rho,qh,tau,coarse_reps,"joint_K_rho"))
        for rho in (0.70,0.90):
            for qh in QH_GRID:
                for tau in TAU_SWEEP_GRID:
                    tasks.append((40.0,rho,qh,tau,coarse_reps,"tau_sweep"))
        # Remove exact duplicates but preserve both tags only where useful; joint tag wins at base tau.
        unique={}
        for t in tasks:
            key=(t[0],t[1],t[2],t[3],t[5])
            unique[key]=t
        tasks=list(unique.values())
        log(f"Campaign 2 coarse envelope: {len(tasks)} configurations × 190 policies × {coarse_reps} replays.")
        rows=[]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs={ex.submit(coarse_worker,t):t for t in tasks}
            done=0
            for fut in as_completed(futs):
                rows.append(fut.result()); done+=1
                if done%25==0 or done==len(tasks): log(f"Campaign 2 coarse completed {done}/{len(tasks)} configurations.")
        coarse=pd.DataFrame(rows).sort_values(["tag","qH","tau","K","rho"])
        coarse.to_csv(coarse_file,index=False)
    else:
        log("Campaign 2 coarse output exists; loading.")
        coarse=pd.read_csv(coarse_file)

    candidates=choose_candidate_configs(coarse)
    candidates.to_csv(candidates_file,index=False)
    log(f"Campaign 2 refinement: {len(candidates)} unique candidate configurations.")
    if not refine_file.exists():
        sums=[]; candidates_rows=[]; method_rows=[]
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs={ex.submit(refine_worker,r._asdict()):i for i,r in enumerate(candidates.itertuples(index=False))}
            done=0
            for fut in as_completed(futs):
                s,c,m=fut.result(); sums.append(s); candidates_rows.extend(c); method_rows.extend(m); done+=1
                log(f"Campaign 2 refinement completed {done}/{len(futs)}.")
        pd.DataFrame(sums).to_csv(refine_file,index=False)
        pd.DataFrame(candidates_rows).to_csv(OUT/"campaign2_refined_candidate_policies.csv",index=False)
        pd.DataFrame(method_rows).to_csv(OUT/"campaign2_refined_method_runs.csv",index=False)
    log("Campaign 2 finished.")


def choose_regimes() -> pd.DataFrame:
    coarse=pd.read_csv(OUT/"campaign2_coarse_operating_envelope.csv")
    refined=pd.read_csv(OUT/"campaign2_refined_config_summary.csv")
    rows=[]; sidn=0
    for base_rho in (0.70,0.90):
        for qh in QH_GRID:
            for base_tau in TAU_BASE_GRID:
                sidn+=1; sid=f"BG{sidn:02d}"
                sub=refined[(refined.original_scenario_id==sid)].copy()
                cert=sub[sub.candidate_certified_policies>0].copy()
                if len(cert):
                    boundary=cert.sort_values(["intervention_index","K","rho"],ascending=[True,True,False]).iloc[0]
                else:
                    boundary=sub.sort_values(["best_candidate_upper","intervention_index"]).iloc[0]
                # Candidate path in the broad grid at the base tau.
                grid=coarse[(coarse.tag=="joint_K_rho")&(coarse.qH==qh)&(coarse.tau==base_tau)&
                            (coarse.rho<=base_rho)&(coarse.K>=40)].copy()
                grid["intervention_index"]=[intervention_index(base_rho,base_tau,r.K,r.rho,r.tau) for r in grid.itertuples()]
                grid=grid.sort_values(["intervention_index","K","rho"],ascending=[True,True,False]).reset_index(drop=True)
                dist=np.abs(grid.K-boundary.K)/40 + np.abs(grid.rho-boundary.rho)/base_rho
                pos=int(np.argmin(dist.to_numpy()))
                picks=[("baseline",40.0,base_rho,qh,base_tau)]
                if pos>0:
                    r=grid.iloc[pos-1]; picks.append(("near_boundary_harder",float(r.K),float(r.rho),qh,base_tau))
                picks.append(("boundary_candidate",float(boundary.K),float(boundary.rho),qh,float(boundary.tau)))
                if pos+1<len(grid):
                    r=grid.iloc[pos+1]; picks.append(("interior_safer",float(r.K),float(r.rho),qh,base_tau))
                # Deduplicate while retaining labels.
                d={}
                for lab,K,rho,qh2,tau in picks:
                    key=(K,rho,qh2,tau); d.setdefault(key,[]).append(lab)
                for (K,rho,qh2,tau),labs in d.items():
                    rows.append({"original_scenario_id":sid,"base_rho":base_rho,"base_tau":base_tau,
                                 "regime":";".join(labs),"K":K,"rho":rho,"qH":qh2,"tau":tau,
                                 "intervention_index":intervention_index(base_rho,base_tau,K,rho,tau),
                                 "boundary_found_certifiable":int(len(cert)>0)})
    return pd.DataFrame(rows)


def evidence_worker(row_dict):
    sid=row_dict["original_scenario_id"]; K=float(row_dict["K"]); rho=float(row_dict["rho"]); qh=float(row_dict["qH"]); tau=float(row_dict["tau"])
    seed_base=2026083000+int(sid[2:])*10_000_000+int(round(K*10))*10_000+int(round(rho*100))*100+int(round(tau*10))
    policies=policies_for_k(K); s=build_scenario("evidence",K,rho,qh,tau)
    surface=build_training_surface(K,rho,qh,tau,seed_base)
    selected=[]
    exhaustive=v11.select_from_indices(surface,range(len(surface)))
    selected.append(("Exhaustive-training",-1,exhaustive))
    for method,residual in (("DR-BGS",True),("Guarded-GP",False)):
        for init in INIT_SEEDS:
            idx,_=v11.guarded_search(surface,residual=residual,seed=20260718+init)
            selected.append((method,init,idx))
    # Exploratory risk-screen oracle candidate using 30 later-pool replays.
    _,bh30,bl30,w30,c30=simulate_matrix(K,rho,qh,tau,30,seed_base+5_000_000,"cert")
    risk=np.maximum((bh30>BH_LIMIT).mean(axis=1),(bl30>BL_LIMIT).mean(axis=1))
    op=(c30+0.15*w30).mean(axis=1)
    oracle=int(np.lexsort((op,risk))[0])
    selected.append(("Risk-screen-oracle",-1,oracle))

    streams=prebuild_streams(CERT_POOL,K,rho,qh,max(EVIDENCE_N),seed_base+20_000_000)
    arrays={}
    for pidx in sorted(set(p for _,_,p in selected)):
        bh=[]; bl=[]; w=[]; cloud=[]; on,off=policies[pidx]
        for r,st in enumerate(streams):
            times,classes,jumps,uniforms,horizon,burn=st
            m=sim_threshold(s,(times,classes,jumps,uniforms),horizon,burn,on,off,
                            seed=seed_base+25_000_000+1009*r)
            bh.append(m["B_H"]); bl.append(m["B_L"]); w.append(m["W"]); cloud.append(m["cloud_fraction"])
        arrays[pidx]=(np.asarray(bh),np.asarray(bl),np.asarray(w),np.asarray(cloud))
    rows=[]
    for method,init,pidx in selected:
        bh,bl,w,cloud=arrays[pidx]
        final=cp_cert(bh,bl)
        for n in EVIDENCE_N:
            c=cp_cert(bh[:n],bl[:n])
            rows.append({**row_dict,"method":method,"init_seed":init,"selected_idx":pidx,
                         "selected_alpha_on":policies[pidx][0],"selected_alpha_off":policies[pidx][1],
                         "evidence_n":n,**c,
                         "mean_B_H":float(bh[:n].mean()),"mean_B_L":float(bl[:n].mean()),
                         "mean_op_cost":float((cloud[:n]+0.15*w[:n]).mean()),
                         "final_1200_certified":final["certified"],
                         "decision_reversal":int(c["certified"]==1 and final["certified"]==0)})
    return rows


def run_campaign3(workers: int) -> None:
    regimes_file=OUT/"campaign3_regimes.csv"; runs_file=OUT/"campaign3_evidence_frontier_runs.csv"
    regimes=choose_regimes(); regimes.to_csv(regimes_file,index=False)
    if runs_file.exists():
        log("Campaign 3 output exists; skipping."); return
    log(f"Campaign 3: {len(regimes)} regime configurations with evidence prefixes through 1,200 replays.")
    rows=[]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(evidence_worker,r._asdict()):i for i,r in enumerate(regimes.itertuples(index=False))}
        done=0
        for fut in as_completed(futs):
            rows.extend(fut.result()); done+=1
            log(f"Campaign 3 completed {done}/{len(futs)} regimes.")
    df=pd.DataFrame(rows)
    df.to_csv(runs_file,index=False)
    summary=df.groupby(["regime","method","evidence_n"]).agg(
        runs=("certified","size"),certified_runs=("certified","sum"),
        certified_fraction=("certified","mean"),decision_reversals=("decision_reversal","sum"),
        median_upper_H=("upper_H","median"),median_upper_L=("upper_L","median")
    ).reset_index()
    summary.to_csv(OUT/"campaign3_evidence_frontier_summary.csv",index=False)
    log("Campaign 3 finished.")


def make_report() -> None:
    c1=pd.read_csv(OUT/"campaign1_strict_scenario_summary.csv")
    c1m=pd.read_csv(OUT/"campaign1_method_slo_frontier.csv")
    c2=pd.read_csv(OUT/"campaign2_refined_config_summary.csv")
    c2m=pd.read_csv(OUT/"campaign2_refined_method_runs.csv")
    c3=pd.read_csv(OUT/"campaign3_evidence_frontier_runs.csv")

    strict_total=int(c1.certifiable_policies.sum())
    scenarios_with_strict=int((c1.certifiable_policies>0).sum())
    best_ratio=float(c1.max_mean_ratio.min())
    cert_configs=int((c2.candidate_certified_policies>0).sum())
    method_summary=c2m.groupby("method").agg(runs=("certified","size"),certified=("certified","sum")).reset_index()
    method_summary["fraction"]=method_summary.certified/method_summary.runs
    c3sum=c3.groupby(["regime","method","evidence_n"]).certified.mean().reset_index()
    reversals=int(c3.decision_reversal.sum())

    lines=[]
    lines.append("# V12 Exploratory Certification Frontier — Results Report\n")
    lines.append("## Scope and claim boundary\n")
    lines.append("These campaigns are exploratory and do not replace the locked V11 result. The original 2%/5% absolute-SLO study remains 0/120 method runs certified. V12 maps why the gate abstained, where certification becomes feasible, and how certification changes with evidence volume.\n")
    lines.append("## Campaign 1 — Current-system feasibility and SLO frontier\n")
    lines.append(f"All 190 policies were evaluated on the later chronological pool for all 12 original scenarios using 150 independent replays per policy. Under the original 2% protected and 5% eligible blocking limits, {strict_total} policy-scenario combinations were certified; {scenarios_with_strict} of 12 scenarios contained at least one certified policy. The smallest observed best-policy mean-limit ratio across scenarios was {best_ratio:.3f}.\n")
    lines.append("Scenario summary:\n\n")
    lines.append(c1.to_markdown(index=False,floatfmt=".4f")); lines.append("\n")
    lines.append("## Campaign 2 — Engineering operating envelope\n")
    lines.append(f"The coarse screen covered K={list(K_GRID)}, offered-load ratios {list(RHO_GRID)}, protected fractions {list(QH_GRID)}, and activation delays {list(TAU_BASE_GRID)}, plus a dedicated delay sweep. {len(c2)} candidate configurations were refined; {cert_configs} contained at least one candidate policy that passed the exact 150-replay gate.\n")
    lines.append("Method-level certification over refined candidate configurations:\n\n")
    lines.append(method_summary.to_markdown(index=False,floatfmt=".4f")); lines.append("\n")
    first=c2[c2.candidate_certified_policies>0].sort_values(["original_scenario_id","intervention_index"]).groupby("original_scenario_id").head(1)
    if len(first):
        lines.append("First certifiable refined candidate by original scenario, ordered under the declared equal-weight intervention index:\n\n")
        cols=["original_scenario_id","K","rho","qH","tau","candidate_labels","intervention_index","candidate_certified_policies","best_candidate_upper"]
        lines.append(first[cols].to_markdown(index=False,floatfmt=".4f")); lines.append("\n")
    lines.append("## Campaign 3 — Evidence and stability frontier\n")
    lines.append(f"Certification was recomputed at n={list(EVIDENCE_N)} using common 1,200-replay sequences. Prefix certification followed by failure at n=1,200 occurred {reversals} times. Such reversals are exploratory stability diagnostics, not production false-safety estimates.\n")
    pivot=c3sum[c3sum.evidence_n.isin([150,1200])].pivot_table(index=["regime","method"],columns="evidence_n",values="certified").reset_index()
    lines.append(pivot.to_markdown(index=False,floatfmt=".4f")); lines.append("\n")
    lines.append("## Scientifically defensible interpretation\n")
    lines.append("1. The V11 gate behaved correctly: it refused unsupported deployment claims.\n")
    lines.append("2. Campaign 1 determines whether the original failure was caused by search nomination or by absence of any certifiable policy in the fixed policy family.\n")
    lines.append("3. Campaign 2 identifies the operational changes needed before the strict 2%/5% SLO becomes certifiable. Any positive result applies to the changed operating regime, not retroactively to V11.\n")
    lines.append("4. Campaign 3 separates physical infeasibility from statistical evidence limitations and reveals whether small certification batches produce unstable decisions.\n")
    (OUT/"V12_EXPLORATORY_RESULTS_REPORT.md").write_text("\n".join(lines),encoding="utf-8")

    # Machine-readable key results.
    key={
        "campaign1": {"strict_certified_policy_scenario_pairs": strict_total,
                      "scenarios_with_any_strict_certified_policy": scenarios_with_strict,
                      "scenario_count": 12},
        "campaign2": {"refined_configurations": int(len(c2)),
                      "configurations_with_candidate_certification": cert_configs,
                      "method_summary": method_summary.to_dict(orient="records")},
        "campaign3": {"evidence_sizes": list(EVIDENCE_N),"decision_reversals": reversals,
                      "summary": c3sum.to_dict(orient="records")},
    }
    (OUT/"V12_KEY_RESULTS.json").write_text(json.dumps(key,indent=2),encoding="utf-8")


def make_figures() -> None:
    import matplotlib.pyplot as plt
    # Campaign 1 method SLO frontier.
    m=pd.read_csv(OUT/"campaign1_method_slo_frontier.csv")
    for method in m.method.unique():
        z=m[m.method==method].pivot(index="BH_limit",columns="BL_limit",values="certified_fraction")
        fig,ax=plt.subplots(figsize=(8,6)); im=ax.imshow(z.values,origin="lower",aspect="auto",vmin=0,vmax=1)
        ax.set_xticks(range(len(z.columns)),[f"{x:.3g}" for x in z.columns],rotation=45,ha="right")
        ax.set_yticks(range(len(z.index)),[f"{x:.3g}" for x in z.index])
        ax.set_xlabel("Eligible blocking limit"); ax.set_ylabel("Protected blocking limit")
        ax.set_title(f"{method}: certification fraction over 60 nominated runs")
        fig.colorbar(im,ax=ax,label="Certified fraction"); fig.tight_layout()
        fig.savefig(OUT/f"campaign1_{method.lower().replace('-','_')}_slo_frontier.png",dpi=180); plt.close(fig)
    # Campaign 2 envelope: maximum screen-feasible rho by K for each qH,tau.
    c=pd.read_csv(OUT/"campaign2_coarse_operating_envelope.csv")
    c=c[c.tag=="joint_K_rho"]
    rows=[]
    for qh in QH_GRID:
        for tau in TAU_BASE_GRID:
            sub=c[(c.qH==qh)&(c.tau==tau)&(c.mean_feasible_policies>0)]
            for K in K_GRID:
                ss=sub[sub.K==K]
                rows.append({"qH":qh,"tau":tau,"K":K,"max_feasible_rho":float(ss.rho.max()) if len(ss) else np.nan})
    d=pd.DataFrame(rows)
    fig,ax=plt.subplots(figsize=(9,6))
    for (qh,tau),g in d.groupby(["qH","tau"]):
        ax.plot(g.K,g.max_feasible_rho,marker="o",label=f"qH={qh}, tau={tau}")
    ax.set_xlabel("Pressure capacity K"); ax.set_ylabel("Maximum mean-feasible offered-load ratio")
    ax.set_title("Exploratory strict-SLO operating envelope (coarse screen)")
    ax.set_ylim(0,0.95); ax.legend(ncol=2,fontsize=8); fig.tight_layout()
    fig.savefig(OUT/"campaign2_operating_envelope.png",dpi=180); plt.close(fig)
    # Campaign 3 evidence frontier.
    e=pd.read_csv(OUT/"campaign3_evidence_frontier_summary.csv")
    fig,ax=plt.subplots(figsize=(9,6))
    for (regime,method),g in e.groupby(["regime","method"]):
        if method=="Risk-screen-oracle" or method=="Exhaustive-training":
            ax.plot(g.evidence_n,g.certified_fraction,marker="o",label=f"{regime}: {method}")
    ax.set_xscale("log"); ax.set_xticks(EVIDENCE_N,[str(x) for x in EVIDENCE_N])
    ax.set_ylim(-0.02,1.02); ax.set_xlabel("Independent certification replays")
    ax.set_ylabel("Certified fraction"); ax.set_title("Certification stability versus evidence volume")
    ax.legend(fontsize=7,ncol=2); fig.tight_layout()
    fig.savefig(OUT/"campaign3_evidence_frontier.png",dpi=180); plt.close(fig)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--campaign",choices=["1","2","3","all"],default="all")
    ap.add_argument("--workers",type=int,default=3)
    ap.add_argument("--campaign1-reps",type=int,default=150)
    ap.add_argument("--coarse-reps",type=int,default=6)
    args=ap.parse_args()
    log(f"Root: {ROOT}")
    log(f"Output: {OUT}")
    if args.campaign in ("1","all"): run_campaign1(args.workers,args.campaign1_reps)
    if args.campaign in ("2","all"): run_campaign2(args.workers,args.coarse_reps)
    if args.campaign in ("3","all"): run_campaign3(args.workers)
    if args.campaign=="all":
        make_report(); make_figures(); log("V12 report and figures generated.")

if __name__=="__main__":
    main()
