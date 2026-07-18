#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, math, py_compile, re, subprocess
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
MAN=ROOT/'manuscript'/'FutureInternet_manuscript_submission_v11.tex'
PDF=ROOT/'manuscript'/'FutureInternet_manuscript_submission_v11.pdf'
checks=[]

def check(name, ok, detail):
    checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)})
    if not ok: print('FAIL',name,detail)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# Locked inputs and chronology
expected={
 'config/TRACE_RISK_STUDY_V11.yaml':'498cad6ac7d5a77d977f1f56e778ad5d7912bcd1a77c4238a442941d046fe205',
 'trace_data/BurstGPT_first100_public.csv':'a2675f51ec359eec09a97d92e0a861171264c207e99aa462c2815845ce606143',
 'v11_code/run_trace_risk_study.py':'6c9de6920ff43a04a49a3c4eeaefb7c6073b41b2b34ff498740c72dcbcdc694d',
}
for rel,h in expected.items(): check('sha256 '+rel,sha(ROOT/rel)==h,sha(ROOT/rel))
primary_lock=ROOT/'audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256'
follow_lock=ROOT/'audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256'
chron=json.loads((ROOT/'audit_v11/LOCK_CHRONOLOGY_V11.json').read_text())['files']
# Use the archived chronology snapshot rather than current filesystem mtimes,
# because Git checkout and ZIP extraction can reset timestamps. This remains
# an internal provenance record, not a trusted timestamp.
def archived_time(rel):
    return float(chron[rel]['archived_mtime_unix'])
def chronology_hash_ok(rel):
    return chron[rel]['sha256']==sha(ROOT/rel)
for rel in ['audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256','config/TRACE_RISK_STUDY_V11.yaml','trace_data/BurstGPT_first100_public.csv','v11_code/run_trace_risk_study.py','v11_results/trace_risk_runs.csv','audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256','config/TRACE_NONINFERIORITY_FOLLOWUP_V11.yaml','v11_code/run_trace_noninferiority_followup.py','v11_results/trace_noninferiority_runs.csv']:
    check('chronology snapshot hash '+rel, chronology_hash_ok(rel), chron[rel]['sha256'])
for rel in ['config/TRACE_RISK_STUDY_V11.yaml','trace_data/BurstGPT_first100_public.csv','v11_code/run_trace_risk_study.py']:
    check('archived primary lock follows '+rel, archived_time('audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256') >= archived_time(rel), 'internal archive chronology')
check('archived primary lock precedes strict results',archived_time('audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256') < archived_time('v11_results/trace_risk_runs.csv'),'internal archive chronology')
check('archived follow-up inputs precede follow-up lock',
      archived_time('config/TRACE_NONINFERIORITY_FOLLOWUP_V11.yaml') <= archived_time('audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256') and
      archived_time('v11_code/run_trace_noninferiority_followup.py') <= archived_time('audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256'),
      'internal archive chronology')
check('archived follow-up lock precedes follow-up results',archived_time('audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256') < archived_time('v11_results/trace_noninferiority_runs.csv'),'internal archive chronology')

# Trace data
trace=pd.read_csv(ROOT/'trace_data/BurstGPT_first100_public.csv')
pos=trace[trace['Total tokens']>0].reset_index(drop=True)
check('trace source rows',len(trace)==100,len(trace))
check('positive rows',len(pos)==95,len(pos))
check('chronological order',bool(np.all(np.diff(pos.Timestamp.to_numpy(float))>=0)),'nondecreasing timestamps')
check('search/cert split',len(pos.iloc[:60])==60 and len(pos.iloc[60:])==35,'60/35')
check('training token median',float(pos.iloc[:60]['Total tokens'].median())==912.0,float(pos.iloc[:60]['Total tokens'].median()))

# Strict outputs
surf=pd.read_csv(ROOT/'v11_results/trace_policy_surfaces.csv')
runs=pd.read_csv(ROOT/'v11_results/trace_risk_runs.csv')
summary=pd.read_csv(ROOT/'v11_results/trace_risk_summary.csv')
check('trace surface rows',len(surf)==12*190,len(surf))
check('strict run rows',len(runs)==12*2*5,len(runs))
check('strict unique scenarios',runs.scenario_id.nunique()==12,runs.scenario_id.nunique())
check('strict all finite',bool(np.isfinite(runs.select_dtypes(include=[np.number]).to_numpy()).all()),'numeric columns')
check('strict universal abstention',int(runs.certified.sum())==0,int(runs.certified.sum()))
check('strict DR max holdout excess',math.isclose(runs[runs.method=='DR-BGS'].holdout_excess.max(),0.14988635716083232,rel_tol=1e-12),runs[runs.method=='DR-BGS'].holdout_excess.max())
check('strict GP p90 excess',math.isclose(runs[runs.method=='Guarded-GP'].holdout_excess.quantile(.9),0.07263211520118233,rel_tol=1e-12),runs[runs.method=='Guarded-GP'].holdout_excess.quantile(.9))
reduction=1-(20*12+150)/(190*12+150)
check('trace work reduction',math.isclose(reduction,0.8395061728395061,rel_tol=1e-15),reduction)

