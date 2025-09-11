
default: dev

dev:
	uv run pytest -q

test:
	uv run pytest -q

fmt:
	ruff format .

lint:
	ruff check .

docker-build:
	docker build -t { '{ project_slug }' } .

docker-up:
	docker compose up -d

docker-down:
	docker compose down


# Security commands
security-install-hooks:
	pre-commit install

security-run-hooks:
	pre-commit run --all-files

security-bandit:
	bandit -r src/ -f json -o bandit-report.json

security-safety:
	safety check --json --output safety-report.json

security-dep-scan:
	uv pip check

security-audit:
	pip-audit --format=json --output=audit-report.json

security-vuln-scan:
	python -m pip_audit --format=json --output=vulnerability-report.json

security-check:
	just security-bandit && just security-safety && just security-dep-scan && just security-run-hooks

