# V13 Fresh-Seed Confirmatory Absolute-Risk Study

**Status:** PASS under the locked primary rule.

## Locked design

The operating point was fixed before result generation at K=40.0 and rho=0.05. The six physical scenarios cross qH=[0.2, 0.5, 0.8] and tau=[0.5, 2.0]. DR-BGS and the same-anchor guarded GP each use 10 fixed fresh search initializations per scenario. Each nomination is tested on two disjoint batches of 1200 and 1200 later-pool replays. A run is counted as confirmed only when both batches independently pass the unchanged 2% protected-blocking, 5% eligible-blocking, and 10% violation-risk gate.

The point was selected from the V12 exploratory frontier because it was an interior low-load regime across all six qH/tau combinations. It is not the original V11 operating regime and does not repair or replace the original 0/120 result.

## Primary outcome

The locked primary rule required at least 54 of 60 DR-BGS runs to certify in both independent batches. Observed: **60/60 (100.00%)**, with a one-sided exact 95% lower confidence bound of 95.13%.

## Method results

| method              |   runs |   batch_A_certified |   batch_B_certified |   confirmed_certified |   unique_scenario_policy_pairs |   median_A_upper_H |   median_A_upper_L |   median_B_upper_H |   median_B_upper_L |   confirmed_fraction |   exact_95pct_lower_bound |
|:--------------------|-------:|--------------------:|--------------------:|----------------------:|-------------------------------:|-------------------:|-------------------:|-------------------:|-------------------:|---------------------:|--------------------------:|
| DR-BGS              |     60 |                  60 |                  60 |                    60 |                              2 |             0.0066 |             0.0031 |             0.0046 |             0.0031 |               1.0000 |                    0.9513 |
| Exhaustive-training |      6 |                   6 |                   6 |                     6 |                              3 |             0.0053 |             0.0031 |             0.0046 |             0.0031 |               1.0000 |                    0.6070 |
| Guarded-GP          |     60 |                  60 |                  60 |                    60 |                             10 |             0.0066 |             0.0031 |             0.0060 |             0.0031 |               1.0000 |                    0.9513 |

## Scenario results

| scenario_id   |     qH |    tau | method              |   runs |   confirmed_certified |   distinct_selected_policies |   max_A_upper |   max_B_upper |   confirmed_fraction |
|:--------------|-------:|-------:|:--------------------|-------:|----------------------:|-----------------------------:|--------------:|--------------:|---------------------:|
| C01           | 0.2000 | 0.5000 | DR-BGS              |     10 |                    10 |                            1 |        0.0085 |        0.0031 |               1.0000 |
| C01           | 0.2000 | 0.5000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0046 |        0.0031 |               1.0000 |
| C01           | 0.2000 | 0.5000 | Guarded-GP          |     10 |                    10 |                            4 |        0.0085 |        0.0046 |               1.0000 |
| C02           | 0.2000 | 2.0000 | DR-BGS              |     10 |                    10 |                            1 |        0.0120 |        0.0109 |               1.0000 |
| C02           | 0.2000 | 2.0000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0120 |        0.0131 |               1.0000 |
| C02           | 0.2000 | 2.0000 | Guarded-GP          |     10 |                    10 |                            3 |        0.0142 |        0.0131 |               1.0000 |
| C03           | 0.5000 | 0.5000 | DR-BGS              |     10 |                    10 |                            1 |        0.0046 |        0.0060 |               1.0000 |
| C03           | 0.5000 | 0.5000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0046 |        0.0060 |               1.0000 |
| C03           | 0.5000 | 0.5000 | Guarded-GP          |     10 |                    10 |                            5 |        0.0046 |        0.0085 |               1.0000 |
| C04           | 0.5000 | 2.0000 | DR-BGS              |     10 |                    10 |                            1 |        0.0031 |        0.0046 |               1.0000 |
| C04           | 0.5000 | 2.0000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0060 |        0.0046 |               1.0000 |
| C04           | 0.5000 | 2.0000 | Guarded-GP          |     10 |                    10 |                            4 |        0.0060 |        0.0060 |               1.0000 |
| C05           | 0.8000 | 0.5000 | DR-BGS              |     10 |                    10 |                            1 |        0.0031 |        0.0031 |               1.0000 |
| C05           | 0.8000 | 0.5000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0031 |        0.0031 |               1.0000 |
| C05           | 0.8000 | 0.5000 | Guarded-GP          |     10 |                    10 |                            2 |        0.0031 |        0.0031 |               1.0000 |
| C06           | 0.8000 | 2.0000 | DR-BGS              |     10 |                    10 |                            1 |        0.0097 |        0.0046 |               1.0000 |
| C06           | 0.8000 | 2.0000 | Exhaustive-training |      1 |                     1 |                            1 |        0.0097 |        0.0046 |               1.0000 |
| C06           | 0.8000 | 2.0000 | Guarded-GP          |     10 |                    10 |                            2 |        0.0109 |        0.0073 |               1.0000 |

## Duplicate-aware audit

The 126 run labels map to 31 unique scenario-policy pairs. Of those unique pairs, 31 passed both independent batches. Batch-A-only failures: 0; batch-B-only failures: 0.

## Interpretation boundary

This confirms that the unchanged absolute-risk gate can issue stable certificates in a separately locked, low-load operating regime. It does not show that the original rho=0.70/0.90 regimes are certifiable, and it does not establish live production safety. The trace slice, privacy-label synthesis, pressure conversion, and moving-block replay limitations remain unchanged.
