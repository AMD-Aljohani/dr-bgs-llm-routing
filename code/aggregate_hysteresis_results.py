#!/usr/bin/env python3
from pathlib import Path
import json, shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'results'; FIG=ROOT/'figures'; FIG.mkdir(exist_ok=True)
rows=[]; surfaces=[]
for group in ['development','fresh']:
    for f in sorted((RES/group).rglob('*_summary.json')):
        r=json.loads(f.read_text()); r['group']=group
        surf_path=f.with_name(f.name.replace('_summary.json','_policy_surface.csv'))
        surf=pd.read_csv(surf_path); surf['group']=group
        all_oracle=float(surf.holdout_objective.min())
        diag=surf[np.isclose(surf.alpha_on,surf.alpha_off)]
        diag_oracle=float(diag.holdout_objective.min())
        r['oracle_hysteresis_gain_vs_single']=(diag_oracle-all_oracle)/max(abs(diag_oracle),1e-12)
        r['holdout_oracle_all']=all_oracle; r['holdout_oracle_single']=diag_oracle
        r['selected_is_strict_hysteresis']=int(r['selected_alpha_on']>r['selected_alpha_off']+1e-9)
        r['exhaustive_is_strict_hysteresis']=int(r['exhaustive_alpha_on']>r['exhaustive_alpha_off']+1e-9)
        r['exact_match_exhaustive']=int(r['final_idx']==r['exhaustive_train_idx'])
        rows.append(r); surfaces.append(surf)

df=pd.DataFrame(rows).sort_values(['group','scenario_id']).reset_index(drop=True)
surf=pd.concat(surfaces,ignore_index=True)
df.to_csv(RES/'hysteresis_summary_all.csv',index=False)
surf.to_csv(RES/'hysteresis_policy_surfaces_all.csv',index=False)

summary=[]
for group in ['development','fresh','all']:
    d=df if group=='all' else df[df.group==group]
    summary.append({
        'group':group,'scenarios':len(d),
        'certificate_rate':d.certified.mean(),
        'fallback_rate':d.fallback.mean(),
        'mean_candidate_count':d.selection_candidate_count.mean(),
        'median_candidate_count':d.selection_candidate_count.median(),
        'mean_work_reduction':d.work_reduction.mean(),
        'median_work_reduction':d.work_reduction.median(),
        'minimum_work_reduction':d.work_reduction.min(),
        'median_regret':d.holdout_regret_vs_exhaustive.median(),
        'p90_regret':d.holdout_regret_vs_exhaustive.quantile(.9),
        'maximum_regret':d.holdout_regret_vs_exhaustive.max(),
        'within_1pct_fraction':(d.holdout_regret_vs_exhaustive<=.01).mean(),
        'within_5pct_fraction':(d.holdout_regret_vs_exhaustive<=.05).mean(),
        'exact_match_fraction':d.exact_match_exhaustive.mean(),
        'strict_hysteresis_selected_fraction':d.selected_is_strict_hysteresis.mean(),
        'oracle_hysteresis_positive_fraction':(d.oracle_hysteresis_gain_vs_single>1e-12).mean(),
        'oracle_hysteresis_gain_median':d.oracle_hysteresis_gain_vs_single.median(),
        'oracle_hysteresis_gain_p90':d.oracle_hysteresis_gain_vs_single.quantile(.9),
        'oracle_hysteresis_gain_max':d.oracle_hysteresis_gain_vs_single.max(),
        'median_distinct_weight_optima':d.distinct_weight_optima.median(),
        'max_distinct_weight_optima':d.distinct_weight_optima.max(),
        'median_robust_max_additive_regret':d.robust_max_additive_regret.median(),
    })
summary=pd.DataFrame(summary)
summary.to_csv(RES/'hysteresis_aggregate_summary.csv',index=False)
(RES/'hysteresis_aggregate_summary.json').write_text(json.dumps(summary.to_dict(orient='records'),indent=2))

# Main figures.
# 1) Work reduction and regret scatter.
fig,ax=plt.subplots(figsize=(7.2,4.8))
for group,marker in [('development','o'),('fresh','s')]:
    d=df[df.group==group]
    ax.scatter(100*d.work_reduction,100*d.holdout_regret_vs_exhaustive,marker=marker,label=group.capitalize())
ax.axhline(5,linestyle='--',linewidth=1)
ax.set_xlabel('Simulation work reduction relative to exhaustive search (%)')
ax.set_ylabel('Holdout excess cost (%)')
ax.set_title('Multi-fidelity search efficiency and decision loss')
ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
fig.savefig(FIG/'fig_v5_work_vs_regret.png',dpi=220); plt.close(fig)

# 2) Regret ECDF.
fig,ax=plt.subplots(figsize=(6.8,4.6))
for group,style in [('development','-'),('fresh','--')]:
    vals=np.sort(100*df[df.group==group].holdout_regret_vs_exhaustive.to_numpy())
    y=np.arange(1,len(vals)+1)/len(vals)
    ax.step(vals,y,where='post',linestyle=style,label=group.capitalize())
