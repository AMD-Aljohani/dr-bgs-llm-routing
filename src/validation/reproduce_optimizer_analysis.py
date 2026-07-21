from pathlib import Path
import numpy as np, pandas as pd, math, os, json
from scipy.spatial.distance import cdist
from scipy.linalg import solve_triangular


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

SURF=pd.read_csv(DATA_SYNTHETIC / 'policy_surfaces.csv')
EPS=1e-12

def coords(df):
    K=df.alpha_on.max()/0.95
    return np.column_stack([df.alpha_on/K,df.alpha_off/K])

def maximin_fill(X, selected, n, seed):
    rng=np.random.default_rng(seed)
    selected=list(dict.fromkeys(selected))
    if not selected: selected=[int(rng.integers(len(X)))]
    chosen=set(selected)
    while len(selected)<n:
        rem=np.array([i for i in range(len(X)) if i not in chosen],int)
        d=cdist(X[rem],X[selected]).min(axis=1)
        ties=rem[np.flatnonzero(np.isclose(d,d.max()))]
        nxt=int(rng.choice(ties)); selected.append(nxt); chosen.add(nxt)
    return selected

def structural_anchors(X,diff):
    targets=[(.05,.05),(.95,.05),(.95,.95),(.5,.05),(.5,.5)]
    a=[int(np.argmin(np.linalg.norm(X-np.array(t),axis=1))) for t in targets]
    a+=list(map(int,np.argsort(diff)[:3]))
    return a

def matern52(X1,X2):
    l=np.array([.2,.2])
    D=(X1[:,None,:]-X2[None,:,:])/l
    r=np.sqrt(np.sum(D*D,axis=2)); sr=np.sqrt(5)*r
    return (1+sr+5*r*r/3)*np.exp(-sr)

def gp_predict(Xtr,ytr,alpha,Xte):
    K=matern52(Xtr,Xtr)
    K.flat[::len(K)+1]+=alpha
    try: L=np.linalg.cholesky(K)
    except np.linalg.LinAlgError:
        K.flat[::len(K)+1]+=1e-10; L=np.linalg.cholesky(K)
    # use numpy solve; very small matrices
    a=np.linalg.solve(L.T,np.linalg.solve(L,ytr))
    Ks=matern52(Xtr,Xte)
    mu=Ks.T@a
    v=np.linalg.solve(L,Ks)
    var=np.maximum(1-np.sum(v*v,axis=0),0)
    return mu,np.sqrt(var)

def select_policy(X,diff,y,se,budget,seed,residual,guards):
    initial=structural_anchors(X,diff) if guards else []
    seen=maximin_fill(X,initial,min(max(8,len(set(initial))),budget),seed)
    chosen=set(seen)
    while len(seen)<budget:
        ids=np.asarray(seen,int)
        if residual:
            A=np.column_stack([np.ones(len(ids)),diff[ids]])
            coef=np.linalg.lstsq(A,y[ids],rcond=None)[0]
            trend=coef[0]+coef[1]*diff
            target=y[ids]-trend[ids]
        else:
            trend=np.full(len(X),y[ids].mean()); target=y[ids]-y[ids].mean()
        scale=max(float(target.std()),1e-6)
        noise=np.maximum(se[ids]/scale,1e-6)**2+1e-6
        rem=np.array([i for i in range(len(X)) if i not in chosen],int)
        mu,sd=gp_predict(X[ids],target/scale,noise,X[rem])
        beta=2+.25*math.log1p(len(seen))
        acq=trend[rem]+scale*mu-beta*scale*sd
        nxt=int(rem[np.argmin(acq)]); seen.append(nxt); chosen.add(nxt)
    return int(min(seen,key=lambda i:y[i])), seen

variants=[('standard_GP',False,False),('guarded_GP',False,True),('residual_GP',True,False),('DR_BGS',True,True)]
rows=[]
for sid,df0 in SURF.groupby('scenario_id',sort=True):
    df=df0.sort_values('policy_idx').reset_index(drop=True)
    X=coords(df); y=df.train_objective.to_numpy(float); h=df.holdout_objective.to_numpy(float)
    diff=df.diffusion_objective.to_numpy(float); se=df.train_objective_ci95_hw.to_numpy(float)/2.093
    ref_idx=int(np.argmin(y)); ref=float(h[ref_idx])
    for seed in range(5):
        for name,residual,guards in variants:
            idx,seen=select_policy(X,diff,y,se,20,20260717+seed,residual,guards)
            regret=max(0.,(float(h[idx])-ref)/max(abs(ref),EPS))
            rows.append({'scenario_id':sid,'seed':seed,'method':name,'selected_idx':idx,'regret':regret,'exact':int(idx==ref_idx),'selected_set':';'.join(map(str,seen))})
raw=pd.DataFrame(rows)
raw.to_csv(str(RESULTS / 'optimizer_reanalysis_runs.csv'),index=False)
summary=raw.groupby('method').agg(median_regret=('regret','median'),p90_regret=('regret',lambda x:x.quantile(.9)),maximum_regret=('regret','max'),runs_within_1pct=('regret',lambda x:(x<=.01).mean()),runs_within_5pct=('regret',lambda x:(x<=.05).mean()),exact=('exact','mean')).reset_index()
summary.to_csv(str(RESULTS / 'optimizer_reanalysis_summary.csv'),index=False)
print(summary.to_string(index=False))
