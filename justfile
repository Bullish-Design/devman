# justfile
# Development tasks for devman

default: test

# Install dependencies
install:
    uv sync

# Run all tests
test:
    uv run pytest -v

# Run tests with coverage
test-cov:
    uv run pytest --cov=src/devman --cov-report=html --cov-report=term-missing

# Run specific test file
test-file file:
    uv run pytest tests/{{file}} -v

# Run tests matching a pattern
test-match pattern:
    uv run pytest -k "{{pattern}}" -v

# Format code
fmt:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Lint code
lint:
    uv run ruff check src tests
    uv run mypy src

# Type check only
check:
    uv run mypy src

# Run all quality checks
qa: lint test

# Clean up temporary files
clean:
    rm -rf .pytest_cache
    rm -rf __pycache__
    rm -rf htmlcov
    rm -rf .coverage
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} +

# Build package
build:
    uv build

# Install package in development mode
dev-install:
    uv pip install -e .

# Test the CLI directly
test-cli *args:
    uv run python -m devman.cli {{args}}

# Generate a test project
test-generate name="test-project":
    uv run python -m devman.cli generate {{name}} --demo

# Show CLI help
help-cli:
    uv run python -m devman.cli --help

# Run tests in watch mode (requires pytest-xdist)
test-watch:
    uv run pytest --looponfail

# Create test coverage badge
coverage-badge:
    uv run coverage-badge -o coverage.svg

# Profile test performance
test-profile:
    uv run pytest --profile-svg

# Setup development environment
setup: install dev-install
    @echo "✅ Development environment ready!"
    @echo "🧪 Run 'just test' to run tests"
    @echo "🎨 Run 'just fmt' to format code"
    @echo "🔍 Run 'just lint' to check code quality"
