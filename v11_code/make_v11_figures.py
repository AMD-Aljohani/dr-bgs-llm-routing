#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
MAN=ROOT/'manuscript'
RES=ROOT/'v11_results'
TRACE=ROOT/'trace_data'/'BurstGPT_first100_public.csv'

# Trace slice: token sizes over elapsed time with chronological split.
d=pd.read_csv(TRACE)
d=d[d['Total tokens']>0].reset_index(drop=True)
t=(d['Timestamp']-d['Timestamp'].iloc[0])/60.0
fig,ax=plt.subplots(figsize=(7.1,3.6))
ax.scatter(t.iloc[:60],d['Total tokens'].iloc[:60],s=24,label='Search pool (first 60 positive rows)')
ax.scatter(t.iloc[60:],d['Total tokens'].iloc[60:],s=24,marker='x',label='Certification pool (last 35 positive rows)')
ax.axvline(t.iloc[60],linestyle='--',linewidth=1)
ax.set_xlabel('Elapsed trace time (min)')
ax.set_ylabel('Total tokens per request')
ax.legend(frameon=False,fontsize=8)
ax.grid(alpha=.25)
fig.tight_layout()
for ext in ('pdf','png'):
 fig.savefig(MAN/f'fig_v11_trace_slice.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)

# Absolute SLO certificate: all abstain.
risk=pd.read_csv(RES/'trace_risk_by_scenario.csv')
risk['max_upper']=risk[['max_upper_H','max_upper_L']].max(axis=1)
piv=risk.pivot(index='scenario_id',columns='method',values='max_upper')
fig,ax=plt.subplots(figsize=(7.1,3.7))
x=np.arange(len(piv))
for method,marker in [('DR-BGS','o'),('Guarded-GP','s')]:
 ax.plot(x,piv[method].to_numpy(),marker=marker,linewidth=1.4,label=method)
ax.axhline(.10,linestyle='--',linewidth=1,label='10% risk budget')
ax.set_xticks(x,piv.index,rotation=45)
ax.set_ylim(0,1.05)
ax.set_ylabel('Largest one-sided upper risk bound')
ax.set_xlabel('Trace-derived scenario')
ax.legend(frameon=False,fontsize=8,ncol=3)
ax.grid(alpha=.25)
fig.tight_layout()
for ext in ('pdf','png'):
 fig.savefig(MAN/f'fig_v11_absolute_slo_certification.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)

# Noninferiority certificate.
ni=pd.read_csv(RES/'trace_noninferiority_by_scenario.csv')
piv=ni.pivot(index='scenario_id',columns='method',values='max_upper')
fig,ax=plt.subplots(figsize=(7.1,3.7))
x=np.arange(len(piv))
for method,marker in [('DR-BGS','o'),('Guarded-GP','s')]:
 ax.plot(x,piv[method].to_numpy(),marker=marker,linewidth=1.4,label=method)
ax.axhline(.10,linestyle='--',linewidth=1,label='10% risk budget')
ax.set_xticks(x,piv.index,rotation=45)
ax.set_ylim(0,max(0.72,float(piv.max().max())*1.08))
ax.set_ylabel('Largest one-sided upper risk bound')
ax.set_xlabel('Trace-derived scenario')
ax.legend(frameon=False,fontsize=8,ncol=3)
ax.grid(alpha=.25)
fig.tight_layout()
for ext in ('pdf','png'):
 fig.savefig(MAN/f'fig_v11_noninferiority_certification.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)
