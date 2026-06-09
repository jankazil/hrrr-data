.PHONY: fmt lint test check clean setup-dev-env upload-anaconda

fmt:
	python -m ruff format

lint:
	python -m ruff check --fix

test:
	pytest

setup-dev-env:
	bash scripts/setup-dev-env.sh

upload-anaconda:
	bash scripts/upload2anaconda.sh

check: fmt lint

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage dist build
