# Reproducibility

## Environment

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Reproduce the analytical validation

The commands run in dependency order:

```bash
python src/validation/validate_service_law.py
python src/validation/validate_cross_hardware_transport.py
python src/validation/validate_policy_surfaces.py
python src/validation/reproduce_optimizer_analysis.py
python src/validation/run_model_form_stress.py
python src/validation/run_solver_triangulation.py
```

All generated outputs are written to `results/analytical_validation/`.

## Compile the manuscript

A TeX Live installation with `latexmk` and `elsarticle` is required.

```bash
cd manuscript
latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary_material.tex
```

## Integrity verification

```bash
python tools/verify_repository.py
```

The verifier checks required files, hashes, Python syntax, expected dataset
dimensions, PDF presence, and the absence of development-version identifiers
in repository paths.

## Scope

The current branch reproduces the analytical validation and provides the
machine-readable policy surfaces used by it. The complete historical
simulation campaigns remain preserved in the immutable GitHub release and
Zenodo archive cited in `README.md`.
