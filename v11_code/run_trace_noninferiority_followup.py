#!/usr/bin/env python3
"""Independent-seed paired noninferiority follow-up for V11.

This script is intentionally separate from the locked absolute-SLO study. It
uses the policies already nominated there and compares each nomination with the
exhaustive training-selection reference on new paired simulation streams.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "v11_code"))
import run_trace_risk_study as base  # noqa: E402

INPUT = ROOT / "v11_results" / "trace_risk_runs.csv"
OUT = ROOT / "v11_results"
REPS = 150
SEED_OFFSET = 12_000_000
COST_MARGIN = 0.05
BH_MARGIN = 0.02
BL_MARGIN = 0.02
RISK = 0.10
FAMILY_ALPHA = 0.05
EPS = 1e-12


def main() -> None:
    runs = pd.read_csv(INPUT)
    train_pool, cert_pool, median_tokens = base.load_trace()
    rows = []
    for _, row in runs.iterrows():
        scenario_number = int(str(row.scenario_id)[-2:])
        scenario_seed = 2026071800 + 10000 * scenario_number
        s = base.build_scenario(
            str(row.scenario_id), float(row.rho), float(row.qH), float(row.tau),
            median_tokens, train_pool,
        )
        seeds = [scenario_seed + SEED_OFFSET + 1009 * r for r in range(REPS)]
        selected = base.evaluate_policy(
            s, cert_pool, median_tokens, float(row.rho), float(row.qH),
            int(row.selected_idx), seeds,
        )
        reference = base.evaluate_policy(
            s, cert_pool, median_tokens, float(row.rho), float(row.qH),
            int(row.exhaustive_train_idx), seeds,
        )
        cost_excess = (selected.op_cost.to_numpy(float) - reference.op_cost.to_numpy(float)) \
            / np.maximum(np.abs(reference.op_cost.to_numpy(float)), EPS)
        delta_bh = selected.B_H.to_numpy(float) - reference.B_H.to_numpy(float)
        delta_bl = selected.B_L.to_numpy(float) - reference.B_L.to_numpy(float)

        v_cost = int(np.sum(cost_excess > COST_MARGIN))
        v_bh = int(np.sum(delta_bh > BH_MARGIN))
        v_bl = int(np.sum(delta_bl > BL_MARGIN))
        alpha_each = FAMILY_ALPHA / 3.0
        u_cost = base.cp_upper(v_cost, REPS, alpha_each)
        u_bh = base.cp_upper(v_bh, REPS, alpha_each)
        u_bl = base.cp_upper(v_bl, REPS, alpha_each)
        certified = int(max(u_cost, u_bh, u_bl) <= RISK)

        rows.append({
            "scenario_id": row.scenario_id,
            "rho": float(row.rho),
            "qH": float(row.qH),
            "tau": float(row.tau),
            "method": row.method,
            "init_seed": int(row.init_seed),
            "selected_idx": int(row.selected_idx),
            "reference_idx": int(row.exhaustive_train_idx),
            "same_policy_as_reference": int(row.selected_idx == row.exhaustive_train_idx),
            "replications": REPS,
            "viol_cost": v_cost,
            "viol_B_H": v_bh,
            "viol_B_L": v_bl,
            "upper_cost": u_cost,
            "upper_B_H": u_bh,
            "upper_B_L": u_bl,
            "max_upper": max(u_cost, u_bh, u_bl),
            "certified": certified,
            "mean_cost_excess": float(np.mean(cost_excess)),
            "median_cost_excess": float(np.median(cost_excess)),
            "p90_cost_excess": float(np.quantile(cost_excess, 0.9)),
            "max_cost_excess": float(np.max(cost_excess)),
            "mean_delta_B_H": float(np.mean(delta_bh)),
            "mean_delta_B_L": float(np.mean(delta_bl)),
        })
        print(f"completed {row.scenario_id} {row.method} seed={int(row.init_seed)}")

    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "trace_noninferiority_runs.csv", index=False)
    summary = detail.groupby("method").agg(
        runs=("certified", "size"),
        certified_runs=("certified", "sum"),
        certified_fraction=("certified", "mean"),
        abstentions=("certified", lambda x: int((x == 0).sum())),
        exact_reference_recoveries=("same_policy_as_reference", "sum"),
        median_max_upper=("max_upper", "median"),
        p90_max_upper=("max_upper", lambda x: float(x.quantile(0.9))),
        max_max_upper=("max_upper", "max"),
        median_mean_cost_excess=("mean_cost_excess", "median"),
        max_mean_cost_excess=("mean_cost_excess", "max"),
    ).reset_index()
    summary.to_csv(OUT / "trace_noninferiority_summary.csv", index=False)

    by_scenario = detail.groupby(["scenario_id", "rho", "qH", "tau", "method"]).agg(
        certified_fraction=("certified", "mean"),
        certified_runs=("certified", "sum"),
        runs=("certified", "size"),
        max_upper=("max_upper", "max"),
        mean_cost_excess=("mean_cost_excess", "mean"),
    ).reset_index()
    by_scenario.to_csv(OUT / "trace_noninferiority_by_scenario.csv", index=False)

    key = {
        "replications": REPS,
        "cost_margin_relative": COST_MARGIN,
        "protected_blocking_margin_absolute": BH_MARGIN,
        "eligible_blocking_margin_absolute": BL_MARGIN,
        "per_event_risk_budget": RISK,
        "family_alpha": FAMILY_ALPHA,
        "summary": summary.to_dict(orient="records"),
    }
    (OUT / "V11_NONINFERIORITY_KEY_RESULTS.json").write_text(json.dumps(key, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
