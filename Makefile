.PHONY: install test lint fmt audit build clean

PYTHON ?= python
EXAMPLE ?= examples/input_zh_gongwen.txt
REPORT ?= build/report.md

install: ## Install the package with dev extras (editable)
	$(PYTHON) -m pip install -e ".[dev]"

test: ## Run the test suite
	$(PYTHON) -m pytest -q

lint: ## Check code style with ruff
	$(PYTHON) -m ruff check src tests

fmt: ## Auto-format code with ruff
	$(PYTHON) -m ruff format src tests

audit: ## Run a baseline audit report against the sample input
	$(PYTHON) -m deslopkit audit $(EXAMPLE) --md $(REPORT)

build: ## Build sdist + wheel
	$(PYTHON) -m build

clean: ## Remove build/test artifacts
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
