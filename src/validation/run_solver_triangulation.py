import numpy as np, pandas as pd, math, json, time
from pathlib import Path
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.special import gammaincc
from scipy.stats import t as student_t
from numba import njit

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_SYNTHETIC = REPOSITORY_ROOT / "data" / "synthetic"
DATA_CALIBRATION = REPOSITORY_ROOT / "data" / "calibration"
RESULTS = REPOSITORY_ROOT / "results" / "analytical_validation"
RESULTS.mkdir(parents=True, exist_ok=True)

sc=pd.read_csv(DATA_SYNTHETIC / 'scenario_definitions.csv').set_index('scenario_id')
surf=pd.read_csv(DATA_SYNTHETIC / 'policy_surfaces.csv')
val=pd.read_csv(RESULTS / 'validation_by_scenario.csv').set_index('scenario_id')

def gamma_tail(rem,mean,cv):
 shape=1/(cv*cv); scale=mean/shape; z=np.maximum(rem,0)/scale; out=gammaincc(shape,z); out=np.asarray(out); out[rem<0]=1; return out
def gamma_tail_work(rem,mean,cv):
 shape=1/(cv*cv); scale=mean/shape; z=np.maximum(rem,0)/scale; out=gammaincc(shape+1,z); out=np.asarray(out); out[rem<0]=1; return out

def ctmc_metrics(r,on,off,N):
 K=float(r.K); x=np.linspace(0,K,N); h=x[1]-x[0]; rows=[]; cols=[]; data=[]
 m2H=r.mean_H**2*(1+r.cv_H**2); m2L=r.mean_L**2*(1+r.cv_L**2)
 inputH=r.lambda_H*r.mean_H; inputL=r.lambda_L*r.mean_L; theta=1/r.tau; muc=1/r.deactivation_mean
 def add(i,j,v):
  if v!=0: rows.append(i);cols.append(j);data.append(v)
 for n in range(3):
  local=inputH+(inputL if n<2 else 0); var=r.lambda_H*m2H+(r.lambda_L*m2L if n<2 else 0)
  for ix,xx in enumerate(x):
   idx=n*N+ix; service=r.mu_max*math.exp(-r.beta*xx/K); b=-service+local; a=max(var,1e-9); up=a/(2*h*h)+max(b,0)/h; down=a/(2*h*h)+max(-b,0)/h; total=0
   if ix<N-1:add(idx,idx+1,up);total+=up
   if ix>0:add(idx,idx-1,down);total+=down
   if n==0 and xx>=on:add(idx,N+ix,r.lambda_L);total+=r.lambda_L
   elif n==1:add(idx,2*N+ix,theta);total+=theta
   elif n==2 and xx<off:add(idx,ix,muc);total+=muc
   add(idx,idx,-total)
 Q=sparse.csr_matrix((data,(rows,cols)),shape=(3*N,3*N)); A=Q.T.tolil(); bvec=np.zeros(3*N); A[-1,:]=np.ones(3*N); bvec[-1]=1; p=spsolve(A.tocsr(),bvec); p=np.asarray(p); p[np.abs(p)<1e-14]=0;p/=p.sum();P=p.reshape(3,N); pall=P.sum(0); rem=K-x
 tH=gamma_tail(rem,r.mean_H,r.cv_H);tL=gamma_tail(rem,r.mean_L,r.cv_L);wH=gamma_tail_work(rem,r.mean_H,r.cv_H);wL=gamma_tail_work(rem,r.mean_L,r.cv_L)
 BH=float((pall*tH).sum());BL=float(((P[0]+P[1])*tL).sum()); localH=inputH*float((pall*(1-wH)).sum());localL=inputL*float(((P[0]+P[1])*(1-wL)).sum()); admitted=max(localH+localL,1e-12);meanx=float((pall*x).sum());W=meanx/admitted;cf=float(P[2].sum()); obj=r.cW*W+r.cB*BH+r.cL*BL+(r.cC*r.cloud_cost_multiplier)*cf
 return {'objective':obj,'W':W,'B_H':BH,'B_L':BL,'cloud_fraction':cf,'mass_error':abs(p.sum()-1),'min_probability':float(p.min()),'residual_inf':float(np.max(np.abs(p@Q)))}

@njit(cache=True)
def reflect(y,K):
 z=y%(2*K)
 return K-abs(z-K)
