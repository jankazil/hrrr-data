.PHONY: fmt lint test check clean setup-dev-env upload-anaconda
#.PHONY: fmt lint type test check clean setup-dev-env upload-anaconda

fmt:
	python -m ruff format

lint:
	python -m ruff check --fix

type:
	python -m mypy

test:
	pytest

setup-dev-env:
	bash scripts/setup-dev-env.sh

upload-pypi:
	bash scripts/upload2pypi.sh

upload-anaconda:
	bash scripts/upload2anaconda.sh

check: fmt lint

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
