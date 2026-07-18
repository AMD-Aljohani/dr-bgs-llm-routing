# Empirical calibration

The direct-telemetry data summarize three complete vLLM concurrency sweeps for Qwen2.5-7B-Instruct on an RTX 3090. The analysis compares four two-parameter monotone service laws and applies a 20,000-draw measurement-error/residual bootstrap.

The bootstrap uses the reported across-sweep standard deviations divided by `sqrt(3)` to perturb the observed means, then resamples centered fit residuals. The fixed random seed is `20260717`.

Run:

```bash
python analyze_calibration.py
```

The normalized service sensitivity rescales only the observed KV-telemetry interval, 0-36.53%, to the model pressure interval `[0,1]`. It is parameter provenance, not a claim that this telemetry endpoint is universal physical capacity.
