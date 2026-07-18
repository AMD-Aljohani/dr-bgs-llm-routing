# V11 Final Validity and Claims Audit

**Status: PASS**

## Headline findings

- 56/56 automated checks passed.
- The compact trace file contains 100 public-viewer rows, 95 with positive tokens, split chronologically 60/35.
- The strict absolute-SLO gate certified 0/120 method runs and therefore returned universal abstention.
- The independent-seed retrospective noninferiority audit certified 50/60 DR-BGS runs and 33/60 guarded-GP runs.
- Every certified noninferiority run exactly recovered the exhaustive training-selected policy; this is validation, not a deployable optimality certificate.
- Search plus certification uses 83.95% fewer replications than exhaustive training evaluation plus the same certification batch.

## Claim boundary

- Arrival times and token counts are trace-derived; privacy labels, pressure conversion, and replay resampling are synthetic.
- The trace study uses a compact public slice, not the full BurstGPT corpus.
- Exact risk bounds are conditional on independent simulator replays from the declared generator.
- Universal abstention is retained as a negative result and does not establish safety.
- The follow-up was designed after the strict result and is not described as external confirmation.

## Automated checks

- **PASS** — sha256 config/TRACE_RISK_STUDY_V11.yaml: 498cad6ac7d5a77d977f1f56e778ad5d7912bcd1a77c4238a442941d046fe205
- **PASS** — sha256 trace_data/BurstGPT_first100_public.csv: a2675f51ec359eec09a97d92e0a861171264c207e99aa462c2815845ce606143
- **PASS** — sha256 v11_code/run_trace_risk_study.py: 6c9de6920ff43a04a49a3c4eeaefb7c6073b41b2b34ff498740c72dcbcdc694d
- **PASS** — chronology snapshot hash audit_v11/TRACE_RISK_LOCK_MANIFEST.sha256: cc0b67bb77ac3f76627070655062167db2c19f464aba0a69d95eb43e498aa974
- **PASS** — chronology snapshot hash config/TRACE_RISK_STUDY_V11.yaml: 498cad6ac7d5a77d977f1f56e778ad5d7912bcd1a77c4238a442941d046fe205
- **PASS** — chronology snapshot hash trace_data/BurstGPT_first100_public.csv: a2675f51ec359eec09a97d92e0a861171264c207e99aa462c2815845ce606143
- **PASS** — chronology snapshot hash v11_code/run_trace_risk_study.py: 6c9de6920ff43a04a49a3c4eeaefb7c6073b41b2b34ff498740c72dcbcdc694d
- **PASS** — chronology snapshot hash v11_results/trace_risk_runs.csv: c75d094728d30ca19dbd3875ecaffe3cd67c9ee94b91f61c34643786af320ba5
- **PASS** — chronology snapshot hash audit_v11/TRACE_NONINFERIORITY_FOLLOWUP_LOCK.sha256: 684758f1a29d55b9811be3037a8410083acdc8278fb01bdfe5fc907d4f2456d7
- **PASS** — chronology snapshot hash config/TRACE_NONINFERIORITY_FOLLOWUP_V11.yaml: 4f10a607b195598f960f1edfc48c6a62680f326d3857570d6e6ed7cc5d9aa65d
- **PASS** — chronology snapshot hash v11_code/run_trace_noninferiority_followup.py: ce04d513a3f9f32e4720ecc882aabdff231a49f42056cd642aa81a6cde4635d4
- **PASS** — chronology snapshot hash v11_results/trace_noninferiority_runs.csv: f22c4d334176cf8af3ae15181b20d1055d679c64b9dc8cc20b4a3b5b82857f5f
- **PASS** — archived primary lock follows config/TRACE_RISK_STUDY_V11.yaml: internal archive chronology
- **PASS** — archived primary lock follows trace_data/BurstGPT_first100_public.csv: internal archive chronology
- **PASS** — archived primary lock follows v11_code/run_trace_risk_study.py: internal archive chronology
- **PASS** — archived primary lock precedes strict results: internal archive chronology
- **PASS** — archived follow-up inputs precede follow-up lock: internal archive chronology
- **PASS** — archived follow-up lock precedes follow-up results: internal archive chronology
- **PASS** — trace source rows: 100
- **PASS** — positive rows: 95
- **PASS** — chronological order: nondecreasing timestamps
- **PASS** — search/cert split: 60/35
- **PASS** — training token median: 912.0
- **PASS** — trace surface rows: 2280
- **PASS** — strict run rows: 120
- **PASS** — strict unique scenarios: 12
- **PASS** — strict all finite: numeric columns
- **PASS** — strict universal abstention: 0
- **PASS** — strict DR max holdout excess: 0.1498863571608323
- **PASS** — strict GP p90 excess: 0.0726321152011823
- **PASS** — trace work reduction: 0.8395061728395061
- **PASS** — follow-up run rows: 120
- **PASS** — follow-up all finite: numeric columns
- **PASS** — DR certified count: 50
- **PASS** — GP certified count: 33
- **PASS** — DR certified fraction: 0.8333333333333334
- **PASS** — GP certified fraction: 0.55
- **PASS** — certified implies exact reference recovery: 83
- **PASS** — DR full-cert scenarios: 10
- **PASS** — GP full-cert scenarios: 5
- **PASS** — manuscript contains 88.77\%: 88.77\%
- **PASS** — manuscript contains 0.348\%: 0.348\%
- **PASS** — manuscript contains 0.878\%: 0.878\%
- **PASS** — manuscript contains 50/60: 50/60
- **PASS** — manuscript contains 33/60: 33/60
- **PASS** — manuscript contains 83.95\%: 83.95\%
- **PASS** — manuscript contains 0.149886: 0.149886
- **PASS** — manuscript contains Guarded Multi-Fidelity Optimization with Trace-Derived Risk Auditing: Guarded Multi-Fidelity Optimization with Trace-Derived Risk Auditing
- **PASS** — no missing citations: []
- **PASS** — no unused bibliography: []
- **PASS** — bibliography unique: 46 items
- **PASS** — selected promotional/AI markers absent: []
- **PASS** — all Python files compile: 35 files; errors=[]
- **PASS** — manuscript PDF exists: 941921
- **PASS** — no undefined citations/references: log scan
- **PASS** — no overfull boxes: log scan
