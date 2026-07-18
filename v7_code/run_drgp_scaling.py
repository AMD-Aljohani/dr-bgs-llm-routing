#!/usr/bin/env python3
from __future__ import annotations
import argparse, math, sys, time
from dataclasses import fields
from pathlib import Path
import numpy as np, pandas as pd
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, ConstantKernel
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'code'))
import run_smpt_campaign as core
Q=[19,31,51]; TRAIN_REPS=6; HOLD_REPS=10; TH=600.; TB=150.; HH=800.; HB=200.; KPOL=20; SEED=20261201; EPS=1e-12

def scenario_from_row(r):
 names={f.name for f in fields(core.Scenario)}; return core.Scenario(**{k:getattr(r,k) for k in names})
def grid(s,q):
 lv=np.linspace(.05*s.K,.95*s.K,q); pairs=[]
 for i,on in enumerate(lv):
  for off in lv[:i+1]: pairs.append((float(on),float(off)))
 return lv,pairs

def sim(s,pairs,streams,h,b,seed):
 a=np.empty((len(pairs),len(streams)))
 for i,(on,off) in enumerate(pairs):
  for r,st in enumerate(streams): a[i,r]=core.sim_threshold(s,st,h,b,on,off,seed+1009*r)['objective']
 return a

def maximin_fill(X,sel,n):
 sel=list(dict.fromkeys(sel))
 while len(sel)<n:
  rem=np.array([i for i in range(len(X)) if i not in set(sel)],int); d=cdist(X[rem],X[sel]).min(axis=1); sel.append(int(rem[np.argmax(d)]))
 return sel

def drgp(X,diff,y,se,k=20):
 targets=[(.05,.05),(.95,.05),(.95,.95),(.5,.05),(.5,.5)]
 anchors=[int(np.argmin(np.linalg.norm(X-np.array(t),axis=1))) for t in targets]+list(map(int,np.argsort(diff)[:3]))
 seen=maximin_fill(X,anchors,min(max(8,len(set(anchors))),k)); kernel=ConstantKernel(1.,'fixed')*Matern([.2,.2],nu=2.5,length_scale_bounds='fixed')
 while len(seen)<k:
  ids=np.array(seen); A=np.column_stack([np.ones(len(ids)),diff[ids]]); coef=np.linalg.lstsq(A,y[ids],rcond=None)[0]; trend=coef[0]+coef[1]*diff
  resid=y[ids]-trend[ids]; scale=max(resid.std(),1e-6); noise=np.maximum(se[ids]/scale,1e-6)**2+1e-6
  gp=GaussianProcessRegressor(kernel=kernel,alpha=noise,optimizer=None,normalize_y=False); gp.fit(X[ids],resid/scale)
  rem=np.array([i for i in range(len(X)) if i not in set(seen)]); mu,sd=gp.predict(X[rem],return_std=True); beta=2+.25*math.log1p(len(seen)); seen.append(int(rem[np.argmin(trend[rem]+scale*mu-beta*scale*sd)]))
 return min(seen,key=lambda i:y[i])

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--scenario',required=True); ap.add_argument('--output',required=True); a=ap.parse_args(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
 summ=pd.read_csv(ROOT/'results'/'hysteresis_summary_all.csv'); r=summ[summ.scenario_id==a.scenario].iloc[0]; s=scenario_from_row(r)
 st=core.generate_stream(s,1,5.); core.sim_threshold(s,st,5.,1.,.5*s.K,.4*s.K,1)
 rows=[]
 for q in Q:
  t=time.time(); lv,pairs=grid(s,q); K=s.K; X=np.array([[on/K,off/K] for on,off in pairs])
  diff=np.array([core.diffusion_metrics(s,on,off,N=81)['objective'] for on,off in pairs])
  trs=[core.generate_stream(s,SEED+100000*q+137*i,TH) for i in range(TRAIN_REPS)]; hos=[core.generate_stream(s,SEED+900000+100000*q+139*i,HH) for i in range(HOLD_REPS)]
  tr=sim(s,pairs,trs,TH,TB,SEED+q*1000); ho=sim(s,pairs,hos,HH,HB,SEED+q*2000)
  y=tr.mean(1); se=tr.std(1,ddof=1)/math.sqrt(TRAIN_REPS); idx=drgp(X,diff,y,se,KPOL); exh=int(np.argmin(y)); ref=ho.mean(1)[exh]; val=ho.mean(1)[idx]; M=len(pairs)
  rows.append({'scenario_id':s.scenario_id,'level_count':q,'policy_count':M,'evaluated_policies':KPOL,'evaluated_fraction':KPOL/M,'work_reduction':1-(KPOL*TRAIN_REPS+HOLD_REPS)/(M*TRAIN_REPS+HOLD_REPS),'selected_idx':idx,'exhaustive_idx':exh,'exact_match':int(idx==exh),'holdout_regret':max(0.,(val-ref)/max(abs(ref),EPS)),'elapsed_seconds':time.time()-t})
  print(rows[-1],flush=True)
 pd.DataFrame(rows).to_csv(out/f'{s.scenario_id}_drgp_scaling.csv',index=False)
if __name__=='__main__':main()
