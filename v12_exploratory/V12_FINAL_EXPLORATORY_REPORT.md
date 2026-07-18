# V12 Exploratory Certification Frontier — Final Corrected Report

## Status

All three planned exploratory campaigns completed. The source V11 repository was read from the uploaded release ZIP and was not edited. The V11 locked result remains unchanged: 0/120 strict absolute-SLO method runs certified. These V12 results are exploratory and cannot be presented as prospective or production certification.

## What was executed

- **Campaign 1:** 12 original later-pool scenarios × all 190 policies × 150 independent replays = **2,280 policy-scenario audits** and **342,000 policy replications**.
- **Campaign 2:** **549 scenario-configuration batches** (325 distinct physical parameter settings) × all 190 policies × 150 replays = **104,310 policy-configuration audits** and **15,646,500 policy replications**. The planned load-only, capacity-only, delay-only, and selected joint capacity/load boundary sweeps were covered.
- **Campaign 3:** 48 regime cases, 12 nomination records per case, and evidence prefixes at 50, 100, 150, 300, 600, and 1,200 replays, producing **3,456 certification decisions** from fresh 1,200-replay streams.

All automated structural and certification-logic checks in `V12_EXECUTION_AUDIT.json` passed.

## Campaign 1 — Original regime

**No policy passed.** None of the 2,280 policy-scenario combinations was certified under the original 2% protected-blocking, 5% eligible-blocking, and 10% violation-risk gate. No policy even met both limits in its sample mean.

The jointly least-bad policies still had protected blocking of **11.12%–28.28%** and eligible blocking of **5.99%–19.79%** across the 12 scenarios. Thus, the original 0/120 result is not explained merely by DR-BGS or guarded GP choosing the wrong policy. In this finite exhaustive simulation audit, the whole 190-policy family failed the declared strict gate at the original operating points.

Relaxing the SLO enough to produce certification at the original operating point would change the claim radically. On the tested threshold grid, the first balanced certifiable pairs were generally **25%–35% protected blocking and 20%–35% eligible blocking**; BG12 still had no certifiable policy through 35%/35%. That is not a credible reinterpretation of the original 2%/5% target.

## Campaign 2 — What operational changes produce strict certificates?

Strict certification became possible only after a material regime change.

### Load-only path, K = 40

The highest certified load ratio was **0.05 or 0.075**, depending on scenario. Relative to the original 0.70/0.90 loads, this is an **89.29%–94.44% reduction in offered load**. No load-only case certified at rho >= 0.10.

### Capacity-only path, original load

Only 2 of 12 scenarios certified with capacity increases up to K = 240:

- BG01: first certification at **K = 200**, five times the original capacity.
- BG03: first certification at **K = 240**, six times the original capacity.

The other ten scenarios remained uncertified through K = 240.

### Activation-delay-only path

Reducing activation delay from the original values down to 0.10 produced **no certified scenario** at the original capacity and load. Faster activation alone does not repair the strict-SLO failure in this model.

### Joint capacity/load diagnostics

Selected exact boundary points show that capacity and load can trade off. Examples include BG07 at K = 240 and rho = 0.80, BG06 at K = 100 and rho = 0.15, and BG11 at K = 60 and rho = 0.10. These are exploratory boundary examples, not a complete exact four-dimensional operating map.

Across the 549 scenario-configuration batches, 38 contained at least one certifiable policy (24 distinct physical settings). Conditional on such a policy existing, the nomination outcomes were:

| method              |   method_runs |   certified_runs |   conditional_certified_fraction |   all_runs |   all_certified |   all_config_fraction |
|:--------------------|--------------:|-----------------:|---------------------------------:|-----------:|----------------:|----------------------:|
| DR-BGS              |           190 |              135 |                           0.7105 |       2745 |             135 |                0.0492 |
| Exhaustive-training |            38 |               28 |                           0.7368 |        549 |              28 |                0.0510 |
| Guarded-GP          |           190 |              140 |                           0.7368 |       2745 |             140 |                0.0510 |

DR-BGS did not outperform the guarded GP in this exploratory frontier. Its useful role remains budgeted nomination with a separate independent gate, not superior absolute-risk selection in every shifted regime.

## Campaign 3 — Evidence volume and stability

At the original baseline, increasing certification evidence from 50 to 1,200 replays yielded **zero certifications for every method**. More evidence cannot repair an operating regime that violates the SLO.

At the independently selected load boundary, the fresh 1,200-replay audit certified:

- DR-BGS: **55/60 (91.67%)**
- Guarded GP: **54/60 (90.00%)**
- Exhaustive-training selection: **11/12 (91.67%)**
- Risk-screen oracle diagnostic: **11/12 (91.67%)**

At one safer load step, DR-BGS, guarded GP, and exhaustive-training selection all certified every run at 1,200 replays. At one harder load step, DR-BGS and guarded GP certified 0/60; exhaustive-training selection certified 2/12.

The raw table contains five prefix-to-final reversals, but all five correspond to the **same BG11 scenario, same selected policy, and same replay stream**, repeated because all five DR-BGS initialization labels selected that policy. Scientifically, this is one unique scenario-policy instability, not five independent failures.

The evidence frontier therefore supports a clear distinction:

1. **Baseline failure is operational**, not a shortage of simulation replications.
2. **Near a genuine feasibility boundary, 150 replays can be underpowered**, and larger independent batches materially stabilize certification.
3. **A safer interior point certifies consistently**, but only after the operating regime has been changed.

## Defensible paper position

The strongest honest result is not “the strict gate became positive.” It is:

> Exhaustive auditing showed that universal V11 abstention was caused by the declared operating regime and policy family, not merely by search error. A separately labeled exploratory operating-envelope study then identified where the same 2%/5% gate becomes statistically certifiable. Certification required major load reduction, very large capacity increases in a few cases, or joint capacity/load changes; additional evidence alone did not rescue the original regime.

This is a useful systems result because it converts an unexplained negative certificate into a diagnosis of **operational infeasibility, nomination error, and evidence limitation**. It must remain separate from the locked V11 claims until one operating point is selected, frozen, and evaluated with a new confirmatory seed batch.