@njit(cache=True)
def sim_path(seed,K,mu_max,beta,inputH,inputL,varH,varL,lamL,theta,muc,on,off,dt,burn_steps,n_steps,stride):
 np.random.seed(seed); x=0.0; n=0; count=(n_steps-burn_steps)//stride; xs=np.empty(count); ns=np.empty(count,np.int64);j=0
 for it in range(n_steps):
  local=inputH+(inputL if n<2 else 0.0); var=varH+(varL if n<2 else 0.0); drift=-mu_max*math.exp(-beta*x/K)+local; x=reflect(x+drift*dt+math.sqrt(var*dt)*np.random.randn(),K)
  rate=0.0
  if n==0 and x>=on: rate=lamL
  elif n==1: rate=theta
  elif n==2 and x<off: rate=muc
  if rate>0 and np.random.rand()<1-math.exp(-rate*dt):
   if n==0:n=1
   elif n==1:n=2
   else:n=0
  if it>=burn_steps and ((it-burn_steps)%stride==0): xs[j]=x;ns[j]=n;j+=1
 return xs,ns

def sample_metrics(r,xs,ns):
 K=r.K;rem=K-xs;tH=gamma_tail(rem,r.mean_H,r.cv_H);tL=gamma_tail(rem,r.mean_L,r.cv_L);wH=gamma_tail_work(rem,r.mean_H,r.cv_H);wL=gamma_tail_work(rem,r.mean_L,r.cv_L); inactive=(ns<2);inputH=r.lambda_H*r.mean_H;inputL=r.lambda_L*r.mean_L;BH=tH.mean();BL=(tL*inactive).mean();ad=inputH*(1-wH).mean()+inputL*((1-wL)*inactive).mean();W=xs.mean()/max(ad,1e-12);cf=(ns==2).mean();obj=r.cW*W+r.cB*BH+r.cL*BL+r.cC*r.cloud_cost_multiplier*cf;return np.array([obj,W,BH,BL,cf])

def mc_metrics(r,on,off,seed):
 dt=.001; horizon=12000.;burn=1500.; stride=20;n_steps=int(horizon/dt);burn_steps=int(burn/dt);m2H=r.mean_H**2*(1+r.cv_H**2);m2L=r.mean_L**2*(1+r.cv_L**2);xs,ns=sim_path(seed,r.K,r.mu_max,r.beta,r.lambda_H*r.mean_H,r.lambda_L*r.mean_L,r.lambda_H*m2H,r.lambda_L*m2L,r.lambda_L,1/r.tau,1/r.deactivation_mean,on,off,dt,burn_steps,n_steps,stride)
 # 20 contiguous batch means
 batches=[]
 for inds in np.array_split(np.arange(len(xs)),20):batches.append(sample_metrics(r,xs[inds],ns[inds]))
 arr=np.vstack(batches); mean=arr.mean(0); hw=student_t.ppf(.975,19)*arr.std(0,ddof=1)/math.sqrt(20)
 return dict(zip(['objective','W','B_H','B_L','cloud_fraction'],mean)),dict(zip(['objective','W','B_H','B_L','cloud_fraction'],hw))

# Select six challenging/representative scenarios.
cands=[]
for col,which in [('third_order_indicator','idxmin'),('third_order_indicator','idxmax'),('beta','idxmin'),('beta','idxmax'),('spearman_diff_holdout','idxmin'),('spearman_diff_holdout','idxmax')]:
 sid=getattr(val[col],which)();cands.append(sid)
selected=['F01','R24','R07','R20','R23','V06']

