# Guarded multi-fidelity optimization with trace-derived risk auditing

This repository contains the manuscript, simulation and optimization code,
policy surfaces, calibration data, trace-derived experiments, operating-envelope
analysis, fresh-seed confirmation, lock manifests, and audit materials for:

> **Guarded Multi-Fidelity Optimization with Trace-Derived Risk Auditing for
> Privacy-Constrained Cloud-Edge LLM Serving**

The manuscript is prepared for *Future Internet*, Special Issue
**Cloud/Edge Computing for Next-Generation Networks: Architecture and
Applications**.

## Release status

**V15 / release 1.5.0 is the current candidate.**

The release preserves the locked V11 result: under the original 2% protected-
blocking and 5% eligible-blocking limits, all 120 DR-BGS and guarded-GP method
runs abstain. V12 then exhaustively evaluates all 190 policies in all 12
original trace-derived scenarios and finds 0/2,280 certifiable policy-scenario
pairs. Increasing the evidence batch to 1,200 replays does not repair the
original regime.

V12 also maps an exploratory operating envelope. Substantial load reduction is
the most consistent path to certification; faster activation alone does not
suffice, and capacity-only expansion through K=240 succeeds in only two of
twelve scenarios. V13 fixes an interior point, K=40 and rho=0.05, before new
result generation. All six unique DR-BGS scenario-policy pairs, twenty guarded-
GP pairs, and six exhaustive-training pairs pass two disjoint 1,200-replay
batches. This is an operating-envelope confirmation, not a production-safety
claim or a practical recommendation for the original load levels.

The public GitHub tag and version-specific Zenodo DOI must be activated and
verified before submission.

## Main evidence

### Synthetic benchmark

| Method | Runs within 1% | Maximum holdout excess |
|---|---:|---:|
| Breadth-first two-stage R&S | 70.56% | 11.67% |
| Standard GP | 95.56% | 7.220% |
| Guarded GP without residual | 100.00% | 0.878% |
| DR-BGS | 100.00% | 0.348% |

DR-BGS evaluates 20 of 190 policies and reduces high-fidelity replications by
88.77%. The same-anchor ablation shows that structural coverage explains most
of the reliability.

### Original strict trace regime

- Trace rows: the first 100 chronological rows of the official `BurstGPT_1.csv` release, 95 with positive tokens.
- Search/certification split: first 60 / later 35 positive-token records.
- Original loads: rho in {0.70, 0.90}.
- Absolute gate: 2% protected blocking, 5% eligible blocking, 10% violation-risk budget.
- Method result: 0/120 certified.
- Exhaustive result: 0/2,280 policy-scenario pairs certified.
- Evidence expansion to 1,200 replays: still zero certifications at baseline.

### Exploratory operating envelope

- Load-only certification occurs only at rho=0.05 or 0.075, depending on scenario.
- No load-only case certifies at rho >= 0.10.
- Capacity-only expansion through K=240 certifies 2/12 scenarios.
- Reducing activation delay to 0.10 certifies 0/12 scenarios.
- Conditional on a certifiable policy existing, DR-BGS certifies 135/190
  nominations and guarded GP 140/190. No superiority claim is made.

### Separately locked low-load confirmation

At K=40 and rho=0.05, using two disjoint 1,200-replay batches:

| Method | Unique scenario-policy pairs | Passed both batches |
|---|---:|---:|
| DR-BGS | 6 | 6 |
| Guarded GP | 20 | 20 |
| Exhaustive training | 6 | 6 |

The 60 DR-BGS initialization labels reduce to six unique physical
scenario-policy pairs and are not treated as independent validation trials.


### Seven-day trace robustness replication

A separately locked replication uses a fixed seven-day chronological window from the official `BurstGPT_1.csv` release:

- Search pool: 11,810 positive-token records from the first five days.
- Certification pool: 6,086 positive-token records from the later two days.
- High-load exhaustive audit: 0/2,280 policy-scenario pairs certified.
- High-load method labels: DR-BGS 0/60; guarded GP 0/60.
- Low-load two-batch confirmation: DR-BGS 6/6, guarded GP 12/12, exhaustive training 6/6 unique method-specific pairs.
- Cross-method deduplication: 18/18 distinct scenario-policy pairs pass both batches.

This replication reduces dependence on the compact 95-positive-record slice but does not establish production safety or full-corpus representativeness.

### Retrospective noninferiority follow-up

- DR-BGS: 50/60 certified.
- Guarded GP: 33/60 certified.
- Every certified label recovers the exhaustive training-selected policy.
- The comparison is retrospective because the reference requires exhaustive evaluation.

## Fast audit

```bash
python -m pip install -r requirements.txt
make audit-v15
```

The V15 audit preserves the original V11 audit hierarchy. As part of the Branch B implementation, the previous filesystem timestamp (mtime) chronology workaround has been removed due to its inherent limitations on Windows/CI environments. The audit now enforces cryptographic immutable provenance by explicitly validating the `V15_PRE_RESULT_LOCK.json` timestamp and ensuring the tracked lock files rigidly match the holistic `SHA256SUMS.txt` cryptographic manifest. It additionally verifies the seven-day trace provenance and locked V15 results, reruns the V11 integrity checks, verifies V12/V13 key-result files, checks numerical claims in the manuscript, compiles Python sources and LaTeX, and validates the release manifest. Note that active 'V14' logic dependencies have been fully removed and reverted to their true 'V11' source layer.

## Directory guide

- `manuscript/`: V15 candidate manuscript, cover letter, highlights, declarations, figures.
- `code/`: core diffusion and compound-jump simulator.
- `v7_code/`--`v11_code/`: archived synthetic and trace-study code.
- `results/`, `v7_results/`--`v11_results/`: archived V6--V11 results.
- `v12_exploratory/`: complete corrected operating-envelope outputs and audit.
- `v13_confirmatory/`: protocol, locks, amendment record, raw results, corrected report, audit.
- `v15_seven_day_robustness/`: locked seven-day protocol, code, outputs, figures, hashes, and report.
- `audit_v11/`: locked V11 audit and chronology materials.
- `audit_v15/`: final V15 trace-provenance, result, manuscript, and package audit.
- `trace_data/`: exact compact and seven-day BurstGPT-derived input slices plus provenance records.
- `calibration/`: vLLM telemetry and service-law calibration.

## Claim boundary

The release does not establish production safety, full-corpus trace
representativeness, cryptographic privacy, a block-level KV-cache model, a
general safe- or multi-fidelity-BO theorem, DR-BGS superiority in every shifted
regime, or population reliability from duplicated initialization labels. Risk
statements are conditional on the declared simulator and replay generator.

Code is licensed under MIT. Original project data and result tables are
licensed under CC BY 4.0. The included BurstGPT-derived slice remains subject
to the source dataset's attribution requirements.
