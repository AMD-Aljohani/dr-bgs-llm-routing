#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, os, sys, time, json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('basev12','/mnt/data/run_v12_exploratory.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
OUT=b.OUT

LOAD_EXACT_GRID=(0.025,0.05,0.075,0.10,0.125,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.80,0.90)


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}",flush=True)


def make_candidates():
    coarse=pd.read_csv(OUT/'campaign2_coarse_operating_envelope.csv')
    rows=[]; sidn=0
    for base_rho in (0.70,0.90):
        for qh in b.QH_GRID:
            for base_tau in b.TAU_BASE_GRID:
                sidn+=1; sid=f'BG{sidn:02d}'
                labels={}
                def add(K,rho,tau,label):
                    key=(float(K),float(rho),float(qh),float(tau))
                    labels.setdefault(key,[]).append(label)
                # Complete load-only path, including finer low-load points.
                for rho in LOAD_EXACT_GRID:
                    if rho <= base_rho+1e-12:
                        add(40.0,rho,base_tau,'load_path')
                # Complete capacity-only path at the original load.
                for K in b.K_GRID:
                    add(K,base_rho,base_tau,'capacity_path')
                # Complete delay-only path at the original K and load.
                for tau in b.TAU_SWEEP_GRID:
                    add(40.0,base_rho,tau,'delay_path')
                # Coarse joint K-rho feasibility boundary and immediate neighbors.
                sub=coarse[(coarse.tag=='joint_K_rho')&(coarse.qH==qh)&(coarse.tau==base_tau)&
                           (coarse.rho<=base_rho)&(coarse.K>=40)].copy()
                for K in b.K_GRID:
                    sk=sub[sub.K==K].sort_values('rho')
                    feas=sk[sk.mean_feasible_policies>0]
                    if len(feas):
                        boundary=float(feas.rho.max())
                    else:
                        boundary=float(sk.loc[sk.min_max_mean_ratio.idxmin()].rho)
                    vals=sorted(sk.rho.unique())
                    pos=vals.index(boundary)
                    for j,label in ((pos-1,'joint_safer'),(pos,'joint_boundary'),(pos+1,'joint_harder')):
                        if 0<=j<len(vals): add(K,float(vals[j]),base_tau,label)
                # Mark baseline.
                add(40.0,base_rho,base_tau,'baseline')
                for (K,rho,qh2,tau),labs in labels.items():
                    match=coarse[(coarse.K==K)&np.isclose(coarse.rho,rho)&(coarse.qH==qh2)&np.isclose(coarse.tau,tau)]
                    coarse_feas=int(match.mean_feasible_policies.max()) if len(match) else -1
                    coarse_ratio=float(match.min_max_mean_ratio.min()) if len(match) else np.nan
                    rows.append({
                        'original_scenario_id':sid,'base_rho':base_rho,'base_tau':base_tau,
                        'K':K,'rho':rho,'qH':qh2,'tau':tau,
                        'candidate_labels':';'.join(sorted(set(labs))),
                        'intervention_index':b.intervention_index(base_rho,base_tau,K,rho,tau),
                        'coarse_mean_feasible_policies':coarse_feas,
                        'coarse_min_max_mean_ratio':coarse_ratio,
                    })
    return pd.DataFrame(rows).drop_duplicates(['original_scenario_id','K','rho','qH','tau'])


