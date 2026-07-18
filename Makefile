.PHONY: audit audit-v15 audit-v14 trace followup figures calibration syntax locks compile report clean

ifeq ($(OS),Windows_NT)
THREAD_ENV = set OMP_NUM_THREADS=1&& set OPENBLAS_NUM_THREADS=1&& set MKL_NUM_THREADS=1&& set NUMEXPR_NUM_THREADS=1&&
else
THREAD_ENV = OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
endif

audit: audit-v15

audit-v15:
	$(THREAD_ENV) python audit_v15/run_final_audit_v15.py

verify-v15:
	$(THREAD_ENV) python audit_v15/run_final_audit_v15.py --verify-only

checksums:
	$(THREAD_ENV) python scripts/generate_sha256sums.py

.PHONY: audit-v14
audit-v14:
	@echo "ERROR: audit-v14 is deprecated and no longer supported; use 'make audit-v15'." >&2
	@exit 2

trace:
	$(THREAD_ENV) python v11_code/run_trace_risk_study.py

followup:
	$(THREAD_ENV) python v11_code/run_trace_noninferiority_followup.py

figures:
	python v11_code/make_v11_figures.py

calibration:
	python calibration/analyze_calibration.py

syntax:
	PYTHONPYCACHEPREFIX=/tmp/drbgs_pycache python -m compileall -q code v7_code v8_code v9_code v9b_code v11_code calibration audit_v11 audit_v14 audit_v15 v12_exploratory v13_confirmatory v15_seven_day_robustness


locks:
	python audit_v11/verify_lock_manifests.py

compile:
	cd manuscript && pdflatex -interaction=nonstopmode -halt-on-error FutureInternet_manuscript_submission_v15.tex && pdflatex -interaction=nonstopmode -halt-on-error FutureInternet_manuscript_submission_v15.tex
	cd manuscript && pdflatex -interaction=nonstopmode -halt-on-error FutureInternet_cover_letter_v15.tex

report:
	$(THREAD_ENV) python audit_v11/run_final_audit_v11.py
	$(THREAD_ENV) python audit_v15/run_final_audit_v15.py

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache .coverage trace_data/__pycache__ code/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find manuscript audit_v11 audit_v15 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.spl' -o -name '*.toc' -o -name '*.fdb_latexmk' -o -name '*.fls' -o -name '*.synctex.gz' \) -delete
