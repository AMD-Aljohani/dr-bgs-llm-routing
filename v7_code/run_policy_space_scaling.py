#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys, time
from dataclasses import fields
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import run_smpt_campaign as core

TRAIN_REPS=6; HOLD_REPS=10
TRAIN_H=600.; TRAIN_B=150.; HOLD_H=800.; HOLD_B=200.
BASE_SEED=20261101; EPS=1e-12
SCENARIOS=['F01','F31','R03','R24','V01','V12']
LEVELS_LIST=[19,31,51]

def scenario_from_row(r):
    names={f.name for f in fields(core.Scenario)}
    return core.Scenario(**{k:getattr(r,k) for k in names})

def grid(s,q):
    lv=np.linspace(.05*s.K,.95*s.K,q); pairs=[]; ij=[]
    for i,on in enumerate(lv):
        for j,off in enumerate(lv[:i+1]): pairs.append((float(on),float(off))); ij.append((i,j))
    return lv,pairs,ij

def simulate(s,pairs,streams,h,b,seed):
    a=np.empty((len(pairs),len(streams)))
    for i,(on,off) in enumerate(pairs):
        for r,st in enumerate(streams):
            a[i,r]=core.sim_threshold(s,st,h,b,on,off,seed+1009*r)['objective']
    return a

def candidates(diff,train,ij,q):
    index={p:i for i,p in enumerate(ij)}; order=np.argsort(diff); cand=set()
    cand.update(map(int,order[:max(8,round(8*q/19))]))
    # Full diagonal and coarse boundaries.
    cand.update(index[(i,i)] for i in range(q))
    step=max(1,q//8)
    for i in range(0,q,step): cand.add(index[(i,0)])
    for j in range(0,q,step): cand.add(index[(q-1,j)])
    for p in [(0,0),(q-1,0),(q-1,q-1),(q//2,0),(q//2,q//2),(q-1,q//2)]: cand.add(index[p])
    rad=max(1,round(2*q/19))
    for idx in order[:3]:
        i,j=ij[int(idx)]
        for di in range(-rad,rad+1):
            for dj in range(-rad,rad+1):
                p=(i+di,j+dj)
                if p in index: cand.add(index[p])
    means={i:float(train[i,:3].mean()) for i in cand}
    cap=max(48,round(2.6*q))
    for _ in range(4):
        best=min(means,key=means.get); bi,bj=ij[best]
        new=set()
        for di in range(-rad,rad+1):
            for dj in range(-rad,rad+1):
                p=(bi+di,bj+dj)
                if p in index:new.add(index[p])
        ids=np.array(sorted(means),int); x=diff[ids]; y=np.array([means[i] for i in ids])
        A=np.column_stack([np.ones(len(ids)),x]); coef=np.linalg.lstsq(A,y,rcond=None)[0]
        pred=coef[0]+coef[1]*diff
        new.update(map(int,np.argsort(pred)[:max(7,q//3)])); new.update(map(int,order[:max(12,q//2)]))
        for i in sorted(new):
            if i not in means: means[i]=float(train[i,:3].mean())
            if len(means)>=cap:break
        if len(means)>=cap:break
    ids=sorted(means)
    return ids,int(min(ids,key=lambda i:train[i].mean()))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--scenario',required=True); ap.add_argument('--output',required=True)
    a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    summ=pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv')
    r=summ[summ.scenario_id==a.scenario].iloc[0]
    s=scenario_from_row(r)
    # warm up
    st=core.generate_stream(s,1,5.); core.sim_threshold(s,st,5.,1.,.5*s.K,.4*s.K,1)
    rows=[]
    for q in LEVELS_LIST:
        t0=time.time(); lv,pairs,ij=grid(s,q)
        diff=np.array([core.diffusion_metrics(s,on,off,N=81)['objective'] for on,off in pairs])
        train_stream=[core.generate_stream(s,BASE_SEED+100000*q+137*i,TRAIN_H) for i in range(TRAIN_REPS)]
        hold_stream=[core.generate_stream(s,BASE_SEED+900000+100000*q+139*i,HOLD_H) for i in range(HOLD_REPS)]
        tr=simulate(s,pairs,train_stream,TRAIN_H,TRAIN_B,BASE_SEED+q*1000)
        ho=simulate(s,pairs,hold_stream,HOLD_H,HOLD_B,BASE_SEED+q*2000)
        idx_exh=int(np.argmin(tr.mean(axis=1))); ids,idx=int(0),int(0)
        ids,idx=candidates(diff,tr,ij,q)
        exh=float(ho.mean(axis=1)[idx_exh]); sel=float(ho.mean(axis=1)[idx])
        M=len(pairs); work=len(ids)*TRAIN_REPS+HOLD_REPS; exwork=M*TRAIN_REPS+HOLD_REPS
        rows.append({'scenario_id':s.scenario_id,'level_count':q,'policy_count':M,'candidate_count':len(ids),'candidate_fraction':len(ids)/M,'work_reduction':1-work/exwork,'selected_idx':idx,'exhaustive_idx':idx_exh,'exact_match':int(idx==idx_exh),'holdout_regret':max(0.,(sel-exh)/max(abs(exh),EPS)),'elapsed_seconds':time.time()-t0})
        print(rows[-1],flush=True)
    pd.DataFrame(rows).to_csv(out/f'{s.scenario_id}_scaling.csv',index=False)

if __name__=='__main__':main()