def exact_worker(row):
    sid=row['original_scenario_id']; K=float(row['K']); rho=float(row['rho']); qh=float(row['qH']); tau=float(row['tau'])
    seed=2026084000+int(sid[2:])*10_000_000+int(round(K*10))*10_000+int(round(rho*1000))*10+int(round(tau*10))
    policies,bh,bl,w,cloud=b.simulate_matrix(K,rho,qh,tau,150,seed,'cert')
    mean_bh=bh.mean(axis=1); mean_bl=bl.mean(axis=1); mean_w=w.mean(axis=1); mean_cloud=cloud.mean(axis=1)
    mean_op=(cloud+0.15*w).mean(axis=1)
    policy_rows=[]; cert=np.zeros(190,dtype=int); upper=np.zeros(190)
    for i,(on,off) in enumerate(policies):
        c=b.cp_cert(bh[i],bl[i]); cert[i]=c['certified']; upper[i]=max(c['upper_H'],c['upper_L'])
        policy_rows.append({**row,'policy_idx':i,'alpha_on':on,'alpha_off':off,
                            'mean_B_H':float(mean_bh[i]),'mean_B_L':float(mean_bl[i]),
                            'mean_W':float(mean_w[i]),'mean_cloud_fraction':float(mean_cloud[i]),
                            'mean_op_cost':float(mean_op[i]),**c})
    surface=b.build_training_surface(K,rho,qh,tau,seed+30_000_000)
    selected=[('Exhaustive-training',-1,b.v11.select_from_indices(surface,range(190)))]
    for method,residual in (('DR-BGS',True),('Guarded-GP',False)):
        for init in b.INIT_SEEDS:
            idx,_=b.v11.guarded_search(surface,residual=residual,seed=20260718+init)
            selected.append((method,init,idx))
    method_rows=[]
    for method,init,idx in selected:
        pr=policy_rows[idx]
        method_rows.append({**row,'method':method,'init_seed':init,'selected_idx':idx,
                            'selected_alpha_on':policies[idx][0],'selected_alpha_off':policies[idx][1],
                            'mean_B_H':pr['mean_B_H'],'mean_B_L':pr['mean_B_L'],
                            'mean_W':pr['mean_W'],'mean_cloud_fraction':pr['mean_cloud_fraction'],
                            'mean_op_cost':pr['mean_op_cost'],'viol_H':pr['viol_H'],'viol_L':pr['viol_L'],
                            'upper_H':pr['upper_H'],'upper_L':pr['upper_L'],'certified':pr['certified']})
    best=int(np.lexsort((mean_op,upper))[0])
    summary={**row,'exact_certifiable_policies':int(cert.sum()),
             'best_policy_idx':best,'best_policy_upper':float(upper[best]),
             'best_policy_mean_B_H':float(mean_bh[best]),'best_policy_mean_B_L':float(mean_bl[best]),
             'method_certified_runs':int(sum(x['certified'] for x in method_rows)),'method_runs':len(method_rows)}
    return summary,policy_rows,method_rows


def run_exact(workers=4):
    cand=make_candidates(); cand.to_csv(OUT/'campaign2_v2_candidate_configs.csv',index=False)
    log(f'V2 Campaign 2 exact refinement: {len(cand)} configurations × 190 policies × 150 replays.')
    sums=[]; prows=[]; mrows=[]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(exact_worker,r._asdict()):i for i,r in enumerate(cand.itertuples(index=False))}
        done=0
        for fut in as_completed(futs):
            s,p,m=fut.result(); sums.append(s); prows.extend(p); mrows.extend(m); done+=1
            if done%10==0 or done==len(futs): log(f'Exact refinement {done}/{len(futs)}')
    pd.DataFrame(sums).to_csv(OUT/'campaign2_v2_config_summary.csv',index=False)
    pd.DataFrame(prows).to_csv(OUT/'campaign2_v2_exact_policy_results.csv',index=False)
    pd.DataFrame(mrows).to_csv(OUT/'campaign2_v2_method_runs.csv',index=False)


def choose_regimes_v2():
    s=pd.read_csv(OUT/'campaign2_v2_config_summary.csv')
    rows=[]; sidn=0
    for base_rho in (0.70,0.90):
        for qh in b.QH_GRID:
            for base_tau in b.TAU_BASE_GRID:
                sidn+=1; sid=f'BG{sidn:02d}'
                load=s[(s.original_scenario_id==sid)&(s.K==40)&np.isclose(s.tau,base_tau)&
                       s.candidate_labels.str.contains('load_path')].sort_values('rho').copy()
                cert=load[load.exact_certifiable_policies>0]
                if len(cert): boundary=float(cert.rho.max())
                else: boundary=float(load.loc[load.best_policy_upper.idxmin()].rho)
                vals=sorted(load.rho.unique()); pos=vals.index(boundary)
                picks=[('baseline',base_rho),('boundary_candidate',boundary)]
                if pos+1<len(vals): picks.append(('near_boundary_harder',vals[pos+1]))
                if pos>0: picks.append(('interior_safer',vals[pos-1]))
                for regime,rho in picks:
                    rr=load[np.isclose(load.rho,rho)].iloc[0]
                    rows.append({'original_scenario_id':sid,'base_rho':base_rho,'base_tau':base_tau,
                                 'regime':regime,'K':40.0,'rho':float(rho),'qH':qh,'tau':base_tau,
                                 'boundary_selected_from_150_replays':1,
                                 'selection_exact_certifiable_policies':int(rr.exact_certifiable_policies),
                                 'selection_best_policy_upper':float(rr.best_policy_upper)})
    return pd.DataFrame(rows)


def evidence_worker_v2(row):
    # Adapted from base evidence worker, but uses the monotone load-only regime.
    return b.evidence_worker(row)


