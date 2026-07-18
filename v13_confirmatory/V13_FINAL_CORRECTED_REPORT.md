# V13 Fresh-Seed Confirmatory Study — Final Duplicate-Aware Report

## Status

The locked operational success rule passed: DR-BGS produced **60/60 confirmed run labels**, exceeding the prespecified minimum of 54/60. Every label passed the unchanged absolute-risk gate in **both disjoint 1,200-replay batches**.

A necessary qualification is that the 60 labels are not 60 independent physical validations. Within each of the six fixed physical scenarios, all ten DR-BGS initialization labels selected the same policy and used common certification streams. The DR-BGS result therefore represents **6/6 unique scenario-policy pairs**, not 60 independent scenario-policy experiments. The earlier nominal 95.13% binomial lower bound over 60 labels is not used in the final interpretation.

## Locked design

- Operating point: **K = 40, rho = 0.05**.
- Physical scenarios: qH in {0.20, 0.50, 0.80} crossed with activation delay tau in {0.50, 2.00}.
- DR-BGS and guarded GP: ten fresh search initialization labels per scenario.
- Strict limits unchanged: protected blocking 2%, eligible blocking 5%, violation-risk budget 10%, familywise alpha 5%.
- Confirmation: two disjoint batches of 1,200 later-pool simulator replays; both batches must certify.

The point was selected from the completed V12 exploration before confirmatory result generation. It is an interior **low-load** regime, not the original V11 operating regime.

## Duplicate-aware results

| method              |   run_labels |   run_labels_confirmed |   physical_scenarios |   unique_scenario_policy_pairs |   unique_pairs_confirmed |   batch_A_failures_unique |   batch_B_failures_unique |   max_upper_bound_A |   max_upper_bound_B |   max_mean_B_H_A |   max_mean_B_H_B |   max_mean_B_L_A |   max_mean_B_L_B |
|:--------------------|-------------:|-----------------------:|---------------------:|-------------------------------:|-------------------------:|--------------------------:|--------------------------:|--------------------:|--------------------:|-----------------:|-----------------:|-----------------:|-----------------:|
| DR-BGS              |           60 |                     60 |                    6 |                              6 |                        6 |                         0 |                         0 |             0.01198 |             0.01085 |          0.00054 |          0.00050 |          0.00045 |          0.00039 |
| Exhaustive-training |            6 |                      6 |                    6 |                              6 |                        6 |                         0 |                         0 |             0.01198 |             0.01309 |          0.00054 |          0.00050 |          0.00045 |          0.00035 |
| Guarded-GP          |           60 |                     60 |                    6 |                             20 |                       20 |                         0 |                         0 |             0.01419 |             0.01309 |          0.00055 |          0.00054 |          0.00051 |          0.00045 |

Across methods, the 126 run labels map to 31 unique scenario-policy pairs. All **31/31 unique pairs** passed both independent batches. No unique pair passed one batch and failed the other.

## What the result establishes

The unchanged absolute-risk gate is not structurally incapable of producing a positive result. Under a separately locked low-load regime, it issued stable certificates in two independent simulator batches for every nominated unique policy tested.

The result also confirms that the prior universal abstention was regime-dependent. At rho = 0.05, both DR-BGS and the guarded GP certified every nomination, as did exhaustive-training selection.

## What it does not establish

1. It does not repair or replace the original **0/120** outcome at rho = 0.70/0.90.
2. It does not show that rho = 0.05 is an attractive production operating point; it represents roughly a 92.9%–94.4% load reduction from the original regimes.
3. It does not show DR-BGS superiority over the guarded GP; both certified completely here.
4. It does not establish population-wide reliability from 60 independent trials. The physical scenario coverage is six fixed qH/tau combinations.
5. It does not establish live production safety. The compact trace slice, synthetic privacy labels, pressure conversion, and moving-block replay remain limitations.

## Seed-lock amendment

The first execution attempt stopped before producing any results because the initial seed integers exceeded NumPy's allowed legacy seed range. Only seed values were corrected. The scientific configuration, success rule, methods, thresholds, and operating point were unchanged, and the amended lock was generated before the successful run. The original failed log and invalid-seed lock are retained.

## Manuscript-level conclusion

A defensible statement is:

> A separately locked fresh-seed confirmation evaluated an interior low-load regime identified by the exploratory operating-envelope analysis. Under the unchanged 2%/5% absolute blocking limits, all six unique DR-BGS scenario-policy pairs passed two disjoint 1,200-replay certification batches; the same was true for all twenty guarded-GP and six exhaustive-training pairs. This confirms that the gate can issue stable positive certificates when the system is operated well inside the feasible region. It does not change the universal abstention observed at the original load levels, and the low-load confirmation should be interpreted as an operating-envelope result rather than evidence of deployability at the original regime.
