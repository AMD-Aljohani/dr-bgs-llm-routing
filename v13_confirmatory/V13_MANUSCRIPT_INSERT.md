# Manuscript Insert for the V12/V13 Extension

## Suggested subsection title

### Operating-envelope diagnosis and separately locked low-load confirmation

## Suggested Results text

The exhaustive operating-envelope analysis showed that the original absolute-SLO abstention was not merely a policy-selection failure. At the original load ratios, none of the 2,280 policy-scenario combinations passed the 2% protected-blocking and 5% eligible-blocking gate. Increasing the certification sample to 1,200 replays did not alter that conclusion. Certification became possible only after material regime changes, most consistently through substantial load reduction.

We therefore selected one common interior point from the completed exploratory frontier, fixed it before new result generation, and conducted a fresh-seed confirmation at K=40 and rho=0.05. Six physical scenarios crossed protected fractions of 0.20, 0.50, and 0.80 with activation delays of 0.5 and 2.0. Every nominated policy was tested on two disjoint batches of 1,200 later-pool replays using the unchanged exact gate. DR-BGS produced 60/60 confirmed initialization labels, corresponding to six unique scenario-policy pairs because all ten initializations within each scenario nominated the same policy. All six unique DR-BGS pairs passed both batches. The guarded GP also passed for all twenty unique nominated pairs, and exhaustive-training selection passed for all six scenario-policy pairs.

This confirmation establishes that the gate can issue stable positive certificates in an interior feasible regime. It does not alter the original universal abstention, imply superiority over the guarded GP, or establish production safety. The confirmed point requires a large reduction from the original offered-load ratios and is therefore an operating-envelope diagnostic rather than a deployment recommendation.

## Suggested compact abstract sentence

A separately locked fresh-seed confirmation at an interior low-load point certified all six unique DR-BGS scenario-policy pairs in two disjoint 1,200-replay batches, while the original high-load regimes remained universally uncertifiable.