# Follow-up outputs
ni=pd.read_csv(ROOT/'v11_results/trace_noninferiority_runs.csv')
nis=pd.read_csv(ROOT/'v11_results/trace_noninferiority_summary.csv')
check('follow-up run rows',len(ni)==120,len(ni))
check('follow-up all finite',bool(np.isfinite(ni.select_dtypes(include=[np.number]).to_numpy()).all()),'numeric columns')
dr=ni[ni.method=='DR-BGS']; gp=ni[ni.method=='Guarded-GP']
check('DR certified count',int(dr.certified.sum())==50,int(dr.certified.sum()))
check('GP certified count',int(gp.certified.sum())==33,int(gp.certified.sum()))
check('DR certified fraction',math.isclose(dr.certified.mean(),5/6,rel_tol=1e-15),dr.certified.mean())
check('GP certified fraction',math.isclose(gp.certified.mean(),0.55,rel_tol=1e-15),gp.certified.mean())
check('certified implies exact reference recovery',bool((ni.loc[ni.certified==1,'same_policy_as_reference']==1).all()),int(ni.loc[ni.certified==1,'same_policy_as_reference'].sum()))
check('DR full-cert scenarios',int((dr.groupby('scenario_id').certified.sum()==5).sum())==10,int((dr.groupby('scenario_id').certified.sum()==5).sum()))
check('GP full-cert scenarios',int((gp.groupby('scenario_id').certified.sum()==5).sum())==5,int((gp.groupby('scenario_id').certified.sum()==5).sum()))

# Manuscript numerical claims and references
tex=MAN.read_text()
required=['88.77\\%','0.348\\%','0.878\\%','50/60','33/60','83.95\\%','0.149886','Guarded Multi-Fidelity Optimization with Trace-Derived Risk Auditing']
for token in required:
    # 0.149886 is reported rounded as 14.99%, so accept either.
    ok=token in tex or (token=='0.149886' and '14.99\\%' in tex)
    check('manuscript contains '+token,ok,token)
cites=[]
for b in re.findall(r'\\cite\{([^}]+)\}',tex): cites.extend(x.strip() for x in b.split(','))
bibs=re.findall(r'\\bibitem\{([^}]+)\}',tex)
check('no missing citations',not(set(cites)-set(bibs)),sorted(set(cites)-set(bibs)))
check('no unused bibliography',not(set(bibs)-set(cites)),sorted(set(bibs)-set(cites)))
check('bibliography unique',len(bibs)==len(set(bibs)),f'{len(bibs)} items')

# Language markers
markers=re.findall(r'(?i)\b(delve|delves|pivotal|groundbreaking|revolutionary|seamlessly|remarkably|breakthrough)\b',tex)
check('selected promotional/AI markers absent',len(markers)==0,markers)

# Python compilation
pyfiles=[x for x in ROOT.rglob('*.py') if '__pycache__' not in x.parts]
errors=[]
for f in pyfiles:
    try: py_compile.compile(str(f),doraise=True)
    except Exception as e: errors.append(f'{f.relative_to(ROOT)}: {e}')
check('all Python files compile',not errors,f'{len(pyfiles)} files; errors={errors}')

# PDF/log
check('manuscript PDF exists',PDF.exists() and PDF.stat().st_size>100000,PDF.stat().st_size if PDF.exists() else 0)
log=ROOT/'manuscript/FutureInternet_manuscript_submission_v11.log'
lt=log.read_text(errors='ignore') if log.exists() else ''
check('no undefined citations/references','undefined citations' not in lt.lower() and 'undefined references' not in lt.lower(),'log scan')
check('no overfull boxes','Overfull \\hbox' not in lt,'log scan')

status='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL'
out={'status':status,'checks':checks,'summary':{
 'checks_total':len(checks),'checks_passed':sum(x['status']=='PASS' for x in checks),
 'checks_failed':sum(x['status']=='FAIL' for x in checks),
 'strict_absolute_certified_runs':int(runs.certified.sum()),
 'dr_noninferiority_certified_runs':int(dr.certified.sum()),
 'gp_noninferiority_certified_runs':int(gp.certified.sum()),
 'trace_work_reduction':reduction,
 'manuscript_sha256':sha(MAN),'pdf_sha256':sha(PDF) if PDF.exists() else None,
}}
(ROOT/'audit_v11/FINAL_AUDIT_V11.json').write_text(json.dumps(out,indent=2))
lines=['# V11 Final Validity and Claims Audit','',f'**Status: {status}**','',
       '## Headline findings','',
       f'- {out["summary"]["checks_passed"]}/{out["summary"]["checks_total"]} automated checks passed.',
       '- The compact trace file contains 100 public-viewer rows, 95 with positive tokens, split chronologically 60/35.',
       '- The strict absolute-SLO gate certified 0/120 method runs and therefore returned universal abstention.',
       '- The independent-seed retrospective noninferiority audit certified 50/60 DR-BGS runs and 33/60 guarded-GP runs.',
       '- Every certified noninferiority run exactly recovered the exhaustive training-selected policy; this is validation, not a deployable optimality certificate.',
       f'- Search plus certification uses {reduction:.2%} fewer replications than exhaustive training evaluation plus the same certification batch.',
       '', '## Claim boundary','',
       '- Arrival times and token counts are trace-derived; privacy labels, pressure conversion, and replay resampling are synthetic.',
       '- The trace study uses a compact public slice, not the full BurstGPT corpus.',
       '- Exact risk bounds are conditional on independent simulator replays from the declared generator.',
       '- Universal abstention is retained as a negative result and does not establish safety.',
       '- The follow-up was designed after the strict result and is not described as external confirmation.',
       '', '## Automated checks','']
for c in checks: lines.append(f'- **{c["status"]}** — {c["name"]}: {c["detail"]}')
(ROOT/'audit_v11/FINAL_AUDIT_REPORT_V11.md').write_text('\n'.join(lines)+'\n')
print(status, out['summary'])
