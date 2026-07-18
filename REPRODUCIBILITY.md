# Reproducibility notes - V11

## Evidence hierarchy

1. V11 strict trace study and lock: `config/TRACE_RISK_STUDY_V11.yaml`,
   `audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256`, and `v11_results/`.
2. V11 retrospective noninferiority follow-up and separate lock.
3. V12 exploratory frontier under `v12_exploratory/`; it does not replace V11.
4. V13 pre-result configuration and lock under `v13_confirmatory/`.
5. V13 seed-range amendment, which changed only invalid seed integers before
   successful result generation.
6. V13 corrected duplicate-aware report and final audit.

## Fast checks

```bash
make locks
make audit-v15
```

## Original strict regime

The later trace pool is used with K=40, rho in {0.70,0.90}, protected fraction
in {0.20,0.50,0.80}, and activation delay in {0.5,2.0}. The unchanged gate
requires one-sided exact upper violation-risk bounds no greater than 0.10 for
both 2% protected-blocking and 5% eligible-blocking limits.

V11 gives 0/120 method certifications. V12 evaluates every policy and confirms
0/2,280 certified policy-scenario pairs. Baseline evidence prefixes through
1,200 replays remain uncertified.

## Exploratory operating envelope

V12 covers 549 scenario-configuration batches and 325 distinct physical
settings, evaluating all 190 policies with 150 replays per batch. The study is
exploratory and all configurations, including failures, are retained.

## Separately locked confirmation

V13 fixes K=40 and rho=0.05 after V12 is complete and before new results. Six
physical scenarios cross qH in {0.20,0.50,0.80} and tau in {0.5,2.0}. Each
nomination is evaluated on two disjoint 1,200-replay batches. All six unique
DR-BGS pairs, twenty guarded-GP pairs, and six exhaustive-training pairs pass
both batches. Duplicated initialization labels are not used as independent
trials.
