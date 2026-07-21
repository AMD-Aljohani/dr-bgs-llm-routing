import numpy as np, pandas as pd, math, json
from scipy.spatial.distance import cdist
from scipy.stats import rankdata, kendalltau
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

SURF=pd.read_csv(DATA_SYNTHETIC / 'policy_surfaces.csv'); EPS=1e-12

def coords(df):
 K=df.alpha_on.max()/.95; return np.column_stack([df.alpha_on/K,df.alpha_off/K])
def maximin_fill(X,sel,n,seed):
 rng=np.random.default_rng(seed); sel=list(dict.fromkeys(sel)); chosen=set(sel)
 if not sel: sel=[int(rng.integers(len(X)))]; chosen=set(sel)
 while len(sel)<n:
  rem=np.array([i for i in range(len(X)) if i not in chosen]); d=cdist(X[rem],X[sel]).min(axis=1); ties=rem[np.flatnonzero(np.isclose(d,d.max()))]; nxt=int(rng.choice(ties)); sel.append(nxt); chosen.add(nxt)
 return sel
def anchors(X,d):
 targets=[(.05,.05),(.95,.05),(.95,.95),(.5,.05),(.5,.5)]
 return [int(np.argmin(np.linalg.norm(X-np.array(t),axis=1))) for t in targets]+list(map(int,np.argsort(d)[:3]))
def kern(A,B):
 D=(A[:,None,:]-B[None,:,:])/.2; r=np.sqrt((D*D).sum(2)); s=np.sqrt(5)*r; return (1+s+5*r*r/3)*np.exp(-s)
def pred(Xt,yt,alpha,Xq):
 K=kern(Xt,Xt); K.flat[::len(K)+1]+=alpha
 try:L=np.linalg.cholesky(K)
 except np.linalg.LinAlgError: K.flat[::len(K)+1]+=1e-10; L=np.linalg.cholesky(K)
 a=np.linalg.solve(L.T,np.linalg.solve(L,yt)); Ks=kern(Xt,Xq); mu=Ks.T@a; v=np.linalg.solve(L,Ks); sd=np.sqrt(np.maximum(1-(v*v).sum(0),0)); return mu,sd
def select(X,d,y,se,seed):
 seen=maximin_fill(X,anchors(X,d),8,seed); chosen=set(seen)
 while len(seen)<20:
  ids=np.asarray(seen); A=np.c_[np.ones(len(ids)),d[ids]]; coef=np.linalg.lstsq(A,y[ids],rcond=None)[0]; trend=coef[0]+coef[1]*d; target=y[ids]-trend[ids]; scale=max(float(target.std()),1e-6); noise=np.maximum(se[ids]/scale,1e-6)**2+1e-6
  rem=np.array([i for i in range(len(X)) if i not in chosen]); mu,sd=pred(X[ids],target/scale,noise,X[rem]); beta=2+.25*math.log1p(len(seen)); nxt=int(rem[np.argmin(trend[rem]+scale*mu-beta*scale*sd)]); seen.append(nxt); chosen.add(nxt)
 return int(min(seen,key=lambda i:y[i]))

def transforms(d,X):
 centered=(d-d.min()); scl=max(np.quantile(centered,.75),1e-12); ranks=(rankdata(d,method='average')-1)/(len(d)-1)
 smooth=np.sin(np.pi*X[:,0])*np.cos(np.pi*X[:,1]); sd=max(d.std(),1e-12)
 return {
  'original':d,
  'positive_affine':3.7*d+2.1,
  'log_monotone':np.log1p(centered/scl),
  'rank_fraction':ranks,
  'squared_rank':ranks**2,
  'smooth_10pct_sd':d+0.10*sd*smooth,
  'smooth_20pct_sd':d+0.20*sd*smooth,
  'smooth_40pct_sd':d+0.40*sd*smooth,
 }
rows=[]
for sid,g0 in SURF.groupby('scenario_id',sort=True):
 g=g0.sort_values('policy_idx').reset_index(drop=True); X=coords(g); d0=g.diffusion_objective.to_numpy(float); y=g.train_objective.to_numpy(float); h=g.holdout_objective.to_numpy(float); se=g.train_objective_ci95_hw.to_numpy(float)/2.093; refidx=int(np.argmin(y)); ref=float(h[refidx]); tv=transforms(d0,X)
 base_sel={}
 for seed in range(5):
  base_sel[seed]=select(X,tv['original'],y,se,20260717+seed)
 for name,d in tv.items():
  kt=float(kendalltau(d0,d).statistic)
  for seed in range(5):
   idx=select(X,d,y,se,20260717+seed); regret=max(0,(h[idx]-ref)/max(abs(ref),EPS)); rows.append({'scenario_id':sid,'variant':name,'seed':seed,'kendall_with_original_low_fidelity':kt,'selected_idx':idx,'regret':regret,'within_1pct':int(regret<=.01),'within_5pct':int(regret<=.05),'exact_training':int(idx==refidx),'same_selection_as_original':int(idx==base_sel[seed])})
raw=pd.DataFrame(rows); raw.to_csv(RESULTS / 'model_form_stress_runs.csv',index=False)
s=raw.groupby('variant').agg(median_kendall=('kendall_with_original_low_fidelity','median'),median_regret=('regret','median'),p90_regret=('regret',lambda x:x.quantile(.9)),maximum_regret=('regret','max'),within_1pct=('within_1pct','mean'),within_5pct=('within_5pct','mean'),exact_training=('exact_training','mean'),same_selection_as_original=('same_selection_as_original','mean')).reset_index()
s.to_csv(RESULTS / 'model_form_stress_summary.csv',index=False); (RESULTS / 'model_form_stress_summary.json').write_text(json.dumps(s.to_dict(orient='records'),indent=2)); print(s.to_string(index=False))
