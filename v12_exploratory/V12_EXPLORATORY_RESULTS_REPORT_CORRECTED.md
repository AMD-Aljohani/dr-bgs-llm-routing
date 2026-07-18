# V12 Exploratory Certification Frontier — Corrected Full Results

## Claim boundary

These analyses are exploratory. They do not replace the locked V11 result, alter its thresholds, or convert a changed operating regime into evidence for the original regime. The V11 absolute-SLO result remains 0/120 method runs certified.

## Run 1 — Exhaustive current-system feasibility

All 190 policies were evaluated in all 12 original later-pool scenarios with 150 independent replays per policy. Exactly 0 of the 2,280 policy-scenario combinations passed the original 2%/5% absolute gate. No original scenario contained a certifiable policy. This establishes that the V11 0/120 result was not caused merely by DR-BGS or guarded-GP selecting the wrong policy; the fixed 190-policy family contained no policy that the independent gate could certify under the original operating conditions.

| scenario_id   |    rho |     qH |    tau |   certifiable_policies |   min_mean_B_H |   min_mean_B_L |   min_upper_H |   min_upper_L |   policy_idx |   alpha_on |   alpha_off |   max_mean_ratio |   mean_B_H |   mean_B_L |
|:--------------|-------:|-------:|-------:|-----------------------:|---------------:|---------------:|--------------:|--------------:|-------------:|-----------:|------------:|-----------------:|-----------:|-----------:|
| BG01          | 0.7000 | 0.2000 | 0.5000 |                      0 |         0.1138 |         0.0981 |        0.9891 |        0.8779 |            0 |     2.0000 |      2.0000 |           5.6917 |     0.1138 |     0.0981 |
| BG02          | 0.7000 | 0.2000 | 2.0000 |                      0 |         0.1772 |         0.1698 |        0.9984 |        0.9852 |            0 |     2.0000 |      2.0000 |           8.8577 |     0.1772 |     0.1731 |
| BG03          | 0.7000 | 0.5000 | 0.5000 |                      0 |         0.1568 |         0.0792 |        0.9998 |        0.7659 |            0 |     2.0000 |      2.0000 |           7.8425 |     0.1568 |     0.0792 |
| BG04          | 0.7000 | 0.5000 | 2.0000 |                      0 |         0.2003 |         0.1511 |        1.0000 |        0.9530 |            0 |     2.0000 |      2.0000 |          10.0132 |     0.2003 |     0.1511 |
| BG05          | 0.7000 | 0.8000 | 0.5000 |                      0 |         0.2245 |         0.0812 |        1.0000 |        0.7537 |            0 |     2.0000 |      2.0000 |          11.2253 |     0.2245 |     0.0812 |
| BG06          | 0.7000 | 0.8000 | 2.0000 |                      0 |         0.2347 |         0.1446 |        1.0000 |        0.8947 |            0 |     2.0000 |      2.0000 |          11.7344 |     0.2347 |     0.1446 |
| BG07          | 0.9000 | 0.2000 | 0.5000 |                      0 |         0.1112 |         0.0954 |        0.9852 |        0.8608 |            0 |     2.0000 |      2.0000 |           5.5599 |     0.1112 |     0.0954 |
| BG08          | 0.9000 | 0.2000 | 2.0000 |                      0 |         0.2077 |         0.1979 |        0.9998 |        0.9959 |            2 |     4.0000 |      4.0000 |          10.3869 |     0.2077 |     0.1979 |
| BG09          | 0.9000 | 0.5000 | 0.5000 |                      0 |         0.1783 |         0.0805 |        1.0000 |        0.7042 |            0 |     2.0000 |      2.0000 |           8.9171 |     0.1783 |     0.0829 |
| BG10          | 0.9000 | 0.5000 | 2.0000 |                      0 |         0.2295 |         0.1686 |        1.0000 |        0.9326 |            0 |     2.0000 |      2.0000 |          11.4761 |     0.2295 |     0.1686 |
| BG11          | 0.9000 | 0.8000 | 0.5000 |                      0 |         0.2647 |         0.0599 |        1.0000 |        0.5695 |            0 |     2.0000 |      2.0000 |          13.2336 |     0.2647 |     0.0599 |
| BG12          | 0.9000 | 0.8000 | 2.0000 |                      0 |         0.2828 |         0.1446 |        1.0000 |        0.8551 |            0 |     2.0000 |      2.0000 |          14.1411 |     0.2828 |     0.1446 |

## Run 2 — Engineering operating envelope

The corrected exact refinement evaluated 549 operating configurations. At each configuration, all 190 policies received 150 independent later-pool replays. The sweep includes a fine load-only path, the complete K=[40.0, 60.0, 80.0, 100.0, 120.0, 160.0, 200.0, 240.0] capacity-only path at the original load, the complete activation-delay path, and coarse joint K-rho boundary points.

Highest load ratio certified on the load-only path for each original scenario:

