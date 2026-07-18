# V15 Seven-Day BurstGPT Robustness Results

## Trace basis

The fixed seven-day window contains 17,896 positive-token rows. The first five days provide 11,810 search rows and the later two days provide 6,086 certification rows. Privacy labels and replay construction remain synthetic.

## Original high-load regimes

Across all 190 policies and 12 scenarios, 0 of 2,280 policy-scenario combinations passed the unchanged 2%/5% absolute gate.

| scenario_id   |     rho |      qH |     tau |   policies |   certified_policies |   min_mean_B_H |   min_mean_B_L |   policy_idx |   alpha_on |   alpha_off |   mean_B_H |   mean_B_L |   upper_H |   upper_L |   max_mean_ratio |   max_upper |
|:--------------|--------:|--------:|--------:|-----------:|---------------------:|---------------:|---------------:|-------------:|-----------:|------------:|-----------:|-----------:|----------:|----------:|-----------------:|------------:|
| R15H01        | 0.70000 | 0.20000 | 0.50000 |        190 |                    0 |        0.05365 |        0.04153 |            2 |    4.00000 |     4.00000 |    0.05365 |    0.04295 |   0.85505 |   0.40793 |          2.68266 |     0.85505 |
| R15H02        | 0.70000 | 0.20000 | 2.00000 |        190 |                    0 |        0.13656 |        0.13029 |            0 |    2.00000 |     2.00000 |    0.13656 |    0.13029 |   0.99838 |   0.92731 |          6.82804 |     0.99838 |
| R15H03        | 0.70000 | 0.50000 | 0.50000 |        190 |                    0 |        0.08582 |        0.03013 |            0 |    2.00000 |     2.00000 |    0.08582 |    0.03013 |   0.94294 |   0.30928 |          4.29114 |     0.94294 |
| R15H04        | 0.70000 | 0.50000 | 2.00000 |        190 |                    0 |        0.15357 |        0.11188 |            0 |    2.00000 |     2.00000 |    0.15357 |    0.11308 |   0.99838 |   0.86653 |          7.67827 |     0.99838 |
| R15H05        | 0.70000 | 0.80000 | 0.50000 |        190 |                    0 |        0.19939 |        0.02222 |            0 |    2.00000 |     2.00000 |    0.19939 |    0.02222 |   1.00000 |   0.20601 |          9.96934 |     1.00000 |
| R15H06        | 0.70000 | 0.80000 | 2.00000 |        190 |                    0 |        0.23158 |        0.09163 |            4 |    6.00000 |     4.00000 |    0.23158 |    0.09190 |   1.00000 |   0.71044 |         11.57905 |     1.00000 |
| R15H07        | 0.90000 | 0.20000 | 0.50000 |        190 |                    0 |        0.07712 |        0.06154 |            2 |    4.00000 |     4.00000 |    0.07712 |    0.06154 |   0.92731 |   0.62803 |          3.85614 |     0.92731 |
| R15H08        | 0.90000 | 0.20000 | 2.00000 |        190 |                    0 |        0.19963 |        0.18846 |           10 |   10.00000 |     2.00000 |    0.19963 |    0.18918 |   1.00000 |   0.99586 |          9.98152 |     1.00000 |
| R15H09        | 0.90000 | 0.50000 | 0.50000 |        190 |                    0 |        0.13627 |        0.03811 |            0 |    2.00000 |     2.00000 |    0.13627 |    0.03957 |   0.99586 |   0.35907 |          6.81361 |     0.99586 |
| R15H10        | 0.90000 | 0.50000 | 2.00000 |        190 |                    0 |        0.20959 |        0.13012 |           28 |   16.00000 |     2.00000 |    0.20959 |    0.13041 |   1.00000 |   0.86653 |         10.47970 |     1.00000 |
| R15H11        | 0.90000 | 0.80000 | 0.50000 |        190 |                    0 |        0.30036 |        0.02111 |            0 |    2.00000 |     2.00000 |    0.30036 |    0.02111 |   1.00000 |   0.22865 |         15.01783 |     1.00000 |
| R15H12        | 0.90000 | 0.80000 | 2.00000 |        190 |                    0 |        0.32095 |        0.10689 |           10 |   10.00000 |     2.00000 |    0.32095 |    0.10689 |   1.00000 |   0.71667 |         16.04726 |     1.00000 |


Method nominations:

| method              |   run_labels |   certified_labels |   physical_scenarios |   unique_scenario_policy_pairs |
|:--------------------|-------------:|-------------------:|---------------------:|-------------------------------:|
| DR-BGS              |           60 |                  0 |                   12 |                             12 |
| Exhaustive-training |           12 |                  0 |                   12 |                             12 |
| Guarded-GP          |           60 |                  0 |                   12 |                             17 |


## Separately locked low-load confirmation

| method              |   run_labels |   confirmed_labels |   physical_scenarios |   unique_scenario_policy_pairs |   unique_pairs_confirmed |   max_upper_bound |
|:--------------------|-------------:|-------------------:|---------------------:|-------------------------------:|-------------------------:|------------------:|
| DR-BGS              |           60 |                 60 |                    6 |                              6 |                        6 |           0.00307 |
| Exhaustive-training |            6 |                  6 |                    6 |                              6 |                        6 |           0.00307 |
| Guarded-GP          |           60 |                 60 |                    6 |                             12 |                       12 |           0.00307 |


After cross-method deduplication, 18 of 18 distinct scenario-policy pairs passed both disjoint 1,200-replay batches. Batch-to-batch reversals: 0.

## Interpretation

This larger-slice replication tests robustness to a substantially broader chronological workload basis. Exact risk bounds remain conditional on the declared block-bootstrap generator and do not constitute live-system safety guarantees. The V11 compact-slice results remain reported as the original study rather than being replaced.
