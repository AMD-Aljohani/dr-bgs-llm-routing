import numpy as np, pandas as pd, json
from scipy.optimize import curve_fit
from scipy.stats import spearmanr, kendalltau
from sklearn.metrics import mean_squared_error, r2_score
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

datasets={
 'Qwen2.5-7B / RTX 3090 (direct telemetry)': pd.read_csv(DATA_CALIBRATION / 'qwen_rtx3090_direct_telemetry.csv').rename(columns={'decode_rate_mean_tok_s':'rate'}),
 'Mistral-7B / RTX 3090': pd.read_csv(DATA_CALIBRATION / 'mistral_rtx3090_summary.csv').rename(columns={'decode_rate_tok_s':'rate'}),
 'Qwen2.5-7B / RTX 4090': pd.read_csv(DATA_CALIBRATION / 'qwen_rtx4090_summary.csv').rename(columns={'decode_rate_tok_s':'rate'}),
 'Qwen2.5-7B / RTX 3090 (independent summary)': pd.read_csv(DATA_CALIBRATION / 'qwen_rtx3090_independent_summary.csv').rename(columns={'decode_rate_tok_s':'rate'}),
}

def exp_norm(u,b): return np.exp(-b*u)
def lin_norm(u,b): return 1-b*u
def recip_norm(u,b): return 1/(1+b*u)
def power_c(c,b): return c**(-b)

def fit_model(x,y,fn,p0=.5,bounds=(0,np.inf)):
    popt,_=curve_fit(fn,x,y,p0=[p0],bounds=bounds,maxfev=10000)
    pred=fn(x,*popt)
    rmse=np.sqrt(np.mean((y-pred)**2)); r2=1-np.sum((y-pred)**2)/np.sum((y-y.mean())**2)
    return float(popt[0]),pred,float(rmse),float(r2)

def loocv(x,y,fn,p0=.5,bounds=(0,np.inf)):
    preds=[]
    for i in range(len(x)):
        mask=np.arange(len(x))!=i
        try:
            p,_=curve_fit(fn,x[mask],y[mask],p0=[p0],bounds=bounds,maxfev=10000)
            preds.append(float(fn(np.array([x[i]]),*p)[0]))
        except Exception:
            preds.append(np.nan)
    preds=np.array(preds)
    return float(np.sqrt(np.nanmean((y-preds)**2))), preds

rows=[]; curves={}
for name,df in datasets.items():
    df=df.sort_values('concurrency').copy()
    c=df.concurrency.to_numpy(float)
    u=np.log2(c)/np.log2(c.max())
    rate=df.rate.to_numpy(float); yn=rate/rate[0]
    curves[name]={'c':c,'u':u,'rate':rate,'yn':yn}
    rho,_=spearmanr(c,rate); tau,_=kendalltau(c,rate)
    for model,fn,p0,bounds in [
        ('exponential',exp_norm,1,(0,np.inf)),
        ('linear',lin_norm,.5,(0,.999999)),
        ('reciprocal',recip_norm,1,(0,np.inf)),
    ]:
        b,pred,rmse,r2=fit_model(u,yn,fn,p0,bounds)
        cv,_=loocv(u,yn,fn,p0,bounds)
        rows.append({'dataset':name,'model':model,'parameter':b,'normalized_rmse':rmse,'normalized_r2':r2,'loocv_rmse':cv,'spearman_concurrency_rate':rho,'kendall_concurrency_rate':tau,'terminal_rate_fraction':yn[-1]})
summary=pd.DataFrame(rows)
summary.to_csv(RESULTS / 'cross_hardware_model_fits.csv',index=False)

# Shared exponential beta on the first 3 distinct hardware/model domains.
primary=list(datasets)[:3]
U=np.concatenate([curves[n]['u'] for n in primary]); Y=np.concatenate([curves[n]['yn'] for n in primary])
b_shared,_=curve_fit(exp_norm,U,Y,p0=[1.0],bounds=(0,np.inf),maxfev=10000)
b_shared=float(b_shared[0]); pred=exp_norm(U,b_shared)
shared={'beta_shared':b_shared,'normalized_rmse':float(np.sqrt(np.mean((Y-pred)**2))),'normalized_r2':float(1-np.sum((Y-pred)**2)/np.sum((Y-Y.mean())**2))}

# Leave-one-domain-out shared beta.
lodo=[]
for held in primary:
    train=[n for n in primary if n!=held]
    u_tr=np.concatenate([curves[n]['u'] for n in train]); y_tr=np.concatenate([curves[n]['yn'] for n in train])
    b,_=curve_fit(exp_norm,u_tr,y_tr,p0=[1.0],bounds=(0,np.inf),maxfev=10000); b=float(b[0])
    y=curves[held]['yn']; u=curves[held]['u']; p=exp_norm(u,b)
    lodo.append({'held_out_dataset':held,'trained_beta':b,'normalized_rmse':float(np.sqrt(np.mean((y-p)**2))),'max_absolute_error':float(np.max(np.abs(y-p))),'spearman_pred_observed':float(spearmanr(p,y).statistic),'kendall_pred_observed':float(kendalltau(p,y).statistic)})
pd.DataFrame(lodo).to_csv(RESULTS / 'cross_hardware_leave_one_domain_out.csv',index=False)

# Pairwise curve distances on common u points (same six concurrency levels).
pairs=[]
for i,a in enumerate(primary):
    for b in primary[i+1:]:
        ya=curves[a]['yn']; yb=curves[b]['yn']
        pairs.append({'dataset_a':a,'dataset_b':b,'rmse_between_normalized_curves':float(np.sqrt(np.mean((ya-yb)**2))),'max_absolute_difference':float(np.max(np.abs(ya-yb))),'spearman':float(spearmanr(ya,yb).statistic),'kendall':float(kendalltau(ya,yb).statistic)})
pd.DataFrame(pairs).to_csv(RESULTS / 'cross_hardware_curve_distances.csv',index=False)

# Residual bootstrap for exponential beta in each primary domain.
rng=np.random.default_rng(20260720); boots=[]
for name in primary:
    u=curves[name]['u']; y=curves[name]['yn']
    b,p,_,_=fit_model(u,y,exp_norm,1,(0,np.inf)); resid=y-p
    draws=[]
    for _ in range(5000):
        yy=np.clip(p+rng.choice(resid,size=len(resid),replace=True),1e-5,1.5)
        try:
            bb,_=curve_fit(exp_norm,u,yy,p0=[b],bounds=(0,np.inf),maxfev=2000)
            draws.append(float(bb[0]))
        except Exception: pass
    arr=np.array(draws)
    boots.append({'dataset':name,'n_bootstrap':len(arr),'beta_hat':b,'beta_ci_low':float(np.quantile(arr,.025)),'beta_ci_high':float(np.quantile(arr,.975)),'terminal_fraction_hat':float(np.exp(-b)),'terminal_fraction_ci_low':float(np.quantile(np.exp(-arr),.025)),'terminal_fraction_ci_high':float(np.quantile(np.exp(-arr),.975))})
pd.DataFrame(boots).to_csv(RESULTS / 'cross_hardware_bootstrap_summary.csv',index=False)

out={'shared_fit':shared,'domain_fits':summary[summary.model=='exponential'].to_dict(orient='records'),'leave_one_domain_out':lodo,'pairwise':pairs,'bootstrap':boots}
(RESULTS / 'cross_hardware_validation_summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
