.PHONY: verify manuscript validation clean

verify:
	python tools/verify_repository.py

manuscript:
	cd manuscript && latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex
	cd manuscript && latexmk -pdf -interaction=nonstopmode -halt-on-error supplementary_material.tex

validation:
	python src/validation/validate_service_law.py
	python src/validation/validate_cross_hardware_transport.py
	python src/validation/validate_policy_surfaces.py
	python src/validation/reproduce_optimizer_analysis.py
	python src/validation/run_model_form_stress.py
	python src/validation/run_solver_triangulation.py

clean:
	cd manuscript && latexmk -C manuscript.tex
	cd manuscript && latexmk -C supplementary_material.tex
