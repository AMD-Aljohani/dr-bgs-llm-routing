from pathlib import Path
import sys, pandas as pd, numpy as np
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as h
summ=pd.read_csv(BASE/'results'/'hysteresis_summary_all.csv')
surf=pd.read_csv(BASE/'results'/'hysteresis_policy_surfaces_all.csv')
scens={s.scenario_id:s for s in h.existing_development_scenarios()+h.fresh_validation_scenarios()}
rows=[]
for _,r in summ.iterrows():
    s=scens[r.scenario_id]; levels,pairs,ij=h.policy_grid(s)
    near=[]
    for idx,(on,off) in enumerate(pairs):
        z=core.diffusion_metrics(s,on,off,N=161,tau_override=0.02)
        near.append(z['objective'])
    idx_near=int(np.argmin(near))
    g=surf[surf.scenario_id==s.scenario_id].set_index('policy_idx')
    idx_aware=int(r.diffusion_best_idx)
    aware=float(g.loc[idx_aware,'holdout_objective'])
    near_hold=float(g.loc[idx_near,'holdout_objective'])
    improvement=(near_hold-aware)/abs(near_hold)
    rows.append({'scenario_id':s.scenario_id,'group':r.group,'design':r.design,'tau':s.tau,
                 'delay_aware_idx':idx_aware,'near_instant_idx':idx_near,
                 'delay_aware_alpha_on':pairs[idx_aware][0],'delay_aware_alpha_off':pairs[idx_aware][1],
                 'near_instant_alpha_on':pairs[idx_near][0],'near_instant_alpha_off':pairs[idx_near][1],
                 'delay_aware_holdout_objective':aware,'near_instant_holdout_objective':near_hold,
                 'delay_aware_improvement':improvement,
                 'same_policy':int(idx_aware==idx_near)})
    print(r.scenario_id,idx_aware,idx_near,improvement)
df=pd.DataFrame(rows)
df.to_csv(BASE/'results'/'v6_activation_delay_ablation.csv',index=False)
for name,g in [('all',df),('development',df[df.group=='development']),('fresh',df[df.group=='fresh'])]:
    x=g.delay_aware_improvement
    print(name,'median',x.median(),'p90',x.quantile(.9),'max',x.max(),'positive',(x>0).mean(),'same',(g.same_policy==1).mean())
print('\nBy tau factorial development:')
f=df[(df.design=='factorial')]
print(f.groupby('tau').delay_aware_improvement.agg(['count','median','mean','max']).to_string())
