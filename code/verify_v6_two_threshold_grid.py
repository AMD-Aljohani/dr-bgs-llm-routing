#!/usr/bin/env python3
from pathlib import Path
import sys
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as h

summ = pd.read_csv(BASE / 'results' / 'hysteresis_summary_all.csv')
scenarios = {s.scenario_id: s for s in h.existing_development_scenarios() + h.fresh_validation_scenarios()}
rows = []
for _, r in summ.iterrows():
    s = scenarios[r.scenario_id]
    on, off = float(r.selected_alpha_on), float(r.selected_alpha_off)
    z321 = core.diffusion_metrics(s, on, off, N=321)
    z641 = core.diffusion_metrics(s, on, off, N=641)
    rows.append({
        'scenario_id': s.scenario_id,
        'group': r.group,
        'alpha_on': on,
        'alpha_off': off,
        'mass_error_321': z321['mass_error'],
        'stationary_residual_321': z321['stationary_residual_inf'],
        'minimum_probability_321': z321['min_probability'],
        'objective_321': z321['objective'],
        'objective_641': z641['objective'],
        'objective_relative_change_321_641': abs(z641['objective'] - z321['objective']) / max(abs(z641['objective']), 1e-12),
        'W_relative_change_321_641': abs(z641['W'] - z321['W']) / max(abs(z641['W']), 1e-12),
        'BH_absolute_change_321_641': abs(z641['B_H'] - z321['B_H']),
        'BL_absolute_change_321_641': abs(z641['B_L'] - z321['B_L']),
        'cloud_absolute_change_321_641': abs(z641['cloud_fraction'] - z321['cloud_fraction']),
    })

df = pd.DataFrame(rows)
out = BASE / 'results' / 'v6_two_threshold_grid_verification_321_641.csv'
df.to_csv(out, index=False)
print(df.describe().to_string())
