.PHONY: install fmt lint format typecheck test cov schema check hooks

install:
	uv sync

fmt:
	uv run black packages scripts tests

lint:
	uv run ruff check packages scripts tests

format:
	uv run black --check packages scripts tests

typecheck:
	uv run mypy

test:
	uv run pytest

cov:
	uv run pytest --cov=state --cov-report=term-missing

schema:
	PYTHONPATH=packages uv run python scripts/generate_schema.py

# Canonical M0 quality gate.
check: lint format typecheck test
	@echo "quality gate passed."

hooks:
	uv run pre-commit install
