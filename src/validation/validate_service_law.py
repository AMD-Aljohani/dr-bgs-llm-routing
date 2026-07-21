import numpy as np, pandas as pd, json
from scipy.optimize import curve_fit
from scipy.stats import spearmanr, kendalltau
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

df=pd.read_csv(DATA_CALIBRATION / 'qwen_rtx3090_direct_telemetry.csv').sort_values('kv_usage_mean_pct')
z=df.kv_usage_mean_pct.to_numpy(float); y=df.decode_rate_mean_tok_s.to_numpy(float); sd=df.decode_rate_sd_tok_s.to_numpy(float)

def expf(x,a,b): return a*np.exp(-b*x)
def linf(x,a,b): return a-b*x
def recip(x,a,b): return a/(1+b*x)
def quad(x,a,b,c): return a+b*x+c*x*x
models=[('exponential',expf,[55,.03],(0,np.inf)),('linear',linf,[55,1],([-np.inf,-np.inf],[np.inf,np.inf])),('reciprocal',recip,[55,.05],(0,np.inf)),('quadratic',quad,[55,-1,.01],([-np.inf]*3,[np.inf]*3))]
rows=[]
for name,fn,p0,bounds in models:
    p,_=curve_fit(fn,z,y,p0=p0,bounds=bounds,maxfev=100000)
    pred=fn(z,*p); rss=float(np.sum((y-pred)**2)); n=len(y); k=len(p)
    rmse=float(np.sqrt(rss/n)); r2=float(1-rss/np.sum((y-y.mean())**2))
    aic=n*np.log(max(rss/n,1e-300))+2*k
    aicc=float(aic+(2*k*(k+1))/(n-k-1)) if n>k+1 else float('inf')
    loo=[]
    for i in range(n):
        m=np.arange(n)!=i
        try:
            pp,_=curve_fit(fn,z[m],y[m],p0=p,bounds=bounds,maxfev=100000)
            loo.append(float(fn(np.array([z[i]]),*pp)[0]))
        except Exception: loo.append(np.nan)
    cv=float(np.sqrt(np.nanmean((y-np.array(loo))**2)))
    rows.append({'model':name,'parameters':';'.join(f'{v:.10g}' for v in p),'rmse_tok_s':rmse,'r2':r2,'aicc':aicc,'loocv_rmse_tok_s':cv})
out=pd.DataFrame(rows).sort_values('aicc'); out.to_csv(RESULTS / 'service_law_model_comparison.csv',index=False)

# Parametric bootstrap using reported across-sweep SDs, minimum small SD retained.
rng=np.random.default_rng(20260720); draws=[]
for _ in range(10000):
    yy=rng.normal(y,np.maximum(sd,1e-3))
    try:
        p,_=curve_fit(expf,z,yy,p0=[53.6,.034],bounds=(0,np.inf),maxfev=10000)
        draws.append(p)
    except Exception: pass
arr=np.array(draws)
boot={'n':len(arr),'a_hat':float(curve_fit(expf,z,y,p0=[53.6,.034],bounds=(0,np.inf))[0][0]),'b_hat':float(curve_fit(expf,z,y,p0=[53.6,.034],bounds=(0,np.inf))[0][1]),'a_ci':[float(np.quantile(arr[:,0],.025)),float(np.quantile(arr[:,0],.975))],'b_ci':[float(np.quantile(arr[:,1],.025)),float(np.quantile(arr[:,1],.975))]}

# Agreement with independently aggregated Qwen 3090 summary.
d2=pd.read_csv(DATA_CALIBRATION / 'qwen_rtx3090_independent_summary.csv').sort_values('concurrency')
y1=y/y[0]; y2=d2.decode_rate_tok_s.to_numpy(float); y2=y2/y2[0]
agreement={'normalized_rmse':float(np.sqrt(np.mean((y1-y2)**2))),'max_abs_difference':float(np.max(np.abs(y1-y2))),'spearman':float(spearmanr(y1,y2).statistic),'kendall':float(kendalltau(y1,y2).statistic)}
summary={'model_comparison':out.to_dict(orient='records'),'bootstrap':boot,'independent_summary_agreement':agreement,'monotonicity_violations':int(np.sum(np.diff(y)>=0))}
(RESULTS / 'service_law_validation_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
