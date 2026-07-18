#!/usr/bin/env python3
"""Regenerate V8 key results and manuscript figures from archived outputs."""
from pathlib import Path
import json, shutil
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'v8_results'/'component_ablation'/'component_ablation_summary.csv'
OUT=ROOT/'v8_results'; MAN=ROOT/'manuscript'
comp=pd.read_csv(COMP)

def row(b,m):
    return comp[(comp.budget==b)&(comp.method==m)].iloc[0]

r20=row(20,'DR_BGS'); g20=row(20,'guarded_GP'); rg20=row(20,'residual_GP'); s20=row(20,'standard_GP')
r12=row(12,'DR_BGS'); g12=row(12,'guarded_GP')
iid=pd.read_csv(ROOT/'v7_results'/'iid59_drgp'/'iid59_drgp_summary.csv').iloc[0]
lhs=pd.read_csv(ROOT/'v7_results'/'fresh59_drgp'/'fresh59_drgp_summary.csv').iloc[0]
scale=pd.read_csv(ROOT/'v7_results'/'drgp_scaling_summary.csv')
robust=pd.read_csv(ROOT/'v7_results'/'robust_pareto'/'robust_pareto_summary.csv').iloc[0]
simple=pd.read_csv(ROOT/'v7_results'/'optimizer_comparison'/'fixed20_simple_summary.csv')

key={
  'primary_method':'Diffusion-Residual Bayesian Guarded Search (DR-BGS)',
  'reference_definition':'policy selected by exhaustive training evaluation of all policies, evaluated on independent holdout streams',
  'development_scenarios':36,
  'development_runs':180,
  'high_fidelity_policy_budget':20,
  'base_policy_count':190,
  'base_high_fidelity_replication_reduction':1-(20*20+30)/(190*20+30),
  'development':{
    'DR_BGS_max_holdout_excess':float(r20.maximum_regret),
    'DR_BGS_within_1pct':float(r20.runs_within_1pct),
    'DR_BGS_exact_training_policy_recovery':float(r20.exact_training_policy_recovery),
    'guarded_GP_max_holdout_excess':float(g20.maximum_regret),
    'guarded_GP_within_1pct':float(g20.runs_within_1pct),
    'guarded_GP_exact_training_policy_recovery':float(g20.exact_training_policy_recovery),
    'standard_GP_max_holdout_excess':float(s20.maximum_regret),
    'residual_GP_without_guards_max_holdout_excess':float(rg20.maximum_regret),
    'budget12_DR_BGS_max_holdout_excess':float(r12.maximum_regret),
    'budget12_guarded_GP_max_holdout_excess':float(g12.maximum_regret),
  },
  'additional_scenario_checks':{
    'latin_hypercube_scenarios':int(lhs.scenarios),
    'latin_hypercube_runs':int(lhs.runs),
    'latin_hypercube_max_holdout_excess':float(lhs.all_run_max_regret),
    'iid_scenarios':int(iid.scenarios),
    'iid_runs':int(iid.runs),
    'iid_max_holdout_excess':float(iid.all_run_max_regret),
    'iid_within_1pct':float(iid.all_run_success_1pct),
    'iid_exact_training_policy_recovery':float(iid.mean_exact_match),
    'provenance_note':'descriptive additional-scenario evaluation; no immutable preregistration in the archive predates scenario generation, so no formal population reliability bound is claimed'
  },
  'scaling':scale.to_dict(orient='records'),
  'robust_pareto':robust.to_dict(),
  'component_ablation_source':'v8_results/component_ablation/component_ablation_summary.csv'
}
(OUT/'V8_KEY_RESULTS.json').write_text(json.dumps(key,indent=2)+'\n')

# Correct aliases from the earlier output name.
rp=ROOT/'v7_results'/'robust_pareto'
if (rp/'weight_profiles_286.csv').exists(): shutil.copy2(rp/'weight_profiles_286.csv',rp/'weight_profiles_287.csv')
if (rp/'robust_pareto_by_scenario.csv').exists():
    d=pd.read_csv(rp/'robust_pareto_by_scenario.csv')
    d=d.rename(columns={'distinct_optima_286':'distinct_optima_287'})
    d.to_csv(rp/'robust_pareto_by_scenario_v8.csv',index=False)

vals=[]
for label,m in [('Local search','local_search'),('Random subset R&S','random_RS'),('Diffusion top-20','diffusion_top20')]:
    q=simple[simple.method==m].iloc[0]; vals.append((label,100*q.max_regret))
vals += [('Standard GP',100*s20.maximum_regret),('Guarded GP',100*g20.maximum_regret),('DR-BGS',100*r20.maximum_regret)]
fig,ax=plt.subplots(figsize=(8.2,4.8)); ax.bar([x[0] for x in vals],[x[1] for x in vals]); ax.set_ylabel('Maximum holdout excess cost (%)'); ax.set_title('Fixed 20-policy high-fidelity budget'); ax.tick_params(axis='x',rotation=18); ax.grid(axis='y',alpha=.25); fig.tight_layout(); fig.savefig(MAN/'fig_v8_optimizer_comparison.png',dpi=220); plt.close(fig)

methods=['standard_GP','residual_GP','guarded_GP','DR_BGS']; labels={'standard_GP':'Standard GP','residual_GP':'Residual GP\n(no guards)','guarded_GP':'Guarded GP\n(no residual)','DR_BGS':'DR-BGS'}
fig,axes=plt.subplots(1,2,figsize=(9.0,4.2),sharey=True)
for ax,b in zip(axes,[12,20]):
    d=comp[comp.budget==b].set_index('method').loc[methods]
    ax.bar([labels[m] for m in methods],100*d.maximum_regret); ax.set_title(f'{b} high-fidelity policies'); ax.tick_params(axis='x',rotation=16); ax.grid(axis='y',alpha=.25)
axes[0].set_ylabel('Maximum holdout excess cost (%)'); fig.suptitle('Ablation of residual calibration and structural guards'); fig.tight_layout(); fig.savefig(MAN/'fig_v8_component_ablation.png',dpi=220); plt.close(fig)

fig,ax=plt.subplots(figsize=(7.2,4.5)); ax.bar(['Original 36\n(180 runs)','Additional LHS 59\n(295 runs)','Additional IID 59\n(295 runs)'],[100*r20.maximum_regret,100*lhs.all_run_max_regret,100*iid.all_run_max_regret]); ax.axhline(1,linestyle='--',linewidth=1,label='1% descriptive tolerance'); ax.set_ylabel('Maximum holdout excess cost (%)'); ax.set_title('DR-BGS across development and additional scenario sets'); ax.grid(axis='y',alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(MAN/'fig_v8_additional_scenarios.png',dpi=220); plt.close(fig)
print(json.dumps(key,indent=2))
