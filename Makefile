.PHONY: audit audit-v15 audit-v14 trace followup figures calibration syntax locks compile report clean

THREAD_ENV=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

audit: audit-v15

audit-v15:
	$(THREAD_ENV) python audit_v15/run_final_audit_v15.py

audit-v14:
	$(THREAD_ENV) python audit_v14/run_final_audit_v14.py

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
	cd audit_v15 && pdflatex -interaction=nonstopmode -halt-on-error FINAL_AUDIT_REPORT_V15.tex && pdflatex -interaction=nonstopmode -halt-on-error FINAL_AUDIT_REPORT_V15.tex

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find manuscript audit_v11 audit_v14 audit_v15 -type f \( -name '*.aux' -o -name '*.log' -o -name '*.out' -o -name '*.spl' -o -name '*.toc' -o -name '*.fdb_latexmk' -o -name '*.fls' -o -name '*.synctex.gz' \) -delete