def run_evidence(workers=4):
    regimes=choose_regimes_v2(); regimes.to_csv(OUT/'campaign3_v2_regimes.csv',index=False)
    log(f'V2 Campaign 3: {len(regimes)} monotone load-path regimes, up to 1,200 replays.')
    rows=[]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(evidence_worker_v2,r._asdict()):i for i,r in enumerate(regimes.itertuples(index=False))}
        done=0
        for fut in as_completed(futs):
            rows.extend(fut.result()); done+=1
            if done%4==0 or done==len(futs): log(f'Evidence {done}/{len(futs)}')
    df=pd.DataFrame(rows); df.to_csv(OUT/'campaign3_v2_evidence_frontier_runs.csv',index=False)
    sm=df.groupby(['regime','method','evidence_n']).agg(runs=('certified','size'),certified_runs=('certified','sum'),
        certified_fraction=('certified','mean'),decision_reversals=('decision_reversal','sum'),
        median_upper_H=('upper_H','median'),median_upper_L=('upper_L','median')).reset_index()
    sm.to_csv(OUT/'campaign3_v2_evidence_frontier_summary.csv',index=False)


def make_report_v2():
    c1=pd.read_csv(OUT/'campaign1_strict_scenario_summary.csv')
    c1m=pd.read_csv(OUT/'campaign1_method_slo_frontier.csv')
    c2=pd.read_csv(OUT/'campaign2_v2_config_summary.csv')
    c2m=pd.read_csv(OUT/'campaign2_v2_method_runs.csv')
    c3=pd.read_csv(OUT/'campaign3_v2_evidence_frontier_runs.csv')
    # Load-only exact boundary per original scenario.
    bounds=[]
    for sid,g in c2[(c2.K==40)&c2.candidate_labels.str.contains('load_path')].groupby('original_scenario_id'):
        cert=g[g.exact_certifiable_policies>0]
        if len(cert): r=cert.sort_values('rho').iloc[-1]
        else: r=g.loc[g.best_policy_upper.idxmin()]
        bounds.append(r)
    bounds=pd.DataFrame(bounds)
    cap=c2[c2.candidate_labels.str.contains('capacity_path')]
    delay=c2[c2.candidate_labels.str.contains('delay_path')]
    method=c2m.groupby('method').agg(runs=('certified','size'),certified=('certified','sum'),fraction=('certified','mean')).reset_index()
    final=c3[c3.evidence_n==1200].groupby(['original_scenario_id','regime','method']).certified.mean().reset_index()
    sum3=c3.groupby(['regime','method','evidence_n']).certified.mean().reset_index()
    lines=['# V12 Exploratory Certification Frontier — Corrected Full Results','',
    '## Claim boundary','',
    'These analyses are exploratory. They do not replace the locked V11 result, alter its thresholds, or convert a changed operating regime into evidence for the original regime. The V11 absolute-SLO result remains 0/120 method runs certified.','',
    '## Run 1 — Exhaustive current-system feasibility','',
    f'All 190 policies were evaluated in all 12 original later-pool scenarios with 150 independent replays per policy. Exactly {int(c1.certifiable_policies.sum())} of the 2,280 policy-scenario combinations passed the original 2%/5% absolute gate. No original scenario contained a certifiable policy. This establishes that the V11 0/120 result was not caused merely by DR-BGS or guarded-GP selecting the wrong policy; the fixed 190-policy family contained no policy that the independent gate could certify under the original operating conditions.','',
    c1.to_markdown(index=False,floatfmt='.4f'),'','## Run 2 — Engineering operating envelope','',
    f'The corrected exact refinement evaluated {len(c2)} operating configurations. At each configuration, all 190 policies received 150 independent later-pool replays. The sweep includes a fine load-only path, the complete K={list(b.K_GRID)} capacity-only path at the original load, the complete activation-delay path, and coarse joint K-rho boundary points.','',
    'Highest load ratio certified on the load-only path for each original scenario:','',
    bounds[['original_scenario_id','base_rho','qH','tau','rho','exact_certifiable_policies','best_policy_upper','best_policy_mean_B_H','best_policy_mean_B_L']].to_markdown(index=False,floatfmt='.4f'),'',
    f'Capacity-only certification occurred in {cap.groupby("original_scenario_id").exact_certifiable_policies.max().gt(0).sum()} of 12 original scenarios for K up to 240. Delay-only certification occurred in {delay.groupby("original_scenario_id").exact_certifiable_policies.max().gt(0).sum()} of 12 original scenarios over tau={list(b.TAU_SWEEP_GRID)}.','',
    'Method nominations over the full refined configuration set:','',method.to_markdown(index=False,floatfmt='.4f'),'','## Run 3 — Evidence and stability frontier','',
    f'Fresh 1,200-replay sequences were generated for baseline, the load-only boundary selected from the independent 150-replay exploration, one harder load point, and one safer load point. There were {int(c3.decision_reversal.sum())} cases in which a prefix certified but the full 1,200-replay audit did not. These are simulation-stability diagnostics, not estimates of real-world false assurance.','',
    sum3[sum3.evidence_n.isin([50,150,1200])].pivot_table(index=['regime','method'],columns='evidence_n',values='certified').reset_index().to_markdown(index=False,floatfmt='.4f'),'','## Main interpretation','',
    '1. The original strict result is a system-and-policy-family infeasibility result under the declared later-pool generator, not simply a search failure.','',
    '2. Strict certification becomes possible only after a material operating-regime change. The exact load boundary is scenario-dependent and must be reported explicitly; it cannot be presented as success at the original 0.70/0.90 load ratios.','',
    '3. Increasing buffer capacity or shortening cloud activation alone may be insufficient. The tables quantify this rather than implying that more simulation evidence can repair an actually violated SLO.','',
    '4. DR-BGS and guarded GP should be judged as nomination methods. The absolute gate separately determines whether the nominated policy has enough independent evidence for the declared claim.']
    (OUT/'V12_EXPLORATORY_RESULTS_REPORT_CORRECTED.md').write_text('\n'.join(lines),encoding='utf-8')
    key={'campaign1':{'certified_policy_scenario_pairs':int(c1.certifiable_policies.sum()),'scenarios_with_any':int((c1.certifiable_policies>0).sum())},
         'campaign2':{'exact_configurations':int(len(c2)),'load_boundaries':bounds.to_dict(orient='records'),
                      'capacity_only_scenarios_with_certification':int(cap.groupby('original_scenario_id').exact_certifiable_policies.max().gt(0).sum()),
                      'delay_only_scenarios_with_certification':int(delay.groupby('original_scenario_id').exact_certifiable_policies.max().gt(0).sum()),
                      'method_summary':method.to_dict(orient='records')},
         'campaign3':{'decision_reversals':int(c3.decision_reversal.sum()),'summary':sum3.to_dict(orient='records')}}
    (OUT/'V12_KEY_RESULTS_CORRECTED.json').write_text(json.dumps(key,indent=2),encoding='utf-8')


