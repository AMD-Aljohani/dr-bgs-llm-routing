# Results Map

## Primary synthetic selection result

Source data:

- `data/synthetic/policy_surfaces.csv`
- `data/synthetic/scenario_definitions.csv`

Reanalysis outputs:

- `results/analytical_validation/optimizer_reanalysis_runs.csv`
- `results/analytical_validation/optimizer_reanalysis_summary.csv`
- `results/analytical_validation/policy_surface_validation.csv`
- `results/analytical_validation/surface_validation_summary.json`

## Service-law validation

Inputs:

- `data/calibration/qwen_rtx3090_direct_telemetry.csv`
- `data/calibration/qwen_rtx3090_independent_summary.csv`
- `data/calibration/qwen_rtx4090_summary.csv`
- `data/calibration/mistral_rtx3090_summary.csv`

Outputs:

- `results/analytical_validation/service_law_model_comparison.csv`
- `results/analytical_validation/service_law_validation_summary.json`
- `results/analytical_validation/cross_hardware_model_fits.csv`
- `results/analytical_validation/cross_hardware_validation_summary.json`

## Approximation and solver checks

- `results/analytical_validation/jump_error_indicators.csv`
- `results/analytical_validation/indicator_correlations.csv`
- `results/analytical_validation/model_form_stress_summary.csv`
- `results/analytical_validation/solver_triangulation.csv`
- `results/analytical_validation/solver_triangulation_summary.json`

The complete trace-risk, operating-envelope, and seven-day campaign history is
preserved in the immutable public release and Zenodo archive.
