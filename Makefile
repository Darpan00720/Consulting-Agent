.PHONY: install fmt lint format typecheck test cov schema traceability check hooks vault-index

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

traceability:
	PYTHONPATH=packages uv run python scripts/generate_traceability.py

# Reindex the knowledge vault ONLY (ADR-003). Never point graphify at packages/.
# Runs from inside the vault so caches/outputs stay in knowledge-vault/graphify-out.
vault-index:
	cd knowledge-vault && graphify update . --force

# Canonical M0 quality gate.
check: lint format typecheck test
	@echo "quality gate passed."

hooks:
	uv run pre-commit install
