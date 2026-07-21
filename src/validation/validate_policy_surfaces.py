import numpy as np, pandas as pd, json
from scipy.stats import spearmanr, kendalltau, gamma
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

surf=pd.read_csv(DATA_SYNTHETIC / 'policy_surfaces.csv')
sc=pd.read_csv(DATA_SYNTHETIC / 'scenario_definitions.csv')

# Policy-surface rank/calibration metrics.
rank_rows=[]
for sid,g0 in surf.groupby('scenario_id',sort=True):
    g=g0.sort_values('policy_idx').reset_index(drop=True)
    d=g.diffusion_objective.to_numpy(float); tr=g.train_objective.to_numpy(float); ho=g.holdout_objective.to_numpy(float)
    d_idx=int(np.argmin(d)); tr_idx=int(np.argmin(tr)); ref=ho[tr_idx]
    row={'scenario_id':sid,'group':g.group.iloc[0],
         'spearman_diff_train':float(spearmanr(d,tr).statistic),
         'spearman_diff_holdout':float(spearmanr(d,ho).statistic),
         'kendall_diff_train':float(kendalltau(d,tr).statistic),
         'kendall_diff_holdout':float(kendalltau(d,ho).statistic),
         'diffusion_best_idx':d_idx,'exhaustive_train_idx':tr_idx,
         'diffusion_best_exact_training':int(d_idx==tr_idx),
         'diffusion_best_holdout_excess':float(max(0,(ho[d_idx]-ref)/max(abs(ref),1e-12))),
         'median_abs_relative_objective_error':float(np.median(np.abs(d-ho)/np.maximum(np.abs(ho),1e-12)))}
    for k in [5,10,20]:
        sd=set(np.argsort(d)[:k]); st=set(np.argsort(tr)[:k]); sh=set(np.argsort(ho)[:k])
        row[f'top{k}_overlap_train']=len(sd&st)/k
        row[f'top{k}_overlap_holdout']=len(sd&sh)/k
        row[f'exhaustive_train_in_diffusion_top{k}']=int(tr_idx in sd)
    rank_rows.append(row)
rank=pd.DataFrame(rank_rows)
rank.to_csv(RESULTS / 'policy_surface_validation.csv',index=False)

# Analytical jump moment and boundary-rejection indicators.
ind=[]
for r in sc.itertuples(index=False):
    # gamma raw moments from mean and CV
    def m2(m,c): return m*m*(1+c*c)
    def m3(m,c): return m**3*(1+c*c)*(1+2*c*c)
    M2=r.lambda_H*m2(r.mean_H,r.cv_H)+r.lambda_L*m2(r.mean_L,r.cv_L)
    M3=r.lambda_H*m3(r.mean_H,r.cv_H)+r.lambda_L*m3(r.mean_L,r.cv_L)
    third=M3/(3*r.K*M2)
    vals={'scenario_id':r.scenario_id,'K':r.K,'rho':r.rho,'beta':r.beta,'jump_cv':r.jump_cv,
          'mean_jump_fraction':r.mean_jump_fraction,'M2_arrival_weighted':M2,'M3_arrival_weighted':M3,
          'third_order_indicator':third}
    for frac in [.05,.10,.25]:
        for cls,m,c in [('H',r.mean_H,r.cv_H),('L',r.mean_L,r.cv_L)]:
            shape=1/(c*c); scale=m*c*c
            vals[f'tail_{cls}_{int(frac*100)}pct']=float(gamma.sf(frac*r.K,a=shape,scale=scale))
    ind.append(vals)
ind=pd.DataFrame(ind)
ind.to_csv(RESULTS / 'jump_error_indicators.csv',index=False)
merged=rank.merge(ind,on='scenario_id').merge(sc[['scenario_id','arrival_scv','tau','qH','cloud_cost_multiplier','deactivation_mean']],on='scenario_id')
merged.to_csv(RESULTS / 'validation_by_scenario.csv',index=False)

# Correlation of model-error indicators with ranking degradation.
outcomes={'rank_degradation':1-merged.spearman_diff_holdout,'top20_degradation':1-merged.top20_overlap_holdout,'diffusion_best_excess':merged.diffusion_best_holdout_excess}
predictors=['third_order_indicator','jump_cv','mean_jump_fraction','tail_H_5pct','tail_L_5pct','tail_H_10pct','tail_L_10pct','tail_H_25pct','tail_L_25pct','beta','arrival_scv','tau']
corr=[]
for p in predictors:
    for oname,y in outcomes.items():
        x=merged[p]
        corr.append({'predictor':p,'outcome':oname,'spearman':float(spearmanr(x,y).statistic),'pearson':float(np.corrcoef(x,y)[0,1])})
corr=pd.DataFrame(corr)
corr.to_csv(RESULTS / 'indicator_correlations.csv',index=False)

# Aggregated summaries with bootstrap CIs over scenarios.
rng=np.random.default_rng(20260720)
def boot_ci(a,stat=np.median,n=10000):
    a=np.asarray(a,float); vals=np.empty(n)
    for i in range(n): vals[i]=stat(rng.choice(a,size=len(a),replace=True))
    return [float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]
summary={
 'n_scenarios':len(rank),
 'policy_surface':{
   'median_spearman_holdout':float(rank.spearman_diff_holdout.median()),
   'median_spearman_holdout_ci':boot_ci(rank.spearman_diff_holdout),
   'p10_spearman_holdout':float(rank.spearman_diff_holdout.quantile(.1)),
   'median_kendall_holdout':float(rank.kendall_diff_holdout.median()),
   'median_top20_overlap_holdout':float(rank.top20_overlap_holdout.median()),
   'fraction_exhaustive_training_optimum_in_diffusion_top20':float(rank.exhaustive_train_in_diffusion_top20.mean()),
   'diffusion_best_exact_training_fraction':float(rank.diffusion_best_exact_training.mean()),
   'median_diffusion_best_holdout_excess':float(rank.diffusion_best_holdout_excess.median()),
   'p90_diffusion_best_holdout_excess':float(rank.diffusion_best_holdout_excess.quantile(.9)),
   'max_diffusion_best_holdout_excess':float(rank.diffusion_best_holdout_excess.max()),
   'median_surface_absolute_relative_objective_error':float(rank.median_abs_relative_objective_error.median()),
   'p90_surface_absolute_relative_objective_error':float(rank.median_abs_relative_objective_error.quantile(.9))
 },
 'analytical_indicators':{
   'median_third_order_indicator':float(ind.third_order_indicator.median()),
   'max_third_order_indicator':float(ind.third_order_indicator.max()),
   'median_tail_H_5pct':float(ind.tail_H_5pct.median()),
   'median_tail_L_5pct':float(ind.tail_L_5pct.median()),
   'median_tail_H_10pct':float(ind.tail_H_10pct.median()),
   'median_tail_L_10pct':float(ind.tail_L_10pct.median()),
   'median_tail_H_25pct':float(ind.tail_H_25pct.median()),
   'median_tail_L_25pct':float(ind.tail_L_25pct.median())
 },
 'indicator_correlations':corr.sort_values('spearman',ascending=False).head(12).to_dict(orient='records')
}
(RESULTS / 'surface_validation_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