| original_scenario_id   |   base_rho |     qH |    tau |    rho |   exact_certifiable_policies |   best_policy_upper |   best_policy_mean_B_H |   best_policy_mean_B_L |
|:-----------------------|-----------:|-------:|-------:|-------:|-----------------------------:|--------------------:|-----------------------:|-----------------------:|
| BG01                   |     0.7000 | 0.2000 | 0.5000 | 0.0750 |                            2 |              0.0938 |                 0.0032 |                 0.0028 |
| BG02                   |     0.7000 | 0.2000 | 2.0000 | 0.0500 |                          190 |              0.0243 |                 0.0004 |                 0.0005 |
| BG03                   |     0.7000 | 0.5000 | 0.5000 | 0.0750 |                          119 |              0.0573 |                 0.0028 |                 0.0022 |
| BG04                   |     0.7000 | 0.5000 | 2.0000 | 0.0500 |                          190 |              0.0243 |                 0.0005 |                 0.0002 |
| BG05                   |     0.7000 | 0.8000 | 0.5000 | 0.0500 |                          190 |              0.0243 |                 0.0003 |                 0.0005 |
| BG06                   |     0.7000 | 0.8000 | 2.0000 | 0.0500 |                          190 |              0.0243 |                 0.0004 |                 0.0004 |
| BG07                   |     0.9000 | 0.2000 | 0.5000 | 0.0750 |                            8 |              0.0669 |                 0.0023 |                 0.0019 |
| BG08                   |     0.9000 | 0.2000 | 2.0000 | 0.0500 |                          190 |              0.0243 |                 0.0003 |                 0.0006 |
| BG09                   |     0.9000 | 0.5000 | 0.5000 | 0.0750 |                           67 |              0.0573 |                 0.0031 |                 0.0026 |
| BG10                   |     0.9000 | 0.5000 | 2.0000 | 0.0500 |                          190 |              0.0243 |                 0.0004 |                 0.0004 |
| BG11                   |     0.9000 | 0.8000 | 0.5000 | 0.0500 |                          190 |              0.0243 |                 0.0005 |                 0.0001 |
| BG12                   |     0.9000 | 0.8000 | 2.0000 | 0.0750 |                            6 |              0.0850 |                 0.0056 |                 0.0052 |

Capacity-only certification occurred in 2 of 12 original scenarios for K up to 240. Delay-only certification occurred in 0 of 12 original scenarios over tau=[0.1, 0.25, 0.5, 1.0, 2.0].

Method nominations over the full refined configuration set:

| method              |   runs |   certified |   fraction |
|:--------------------|-------:|------------:|-----------:|
| DR-BGS              |   2745 |         135 |     0.0492 |
| Exhaustive-training |    549 |          28 |     0.0510 |
| Guarded-GP          |   2745 |         140 |     0.0510 |

## Run 3 — Evidence and stability frontier

Fresh 1,200-replay sequences were generated for baseline, the load-only boundary selected from the independent 150-replay exploration, one harder load point, and one safer load point. There were 5 cases in which a prefix certified but the full 1,200-replay audit did not. These are simulation-stability diagnostics, not estimates of real-world false assurance.

| regime               | method              |     50 |    150 |   1200 |
|:---------------------|:--------------------|-------:|-------:|-------:|
| baseline             | DR-BGS              | 0.0000 | 0.0000 | 0.0000 |
| baseline             | Exhaustive-training | 0.0000 | 0.0000 | 0.0000 |
| baseline             | Guarded-GP          | 0.0000 | 0.0000 | 0.0000 |
| baseline             | Risk-screen-oracle  | 0.0000 | 0.0000 | 0.0000 |
| boundary_candidate   | DR-BGS              | 0.5000 | 0.6667 | 0.9167 |
| boundary_candidate   | Exhaustive-training | 0.5000 | 0.7500 | 0.9167 |
| boundary_candidate   | Guarded-GP          | 0.5333 | 0.7167 | 0.9000 |
| boundary_candidate   | Risk-screen-oracle  | 0.5000 | 0.5833 | 0.9167 |
| interior_safer       | DR-BGS              | 1.0000 | 1.0000 | 1.0000 |
| interior_safer       | Exhaustive-training | 1.0000 | 1.0000 | 1.0000 |
| interior_safer       | Guarded-GP          | 0.9167 | 1.0000 | 1.0000 |
| interior_safer       | Risk-screen-oracle  | 0.9167 | 1.0000 | 1.0000 |
| near_boundary_harder | DR-BGS              | 0.0000 | 0.0000 | 0.0000 |
| near_boundary_harder | Exhaustive-training | 0.0000 | 0.0000 | 0.1667 |
| near_boundary_harder | Guarded-GP          | 0.0000 | 0.0000 | 0.0000 |
| near_boundary_harder | Risk-screen-oracle  | 0.0000 | 0.0000 | 0.0833 |

## Main interpretation

1. The original strict result is a system-and-policy-family infeasibility result under the declared later-pool generator, not simply a search failure.

2. Strict certification becomes possible only after a material operating-regime change. The exact load boundary is scenario-dependent and must be reported explicitly; it cannot be presented as success at the original 0.70/0.90 load ratios.

3. Increasing buffer capacity or shortening cloud activation alone may be insufficient. The tables quantify this rather than implying that more simulation evidence can repair an actually violated SLO.

4. DR-BGS and guarded GP should be judged as nomination methods. The absolute gate separately determines whether the nominated policy has enough independent evidence for the declared claim.