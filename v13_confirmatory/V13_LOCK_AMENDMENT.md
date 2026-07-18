# V13 Pre-Result Lock Amendment

The first execution attempt terminated before any scenario completed and before any result CSV or key-result file was created. The simulator rejected the locked integer seeds because several exceeded NumPy's permitted legacy seed range of 0 to 2^32-1.

Only the numeric seed bases were replaced with valid, nonoverlapping values. The operating point, scenario set, methods, search budget, certification batches, thresholds, primary success rule, and claim boundary are unchanged.

The failed execution log and original invalid-seed lock are retained. A new pre-result lock was generated before rerunning the study.
