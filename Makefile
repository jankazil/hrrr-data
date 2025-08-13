.PHONY: fmt lint type test check clean 

fmt:
	python -m ruff format

lint:
	python -m ruff check --fix

type:
	python -m mypy

test:
	pytest

check: fmt lint

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build