def make_figures_v2():
    import matplotlib.pyplot as plt
    c2=pd.read_csv(OUT/'campaign2_v2_config_summary.csv')
    load=c2[(c2.K==40)&c2.candidate_labels.str.contains('load_path')]
    fig,ax=plt.subplots(figsize=(9,6))
    for sid,g in load.groupby('original_scenario_id'):
        ax.plot(g.sort_values('rho').rho,g.sort_values('rho').exact_certifiable_policies,marker='o',label=sid)
    ax.set_xlabel('Offered-load ratio'); ax.set_ylabel('Number of certifiable policies (of 190)')
    ax.set_title('Exact strict-SLO certification frontier on the load-only path')
    ax.legend(ncol=3,fontsize=7); fig.tight_layout(); fig.savefig(OUT/'campaign2_v2_load_certification_frontier.png',dpi=180); plt.close(fig)
    e=pd.read_csv(OUT/'campaign3_v2_evidence_frontier_summary.csv')
    fig,ax=plt.subplots(figsize=(9,6))
    for (regime,method),g in e.groupby(['regime','method']):
        if method in ('DR-BGS','Guarded-GP','Exhaustive-training'):
            ax.plot(g.evidence_n,g.certified_fraction,marker='o',label=f'{regime}: {method}')
    ax.set_xscale('log'); ax.set_xticks(b.EVIDENCE_N,[str(x) for x in b.EVIDENCE_N]); ax.set_ylim(-.02,1.02)
    ax.set_xlabel('Independent certification replays'); ax.set_ylabel('Certified fraction')
    ax.set_title('Corrected evidence frontier on a monotone load path'); ax.legend(fontsize=6,ncol=2)
    fig.tight_layout(); fig.savefig(OUT/'campaign3_v2_evidence_frontier.png',dpi=180); plt.close(fig)

if __name__=='__main__':
    run_exact(4); run_evidence(4); make_report_v2(); make_figures_v2(); log('Corrected V2 campaigns complete.')
