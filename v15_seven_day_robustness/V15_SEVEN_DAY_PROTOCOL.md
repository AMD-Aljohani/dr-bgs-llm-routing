# V15 Seven-Day BurstGPT Robustness Protocol

## Status and purpose

This study is a separately locked robustness replication. It does not replace the V11 compact-slice study, the V12 exploratory operating-envelope analysis, or the V13 low-load confirmation. Its purpose is to test whether the main high-load abstention and low-load positive-certification findings persist when the workload basis is expanded from 95 positive-token records to a fixed seven-day chronological window from the official `BurstGPT_1.csv` release.

## Trace provenance and split

- Source: official `BurstGPT_1.csv` release.
- Source SHA-256: `46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a`.
- Seven-day window: `0 <= Timestamp < 604800` seconds.
- Search pool: first five days, `0 <= Timestamp < 432000`, positive-token rows only.
- Certification pool: days five through seven, `432000 <= Timestamp < 604800`, positive-token rows only.
- Search rows: 11,810.
- Certification rows: 6,086.
- Privacy labels, pressure conversion, target load, and moving-block replay remain synthetic.

## Fixed replay model

The V11 replay transformation is retained:

- moving-block bootstrap length: 8;
- requests per replay: 560;
- token-to-pressure mapping unchanged;
- privacy labels generated independently at the scenario-specific protected fraction;
- search and certification use disjoint chronological pools and disjoint simulation seeds.

## Campaign A: original high-load robustness audit

Twelve scenarios cross:

- offered-load ratio: 0.70 and 0.90;
- protected fraction: 0.20, 0.50, and 0.80;
- activation delay: 0.5 and 2.0.

For every scenario:

- evaluate all 190 policies with 12 search-pool replications per policy;
- nominate policies using DR-BGS and same-anchor guarded GP under five fixed initializations;
- evaluate every policy with 150 independent certification-pool replays;
- apply the unchanged absolute gate: protected blocking limit 2%, eligible blocking limit 5%, per-constraint violation-risk limit 10%, familywise alpha 5% with Bonferroni allocation.

Primary outputs:

- number of certifiable policy-scenario pairs among 2,280 exhaustive combinations;
- certified nominations for DR-BGS and guarded GP;
- minimum attainable blocking and exact risk bounds by scenario.

## Campaign B: separately locked low-load confirmation

Six scenarios cross:

- fixed capacity K = 40;
- fixed offered-load ratio rho = 0.05;
- protected fraction: 0.20, 0.50, and 0.80;
- activation delay: 0.5 and 2.0.

For every scenario:

- evaluate all 190 policies with 12 search-pool replications per policy;
- run DR-BGS and guarded GP under ten fixed initializations;
- include exhaustive-training selection;
- certify each distinct nominated policy using two disjoint batches of 1,200 certification-pool replays;
- require both batches to pass the unchanged absolute gate.

The method-level initialization labels are reported, but the principal interpretation is duplicate-aware at the unique scenario-policy level.

## Claim boundary

The study may establish robustness of the simulator-based findings to a much larger chronological workload basis. It cannot establish production safety, validate synthetic privacy labels, or convert bootstrap replays into independent observations of the real workload distribution. Exact binomial bounds remain conditional on independent draws from the declared replay generator.
