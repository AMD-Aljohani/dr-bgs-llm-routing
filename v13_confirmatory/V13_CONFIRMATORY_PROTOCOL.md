# V13 Fresh-Seed Confirmatory Protocol

## Locked question

At a single operating point selected from the completed V12 exploratory frontier, does the unchanged absolute-risk gate issue stable certificates for DR-BGS nominations on two independent fresh-seed certification batches?

## Operating point

- Local pressure capacity: K = 40.
- Offered-load ratio: rho = 0.05.
- Six physical scenarios: qH in {0.20, 0.50, 0.80} crossed with activation delay tau in {0.50, 2.00}.

This is a common low-load interior point selected before confirmatory result generation. It is not the original V11 rho = 0.70/0.90 regime.

## Search and comparators

- DR-BGS: 10 fixed fresh search initializations per physical scenario.
- Same-anchor guarded GP: 10 identical initialization labels per physical scenario.
- Exhaustive-training selection: one reference nomination per physical scenario.
- Training budget: 12 replications per evaluated policy.
- Budgeted methods evaluate 20 of 190 policies.

## Strict certification

The original limits are unchanged:

- Protected-request blocking limit: 2%.
- Eligible-request blocking limit: 5%.
- Maximum violation risk: 10%.
- Bonferroni familywise alpha: 5%.

Each nomination receives two disjoint fresh-seed batches, A and B, each containing 1,200 independent simulator replays from the later chronological trace pool. A run is `confirmed certified` only when both batches independently pass the exact gate.

## Primary success rule

DR-BGS must achieve at least 54 confirmed certifications among 60 method–scenario–initialization runs. The observed proportion and its one-sided exact 95% lower confidence bound will be reported.

The guarded GP and exhaustive-training selection are prespecified comparators. No superiority claim between DR-BGS and the guarded GP is a primary hypothesis.

## Duplicate-aware reporting

Method-run counts and unique scenario-policy counts will both be reported because different search initializations may nominate the same policy. Repeated labels that map to one scenario-policy pair are not treated as independent physical validations.

## Claim boundary

A positive result would confirm only that the unchanged gate works in this separately locked low-load simulation regime. It would not repair the original V11 0/120 result, establish certification at the original loads, validate the full BurstGPT corpus, or establish production safety.
