#!/usr/bin/env python3
"""Reproduce service-law selection, bootstrap intervals, and calibration figure.

Run from this directory:
    python analyze_calibration.py

Inputs:
    qwen25_7b_rtx3090_direct_telemetry_summary.csv
Outputs:
    service_law_model_comparison.csv
    service_law_bootstrap_summary.csv
    service_law_bootstrap_draws.npz
    fig_calibration_service_fit.pdf/png
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
SEED = 20260717
N_BOOT = 20000

def exp_law(z, a, b): return a * np.exp(-b * z)
def reciprocal_law(z, a, b): return a / (1.0 + b * z)
def power_law(z, a, b): return a * (1.0 + z) ** (-b)
def linear_law(z, a, b): return a - b * z

raw = pd.read_csv(ROOT / 'qwen25_7b_rtx3090_direct_telemetry_summary.csv')
x = raw['kv_usage_mean_pct'].to_numpy(float)
xsd = raw['kv_usage_sd_pct'].to_numpy(float)
y = raw['decode_rate_mean_tok_s'].to_numpy(float)
ysd = raw['decode_rate_sd_tok_s'].to_numpy(float)
sweeps = int(raw['sweeps'].iloc[0])

models = [
    ('Exponential', exp_law, [54.0, 0.034], r'$a e^{-bz}$'),
    ('Reciprocal', reciprocal_law, [57.0, 0.06], r'$a/(1+bz)$'),
    ('Power', power_law, [75.0, 0.34], r'$a(1+z)^{-b}$'),
    ('Linear', linear_law, [50.0, 1.0], r'$a-bz$'),
]
rows = []
fit_map = {}
for name, fun, p0, formula in models:
    popt, _ = curve_fit(fun, x, y, p0=p0, maxfev=10000)
    pred = fun(x, *popt)
    rss = float(np.sum((y - pred) ** 2))
    n, k = len(y), len(popt)
    rmse = float(np.sqrt(rss / n))
    r2 = float(1.0 - rss / np.sum((y - y.mean()) ** 2))
    aic = n * np.log(rss / n) + 2 * k
    aicc = float(aic + 2 * k * (k + 1) / (n - k - 1))
    loo_sq = []
    for i in range(n):
        keep = np.arange(n) != i
        pp, _ = curve_fit(fun, x[keep], y[keep], p0=popt, maxfev=10000)
        loo_sq.append(float((y[i] - fun(x[i], *pp)) ** 2))
    rows.append({
        'model': name, 'formula': formula,
        'parameter_a': popt[0], 'parameter_b': popt[1],
        'R2': r2, 'RMSE_tok_s': rmse, 'AICc': aicc,
        'LOOCV_RMSE_tok_s': float(np.sqrt(np.mean(loo_sq))),
    })
    fit_map[name] = (fun, popt)
model_df = pd.DataFrame(rows).sort_values('AICc')
model_df.to_csv(ROOT / 'service_law_model_comparison.csv', index=False)

fun, point = fit_map['Exponential']
centered_residuals = y - fun(x, *point)
centered_residuals -= centered_residuals.mean()
rng = np.random.default_rng(SEED)
draws = []
for _ in range(N_BOOT):
    xb = np.maximum(0.0, rng.normal(x, xsd / np.sqrt(sweeps)))
    yb = rng.normal(y, ysd / np.sqrt(sweeps)) + rng.choice(centered_residuals, len(y), replace=True)
    try:
        pp, _ = curve_fit(fun, xb, yb, p0=point, maxfev=10000)
        if np.all(np.isfinite(pp)) and pp[0] > 0 and pp[1] > 0:
            draws.append(pp)
    except (RuntimeError, ValueError, FloatingPointError):
        continue
draws = np.asarray(draws)
if len(draws) < 0.95 * N_BOOT:
    raise RuntimeError(f'Only {len(draws)} valid bootstrap fits out of {N_BOOT}')

q = np.quantile(draws, [0.025, 0.5, 0.975], axis=0)
zmax = float(x.max())
beta_norm = draws[:, 1] * zmax
service_fraction = np.exp(-beta_norm)
qbn = np.quantile(beta_norm, [0.025, 0.5, 0.975])
qsf = np.quantile(service_fraction, [0.025, 0.5, 0.975])
summary = pd.DataFrame([
    ['mu_max_tok_s', point[0], q[0,0], q[1,0], q[2,0]],
    ['beta_per_KV_percentage_point', point[1], q[0,1], q[1,1], q[2,1]],
    ['normalized_beta_over_observed_0_to_36.53pct_interval', point[1]*zmax, qbn[0], qbn[1], qbn[2]],
    ['service_fraction_at_max_observed_pressure', np.exp(-point[1]*zmax), qsf[0], qsf[1], qsf[2]],
], columns=['quantity','point_estimate','ci_2.5','bootstrap_median','ci_97.5'])
summary.to_csv(ROOT / 'service_law_bootstrap_summary.csv', index=False)
np.savez_compressed(ROOT / 'service_law_bootstrap_draws.npz',
                    mu_max=draws[:,0], beta_pct=draws[:,1], beta_normalized=beta_norm)

zgrid = np.linspace(0, 40, 300)
subset = draws[::max(1, len(draws)//3000)]
pred = np.array([a*np.exp(-b*zgrid) for a,b in subset])
lo, hi = np.quantile(pred, [0.025, 0.975], axis=0)
fig, ax = plt.subplots(figsize=(7.2, 4.6))
ax.errorbar(x, y, xerr=xsd, yerr=ysd, fmt='o', capsize=3,
            label='Three-sweep means ± SD')
ax.plot(zgrid, fun(zgrid, *point), label='Exponential fit')
ax.fill_between(zgrid, lo, hi, alpha=0.2, label='95% bootstrap band')
ax.set_xlabel('Mean vLLM GPU KV-cache usage (%)')
ax.set_ylabel('Per-stream decode rate (tokens/s)')
ax.set_xlim(0, 40); ax.set_ylim(12, 57)
ax.grid(True, alpha=0.3); ax.legend()
fig.tight_layout()
fig.savefig(ROOT / 'fig_calibration_service_fit.pdf', bbox_inches='tight')
fig.savefig(ROOT / 'fig_calibration_service_fit.png', dpi=220, bbox_inches='tight')
print(model_df.to_string(index=False))
print(summary.to_string(index=False))