ax.set_xlabel('Holdout excess cost relative to exhaustive search (%)')
ax.set_ylabel('Empirical cumulative fraction')
ax.set_title('Global empirical validation over the 190-policy space')
ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
fig.savefig(FIG/'fig_v5_regret_ecdf.png',dpi=220); plt.close(fig)

# 3) Hysteresis oracle gain distribution.
fig,ax=plt.subplots(figsize=(7.0,4.5))
vals=np.sort(100*df.oracle_hysteresis_gain_vs_single.to_numpy())
ax.bar(np.arange(len(vals)),vals)
ax.axhline(0,linewidth=1)
ax.set_xlabel('Scenario ordered by gain')
ax.set_ylabel('Oracle gain over best single threshold (%)')
ax.set_title('Incremental value of the two-threshold policy space')
ax.grid(axis='y',alpha=.25); fig.tight_layout()
fig.savefig(FIG/'fig_v5_hysteresis_gain.png',dpi=220); plt.close(fig)

# 4) Weight sensitivity.
fig,ax=plt.subplots(figsize=(6.8,4.5))
counts=df.distinct_weight_optima.value_counts().sort_index()
ax.bar(counts.index.astype(str),counts.values)
ax.set_xlabel('Distinct optimal policies across 29 weight profiles')
ax.set_ylabel('Scenarios')
ax.set_title('Objective-weight sensitivity')
ax.grid(axis='y',alpha=.25); fig.tight_layout()
fig.savefig(FIG/'fig_v5_weight_sensitivity.png',dpi=220); plt.close(fig)

# 5) Example 2D holdout surface (F04, largest oracle hysteresis gain).
example=df.loc[df.oracle_hysteresis_gain_vs_single.idxmax(),'scenario_id']
e=surf[surf.scenario_id==example].copy()
levels=np.sort(e.alpha_on.unique()); mat=np.full((len(levels),len(levels)),np.nan)
for _,r in e.iterrows():
    i=np.where(np.isclose(levels,r.alpha_on))[0][0]
    j=np.where(np.isclose(levels,r.alpha_off))[0][0]
    mat[j,i]=r.holdout_objective
fig,ax=plt.subplots(figsize=(6.3,5.2))
im=ax.imshow(mat,origin='lower',aspect='auto',extent=[.05,.95,.05,.95])
ax.plot([.05,.95],[.05,.95],linestyle='--',linewidth=1,label='Single-threshold diagonal')
best=e.loc[e.holdout_objective.idxmin()]
diag=e[np.isclose(e.alpha_on,e.alpha_off)]; bestd=diag.loc[diag.holdout_objective.idxmin()]
K=float(df.loc[df.scenario_id==example,'K'].iloc[0])
ax.scatter(best.alpha_on/K,best.alpha_off/K,marker='*',s=110,label='Best hysteretic pair')
ax.scatter(bestd.alpha_on/K,bestd.alpha_off/K,marker='x',s=70,label='Best single threshold')
ax.set_xlabel(r'Activation threshold $\alpha_{\rm on}/K$')
ax.set_ylabel(r'Deactivation threshold $\alpha_{\rm off}/K$')
ax.set_title(f'Jump-model objective surface: {example}')
fig.colorbar(im,ax=ax,label='Holdout objective')
ax.legend(loc='best'); fig.tight_layout()
fig.savefig(FIG/'fig_v5_hysteresis_surface.png',dpi=220); plt.close(fig)

# 6) Certificate and fallback counts.
fig,ax=plt.subplots(figsize=(6.4,4.3))
ct=df.groupby(['group','certified']).size().unstack(fill_value=0)
ct=ct.rename(columns={0:'Explored-set fallback',1:'Certificate achieved'})
ct.plot(kind='bar',ax=ax)
ax.set_xlabel('Scenario set'); ax.set_ylabel('Scenarios')
ax.set_title('Nominal explored-set certification outcomes')
ax.tick_params(axis='x',rotation=0); ax.grid(axis='y',alpha=.25)
fig.tight_layout(); fig.savefig(FIG/'fig_v5_certificate_rate.png',dpi=220); plt.close(fig)

# Machine-readable key results.
key={
    'title':'MIGR-H hysteresis search results',
    'policy_space':190,
    'strict_hysteresis_pairs':171,
    'single_threshold_diagonal':19,
    'development_scenarios':24,
    'fresh_scenarios':12,
    'aggregate':summary.to_dict(orient='records'),
    'worst_scenarios':df.nlargest(5,'holdout_regret_vs_exhaustive')[['scenario_id','group','holdout_regret_vs_exhaustive','work_reduction','certified']].to_dict(orient='records'),
    'largest_hysteresis_gains':df.nlargest(5,'oracle_hysteresis_gain_vs_single')[['scenario_id','group','oracle_hysteresis_gain_vs_single']].to_dict(orient='records'),
}
(RES/'V5_KEY_RESULTS.json').write_text(json.dumps(key,indent=2))
print(summary.to_string(index=False))
