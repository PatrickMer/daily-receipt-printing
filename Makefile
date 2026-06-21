RUN = uv run

.PHONY: format lint test build run clean help

format: ## Auto-fix formatting and lint issues
	$(RUN) black src tests
	$(RUN) ruff check --fix src tests

lint: ## Check formatting, lint, and types (no modifications)
	$(RUN) black --check src tests
	$(RUN) ruff check src tests
	$(RUN) mypy

test: ## Run pytest with coverage
	$(RUN) pytest

build: lint test ## Full validation gate (lint + test)

run: ## Run the main script (use RECEIPT=path/to/receipt.json)
	PYTHONPATH=src $(RUN) python src/core/main.py $(RECEIPT)

preview: ## Preview receipt as text (use RECEIPT=path/to/receipt.json)
	PYTHONPATH=src $(RUN) python src/core/main.py --preview $(RECEIPT)

clean: ## Remove build artifacts and caches
	rm -rf build/ .mypy_cache/ .pytest_cache/ .ruff_cache/ htmlcov/
	rm -f .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

help: ## Show available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
