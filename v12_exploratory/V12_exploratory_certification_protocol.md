# V12 Exploratory Certification Frontier Protocol

## Purpose

This protocol is an exploratory extension of V11. It does not replace or reinterpret the locked V11 strict result. The original result remains: under the original pressure mapping, capacity, trace replay, protected-request blocking limit of 2%, eligible-request blocking limit of 5%, and 10% violation-risk budget, the absolute gate certified 0 of 120 method runs.

The objective is to determine why certification failed, where certification becomes feasible, and how much independent evidence is required once the underlying system is actually capable of meeting the limits.

## Non-negotiable reporting rules

1. Preserve the complete V11 strict result unchanged.
2. Label all three campaigns below as exploratory.
3. Report every tested configuration, including failures and universal-abstention regions.
4. Do not select thresholds or operating points by looking only at DR-BGS.
5. Distinguish:
   - physical/operational feasibility;
   - optimizer nomination quality;
   - statistical certification power.
6. Any later confirmatory claim must use a separately locked configuration and fresh simulation seeds.

---

## Campaign 1 — Current-System Feasibility and SLO Frontier

### Question

At the original V11 operating conditions, is any policy in the full 190-policy set capable of meeting the strict blocking limits on the later chronological pool?

### Design

- Scenarios: BG01–BG12.
- Policies: all 190 admissible threshold pairs.
- Trace source: original later chronological certification pool.
- High-fidelity simulator: unchanged.
- Primary replay count: the V11 certification count.
- Additional precision run: increase replay count for policies close to the feasibility boundary.
- Methods:
  - exhaustive policy map;
  - V11 DR-BGS nomination;
  - V11 guarded-GP nomination;
  - exhaustive training-selected policy.

### SLO frontier

Evaluate a declared grid of blocking limits:

- Protected-request limit: 2%, 5%, 10%, 15%, 20%, 25%, 30%, 35%.
- Eligible-request limit: 5%, 10%, 15%, 20%, 25%, 30%, 35%.

Keep the violation-risk budget and multiplicity correction unchanged.

### Outputs

- Number and fraction of feasible policies per scenario.
- Minimum attainable protected and eligible blocking.
- Pareto frontier among blocking, cloud use, waiting cost, and total operational cost.
- Certification count for each method at every SLO pair.
- Minimal SLO pair that can be certified in each scenario.
- Cases where a feasible policy exists but a search method nominates an infeasible policy.
- Cases where no policy in the 190-policy family is feasible.

### Interpretation

This campaign separates optimizer failure from policy-family or system infeasibility. Relaxed limits are diagnostic operating-envelope results, not retrospective replacements for the original 2%/5% limits.

---

## Campaign 2 — Engineering Operating Envelope Under the Original Strict SLO

### Question

What operational changes make the original 2% protected and 5% eligible blocking limits feasible?

### Fixed quantities

- Blocking limits: 2% and 5%.
- Violation-risk budget: 10%.
- Familywise confidence construction: unchanged.
- Trace replay and privacy-label mechanism: unchanged unless explicitly identified as a separate sensitivity factor.

### Coarse relative sweeps

Use baseline-relative multipliers, subject to the exact parameter names and admissible ranges in the V11 code:

- Local capacity multiplier: 1.00, 1.25, 1.50, 1.75, 2.00.
- Offered-load multiplier: 1.00, 0.90, 0.80, 0.70, 0.60.
- Cloud-activation-delay multiplier: 1.00, 0.75, 0.50, 0.25.

Run one-factor-at-a-time sweeps first. Then run a limited joint design around the first feasible region. Refine the transition boundary rather than exhaustively testing the full Cartesian product.

### Methods

- Exhaustive 190-policy oracle for diagnostic feasibility.
- DR-BGS with the original 20-policy budget.
- Same-anchor guarded GP with the original 20-policy budget.

### Outputs

- Strict-certification probability by operating point.
- Feasible-policy count by scenario.
- Required capacity increase, load reduction, or activation-delay reduction.
- Cost and cloud-use consequences of obtaining certification.
- Search regret relative to the exhaustive training-selected policy.
- Cases where strict feasibility exists but the search misses it.
- Cases where no feasible policy exists even after moderate engineering changes.

### Interpretation

This campaign identifies whether strict certification requires more capacity, lower load, faster cloud readiness, or a richer routing/action model. It does not call a changed system equivalent to the original one.

---

## Campaign 3 — Certification Evidence and Stability Frontier

### Question

Once an operating point is physically feasible, how much independent simulation evidence is required for stable certification?

### Operating points

Evaluate:

1. The original V11 operating point.
2. The first feasible point found in Campaign 2.
3. One interior feasible point with margin from the feasibility boundary.
4. One near-boundary point.

### Certification replay counts

- 50
- 100
- 150
- 300
- 600
- 1,200

Keep the 2%/5% limits, 10% violation-risk budget, and familywise confidence level fixed.

### Methods

- DR-BGS nomination.
- Guarded-GP nomination.
- Exhaustive training-selected policy.
- Best feasible policy from the exhaustive diagnostic map, labeled as an oracle diagnostic only.

### Outputs

- Certified and abstained counts.
- Exact upper risk bounds.
- False-certification frequency under larger independent evaluation batches.
- Stability of the certification decision as replay count increases.
- Replication cost and work reduction.
- Difference between lack of evidence and genuine SLO violation.
- Method comparison at identical evidence budgets.

### Confirmatory stage

After the three exploratory campaigns:

1. Select one scientifically meaningful operating point and one certification replay count.
2. Freeze the complete configuration, seeds, analysis code, and success criteria.
3. Create a SHA-256 lock manifest before result generation.
4. Run a fresh confirmatory batch.
5. Report all outcomes, including abstentions and failures.

---

## Required final figures and tables

1. Heatmap: certifiable SLO region at the original operating point.
2. Heatmap or contour: strict 2%/5% feasibility over capacity, load, and activation delay.
3. Curve: certification probability versus replay count.
4. Table: exhaustive feasibility versus DR-BGS and guarded-GP nomination.
5. Table: engineering cost of moving from the original regime to a certifiable regime.
6. Failure taxonomy:
   - no feasible policy;
   - feasible policy missed by search;
   - feasible nomination but insufficient evidence;
   - certified nomination;
   - false certification under extended audit.

## Claim boundary

The exploratory results may establish a certification frontier and diagnose the source of abstention. They may not erase the locked V11 result, claim production safety, or present an operating point selected after exploration as independently confirmatory.
