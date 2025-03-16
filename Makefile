.PHONY: test quality precommit clean

# Default Python interpreter
PYTHON ?= python

# Test command
test:
	$(PYTHON) -m pytest

# Run all quality checks and tests
quality: precommit-run test

# Install pre-commit hooks
precommit:
	pip install pre-commit
	pre-commit install

# Run pre-commit on all files
precommit-run:
	pre-commit run --all-files

# Clean build artifacts and temporary files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# Help target
help:
	@echo "Available targets:"
	@echo "  make test         - Run all tests"
	@echo "  make quality      - Run all quality checks and tests"
	@echo "  make precommit    - Install pre-commit hooks"
	@echo "  make precommit-run - Run pre-commit on all files"
	@echo "  make clean        - Remove build artifacts and cache files"
