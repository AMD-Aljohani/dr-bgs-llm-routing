#!/usr/bin/env python3
"""Budget-matched breadth-first two-stage ranking-and-selection comparator.

Total training budget per scenario/seed is 400 jump simulations:
  190 policies x 2 CRN replications + 10 shortlisted policies x 2 more.
The selected policy is evaluated on the archived independent holdout surface.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import run_smpt_campaign as core
import run_hysteresis_c_migr as migr

SURF=pd.read_csv(ROOT/'results'/'hysteresis_policy_surfaces_all.csv')
SUM=pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv')
BASE_SEEDS=[20261001,20261002,20261003,20261004,20261005]
H=900.; BURN=225.

def all_scenarios():
    dev=migr.existing_development_scenarios()
    fresh=migr.fresh_validation_scenarios()
    d={s.scenario_id:s for s in dev+fresh}
    return [d[sid] for sid in SUM.scenario_id]

def eval_policy(s,pair,streams,seed_base):
    vals=[]
    for r,st in enumerate(streams):
        vals.append(core.sim_threshold(s,st,H,BURN,pair[0],pair[1],seed_base+1009*r)['objective'])
    return vals

def run_one(s,scenario_index,seed):
    _,pairs,_=migr.policy_grid(s)
    streams=[core.generate_stream(s,seed+100000*scenario_index+137*r,H) for r in range(4)]
    y2=np.empty(len(pairs))
    first={}
    for i,p in enumerate(pairs):
        v=eval_policy(s,p,streams[:2],seed+700000*scenario_index)
        first[i]=v; y2[i]=np.mean(v)
    shortlist=np.argsort(y2)[:10]
    y4={}
    for i in shortlist:
        extra=eval_policy(s,pairs[int(i)],streams[2:],seed+1700000*scenario_index)
        y4[int(i)]=float(np.mean(first[int(i)]+extra))
    selected=min(y4,key=y4.get)
    df=SURF[SURF.scenario_id==s.scenario_id].sort_values('policy_idx').reset_index(drop=True)
    ref_idx=int(SUM.loc[SUM.scenario_id==s.scenario_id,'exhaustive_train_idx'].iloc[0])
    ref=float(df.holdout_objective.iloc[ref_idx]); val=float(df.holdout_objective.iloc[selected])
    regret=max(0.,(val-ref)/max(abs(ref),1e-12))
    return {'scenario_id':s.scenario_id,'seed':seed,'selected_idx':selected,
            'reference_idx':ref_idx,'regret':regret,'exact':int(selected==ref_idx),
            'training_replications':400,'shortlist_size':10}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--count',type=int);ap.add_argument('--output',required=True);a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    ss=all_scenarios(); end=len(ss) if a.count is None else a.start+a.count
    # JIT warmup
    s=ss[a.start]; st=core.generate_stream(s,1,5.); core.sim_threshold(s,st,5.,1.,.5*s.K,.4*s.K,1)
    rows=[]
    for gi,s in enumerate(ss[a.start:end],a.start):
        for seed in BASE_SEEDS: rows.append(run_one(s,gi+1,seed))
        print(f'[{gi+1:02d}/36] {s.scenario_id}',flush=True)
    pd.DataFrame(rows).to_csv(out/f'bf_rs_part_{a.start:02d}.csv',index=False)
if __name__=='__main__':main()