rows=[]; start=time.time()
for si,sid in enumerate(selected):
 r=sc.loc[sid]; g=surf[surf.scenario_id==sid].sort_values('policy_idx').reset_index(drop=True); K=r.K
 didx=int(np.argmin(g.diffusion_objective.to_numpy())); tidx=int(np.argmin(g.train_objective.to_numpy())); cidx=int(np.argmin(np.linalg.norm(g[['alpha_on','alpha_off']].to_numpy()-np.array([.5*K,.5*K]),axis=1))); policy_ids=[didx]; pnames=['diffusion_best'];
 if tidx not in policy_ids: policy_ids.append(tidx); pnames.append('exhaustive_train_best')
 else:
  alt=next(int(i) for i in np.argsort(g.train_objective.to_numpy()) if int(i) not in policy_ids); policy_ids.append(alt); pnames.append('second_best_train')
 if cidx not in policy_ids: policy_ids.append(cidx); pnames.append('center_diagonal')
 else:
  target=np.array([.95*K,.05*K]); alt=int(np.argmin(np.linalg.norm(g[['alpha_on','alpha_off']].to_numpy()-target,axis=1)));
  if alt in policy_ids: alt=next(int(i) for i in range(len(g)) if int(i) not in policy_ids)
  policy_ids.append(alt); pnames.append('upper_offdiagonal')
 for pi,(pid,pname) in enumerate(zip(policy_ids,pnames)):
  row=g.iloc[pid];on=float(row.alpha_on);off=float(row.alpha_off);arch=float(row.diffusion_objective)
  m161=ctmc_metrics(r,on,off,161);m321=ctmc_metrics(r,on,off,321);mc,hw=mc_metrics(r,on,off,20260720+si*10)
  rows.append({'scenario_id':sid,'policy_role':pname,'policy_idx':pid,'alpha_on':on,'alpha_off':off,'archived_objective':arch,'ctmc161_objective':m161['objective'],'ctmc321_objective':m321['objective'],'ctmc161_abs_error_vs_archive':abs(m161['objective']-arch),'grid_relative_change':abs(m321['objective']-m161['objective'])/max(abs(m321['objective']),1e-12),'mc_objective':mc['objective'],'mc_objective_ci95_hw':hw['objective'],'mc_relative_error_vs_ctmc321':abs(mc['objective']-m321['objective'])/max(abs(m321['objective']),1e-12),'mc_ci_covers_ctmc321':int(abs(mc['objective']-m321['objective'])<=hw['objective']),'ctmc321_W':m321['W'],'mc_W':mc['W'],'mc_W_hw':hw['W'],'ctmc321_B_H':m321['B_H'],'mc_B_H':mc['B_H'],'mc_B_H_hw':hw['B_H'],'ctmc321_B_L':m321['B_L'],'mc_B_L':mc['B_L'],'mc_B_L_hw':hw['B_L'],'ctmc321_cloud_fraction':m321['cloud_fraction'],'mc_cloud_fraction':mc['cloud_fraction'],'mc_cloud_fraction_hw':hw['cloud_fraction']})
out=pd.DataFrame(rows);out.to_csv(RESULTS / 'solver_triangulation.csv',index=False)
rank_rows=[]
for sid,gg in out.groupby('scenario_id'):
 from scipy.stats import spearmanr,kendalltau
 rank_rows.append({'scenario_id':sid,'spearman_ctmc_mc':float(spearmanr(gg.ctmc321_objective,gg.mc_objective).statistic),'kendall_ctmc_mc':float(kendalltau(gg.ctmc321_objective,gg.mc_objective).statistic),'best_policy_agreement':int(gg.loc[gg.ctmc321_objective.idxmin(),'policy_idx']==gg.loc[gg.mc_objective.idxmin(),'policy_idx'])})
rankdf=pd.DataFrame(rank_rows);rankdf.to_csv(RESULTS / 'solver_policy_ranking.csv',index=False)
summary={'selected_scenarios':selected,'n_policy_cases':len(out),'median_policy_rank_spearman':float(rankdf.spearman_ctmc_mc.median()),'best_policy_agreement_fraction':float(rankdf.best_policy_agreement.mean()),'max_ctmc161_abs_error_vs_archive':float(out.ctmc161_abs_error_vs_archive.max()),'median_grid_relative_change':float(out.grid_relative_change.median()),'max_grid_relative_change':float(out.grid_relative_change.max()),'median_mc_relative_error_vs_ctmc321':float(out.mc_relative_error_vs_ctmc321.median()),'p90_mc_relative_error_vs_ctmc321':float(out.mc_relative_error_vs_ctmc321.quantile(.9)),'max_mc_relative_error_vs_ctmc321':float(out.mc_relative_error_vs_ctmc321.max()),'mc_ci_coverage_fraction':float(out.mc_ci_covers_ctmc321.mean()),'runtime_seconds':time.time()-start}
(RESULTS / 'solver_triangulation_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2));print(out[['scenario_id','policy_role','archived_objective','ctmc161_objective','ctmc321_objective','mc_objective','mc_objective_ci95_hw','mc_relative_error_vs_ctmc321']].to_string(index=False))
