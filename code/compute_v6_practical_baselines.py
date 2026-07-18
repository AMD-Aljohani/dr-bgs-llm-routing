from pathlib import Path
import sys, numpy as np, pandas as pd
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as h

summ=pd.read_csv(BASE/'results'/'hysteresis_summary_all.csv')
surf=pd.read_csv(BASE/'results'/'hysteresis_policy_surfaces_all.csv')
rows=[]
for group, scenarios, seed_offset in [
    ('development', h.existing_development_scenarios(), 0),
    ('fresh', h.fresh_validation_scenarios(), 500_000_000),
]:
    for idx,s in enumerate(scenarios,1):
        r=summ[summ.scenario_id==s.scenario_id].iloc[0]
        hold_streams=[core.generate_stream(s,h.SEED+seed_offset+21_000_000+100_000*idx+139*rep,h.HOLDOUT_HORIZON)
                      for rep in range(h.HOLDOUT_REPS)]
        vals=[]
        for rep,st in enumerate(hold_streams):
            z=core.sim_threshold(s,st,h.HOLDOUT_HORIZON,h.HOLDOUT_BURN,2.0*s.K,2.0*s.K,
                                 h.SEED+seed_offset+1_700_000*idx+1009*rep)
            vals.append(z['objective'])
        local=float(np.mean(vals))
        g=surf[surf.scenario_id==s.scenario_id]
        def obj(onfrac, offfrac):
            q=g[np.isclose(g.alpha_on,onfrac*s.K)&np.isclose(g.alpha_off,offfrac*s.K)]
            assert len(q)==1,(s.scenario_id,onfrac,offfrac,len(q))
            return float(q.holdout_objective.iloc[0])
        diff=float(g[g.policy_idx==int(r.diffusion_best_idx)].holdout_objective.iloc[0])
        row={
            'scenario_id':s.scenario_id,'group':group,
            'migr_h':float(r.adaptive_holdout_objective),
            'local_only':local,
            'static_half':obj(.5,.5),
            'fixed_deadband_05_04':obj(.5,.4),
            'diffusion_only':diff,
            'best_single_training':float(r.single_holdout_objective),
        }
        for k in ['local_only','static_half','fixed_deadband_05_04','diffusion_only','best_single_training']:
            row['improvement_vs_'+k]=(row[k]-row['migr_h'])/abs(row[k])
        rows.append(row)
        print(group,idx,s.scenario_id,local)

df=pd.DataFrame(rows)
out=BASE/'results'/'v6_practical_baseline_comparison.csv'
df.to_csv(out,index=False)
agg=[]
for k in ['local_only','static_half','fixed_deadband_05_04','diffusion_only','best_single_training']:
    x=df['improvement_vs_'+k]
    agg.append({'baseline':k,'median_improvement':x.median(),'p10':x.quantile(.1),'p90':x.quantile(.9),'better_fraction':(x>0).mean(),'scenarios':len(x)})
a=pd.DataFrame(agg)
a.to_csv(BASE/'results'/'v6_practical_baseline_summary.csv',index=False)
print('\nSUMMARY')
print(a.to_string(index=False))
