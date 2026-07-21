# Evidence-Gated Cloud-Edge LLM Serving

Reproducibility repository for:

**Evidence-Gated Cloud-Edge LLM Serving with Delayed Activation**

The repository presents one current, purpose-based layout. Development-stage
directories and filenames are not duplicated on the default branch. Earlier
immutable research snapshots remain available through Git tags and the Zenodo
record.

## Main findings

- DR-BGS evaluates 20 of 190 policies, reducing high-fidelity replication work
  by 88.77%.
- All 180 synthetic benchmark selections remain within 1% of exhaustive
  training selection; the maximum holdout excess is 0.348%.
- At the original trace-derived loads, no policy among 2,280 policy-scenario
  pairs satisfies the declared certification rule.
- A separately fixed low-load point passes two independent 1,200-replay
  confirmation batches.
- Retrospective analytical validation independently reproduces the optimizer
  result and strengthens numerical and service-law model-form credibility.
- End-to-end production validation is not claimed.

## Repository map

| Path | Purpose |
|---|---|
| `manuscript/` | Current manuscript, supplement, and publication figures |
| `src/validation/` | Reproducible analytical and numerical validation code |
| `data/synthetic/` | Exhaustive policy surfaces and scenario definitions |
| `data/calibration/` | Existing GPU/model calibration summaries |
| `results/analytical_validation/` | Machine-readable validation outputs |
| `protocols/` | Retrospective validation protocol |
| `validation/` | Human-readable report and supporting figures |
| `audit/` | Checksums, file manifest, and clean-package audit |
| `docs/` | Reproduction, release, and archive documentation |
| `tools/` | Repository verification utilities |

## Quick verification

```bash
python -m pip install -r requirements.txt
python tools/verify_repository.py
```

To rebuild the publication PDFs:

```bash
make manuscript
```

To reproduce the analytical validation results from the archived inputs:

```bash
make validation
```

## Historical research archive

The public release and Zenodo archive preserve the full earlier experiment
history, including the simulator, trace campaigns, protocol locks, and
integrity audits:

- GitHub repository: https://github.com/AMD-Aljohani/dr-bgs-llm-routing
- Archived release: https://github.com/AMD-Aljohani/dr-bgs-llm-routing/releases/tag/v1.1.0
- Zenodo version DOI: https://doi.org/10.5281/zenodo.21434924
- Calibration archive: https://doi.org/10.5281/zenodo.21194313

The default branch is intentionally clean; Git tags and Zenodo provide the
immutable development history.

## Claim boundary

The evidence is conditional on the declared simulator, policy family, trace
transformation, and replay model. The repository does not claim production
safety, hardware-in-the-loop control, or end-to-end real-system validation.

## License

Code is released under the MIT License. Data and generated research artifacts
are released under Creative Commons Attribution 4.0 International.
