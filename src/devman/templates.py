# src/devenv_templater/templates.py
"""Template definitions for devenv projects."""

DEVENV_NIX_TEMPLATE = '''# devenv.nix - {{name}}
{ pkgs, config, lib, ... }: {
  name = "{{name}}";
  
  languages.python = {
    enable = true;
    version = "{{python_version}}";
    uv.enable = true;
  };
  
  packages = with pkgs; [
    just
    git
{%if use_containers%}
    docker-compose
    skopeo
{%endif%}
{%if project_type == "ml"%}
    jupyter
{%endif%}
  ];

{%if container_type == "devenv"%}
  # Container generation via devenv
  containers.{{name}} = {
    name = "{{name}}";
    registry = "localhost:5000";
    copyToRoot = pkgs.buildEnv {
      name = "container-root";
      paths = with pkgs; [ python{{python_version_short}} git uv ];
    };
    config = {
{%if project_type == "api"%}
      Cmd = [ "uvicorn" "{{name}}.main:app" "--host" "0.0.0.0" "--reload" ];
      ExposedPorts = { "8000/tcp" = {}; };
{%endif%}
{%if project_type == "web"%}
      Cmd = [ "flask" "--app" "{{name}}.app:app" "run" "--host" "0.0.0.0" ];
      ExposedPorts = { "5000/tcp" = {}; };
{%endif%}
      Env = [
        "PYTHONPATH=/app/src"
        "UV_COMPILE_BYTECODE=1"
      ];
    };
  };
{%endif%}

  env = {
    PYTHONPATH = "${config.env.DEVENV_ROOT}/src";
{%if use_containers%}
    REGISTRY_URL = "localhost:5000";
{%endif%}
{%if use_database%}
    DATABASE_URL = "{{database_type}}://user:pass@localhost:5432/{{name}}";
{%endif%}
  };
  
  enterShell = ''
    echo "🚀 {{name}} development environment"
    
    # Install dependencies
    if [ -f "pyproject.toml" ]; then
      uv sync
    fi
    
    echo "Available commands: just --list"
  '';
  
{%if use_database%}
  services.{{database_type}} = {
    enable = true;
    initialScript = "CREATE DATABASE IF NOT EXISTS {{name}};";
  };
{%endif%}

{%if use_redis%}
  services.redis.enable = true;
{%endif%}

{%if project_type == "api"%}
  processes.api.exec = "uv run fastapi dev src/{{name}}/main.py --host 0.0.0.0";
{%endif%}
{%if project_type == "web"%}
  processes.web.exec = "uv run flask --app src/{{name}}/app.py run --debug";
{%endif%}
{%if project_type == "ml"%}
  processes.jupyter.exec = "uv run jupyter lab --ip=0.0.0.0 --no-browser";
{%endif%}
}'''

JUSTFILE_TEMPLATE = '''# justfile - {{name}}
set dotenv-load

# List available commands
default:
    @just --list

# Enter development shell
shell:
    devenv shell

# Start development server
dev:
{%if project_type == "api"%}
    uv run fastapi dev src/{{name}}/main.py --host 0.0.0.0 --reload
{%endif%}
{%if project_type == "web"%}
    uv run flask --app src/{{name}}/app.py run --debug
{%endif%}
{%if project_type == "cli"%}
    uv run python -m {{name}}.cli
{%endif%}
{%if project_type == "ml"%}
    uv run jupyter lab --ip=0.0.0.0 --no-browser
{%endif%}

# Run tests
test:
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    uv run pytest tests/ --cov=src/{{name}} --cov-report=html

# Lint and format
lint:
    uv run ruff format src/ tests/
    uv run ruff check src/ tests/ --fix

# Type check
check:
    uv run mypy src/

# Security audit
audit:
    uv run pip-audit

# Install local dependency
install-local dep:
    uv add --editable ../{{dep}}

# Update dependencies  
update:
    uv lock --upgrade
    uv sync

{%if container_type == "devenv"%}
# Build devenv container
build:
    devenv container build {{name}}

# Run container
run:
    docker run --rm -p {%if project_type == "api"%}8000:8000{%endif%}{%if project_type == "web"%}5000:5000{%endif%} localhost:5000/{{name}}

# Push to registry
push:
    devenv container build {{name}}
    docker push localhost:5000/{{name}}
{%endif%}

{%if container_type == "docker"%}
# Build docker container
build:
    docker compose build

# Start all services
up:
    docker compose up -d

# Stop all services
down:
    docker compose down

# View logs
logs:
    docker compose logs -f
{%endif%}

{%if use_database%}
# Database migration
migrate:
    uv run alembic upgrade head

# Create migration
migrate-create message:
    uv run alembic revision --autogenerate -m "{{message}}"
{%endif%}

# Clean artifacts
clean:
    rm -rf .pytest_cache __pycache__ .coverage htmlcov/
    find . -type d -name "__pycache__" -delete
'''

PYPROJECT_TEMPLATE = '''[project]
name = "{{name}}"
version = "0.1.0"
description = "{{name}} - A Python project"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
{%for dep in dependencies%}
    "{{dep}}",
{%endfor%}
]
requires-python = ">={{python_version}}"

[project.optional-dependencies]
dev = [
{%for dep in dev_dependencies%}
    "{{dep}}",
{%endfor%}
]

{%if project_type == "cli"%}
[project.scripts]
{{name}} = "{{name}}.cli:main"
{%endif%}

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py{{python_version_short}}"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "{{python_version}}"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"

{%for dep in local_dependencies%}
[tool.uv.sources]
{{dep}} = { path = "../{{dep}}" }

{%endfor%}
'''

ENVRC_TEMPLATE = '''# .envrc - Automatic devenv activation
use devenv
'''

DOCKERFILE_TEMPLATE = '''# Dockerfile - {{name}}
FROM python:{{python_version}}-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Environment optimization
ENV UV_COMPILE_BYTECODE=1 \\
    UV_LINK_MODE=copy \\
    PYTHONPATH=/app/src

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \\
    uv sync --frozen

# Copy application
COPY . .

{%if project_type == "api"%}
EXPOSE 8000
CMD ["uvicorn", "{{name}}.main:app", "--host", "0.0.0.0", "--port", "8000"]
{%endif%}
{%if project_type == "web"%}
EXPOSE 5000
CMD ["flask", "--app", "{{name}}.app:app", "run", "--host", "0.0.0.0"]
{%endif%}
'''

DOCKER_COMPOSE_TEMPLATE = '''# docker-compose.yml - {{name}}
services:
  app:
    build: .
    ports:
{%if project_type == "api"%}
      - "8000:8000"
{%endif%}
{%if project_type == "web"%}
      - "5000:5000"
{%endif%}
    volumes:
      - .:/app
    environment:
      - PYTHONPATH=/app/src
{%if use_database%}
      - DATABASE_URL={{database_type}}://user:pass@{{database_type}}:5432/{{name}}
{%endif%}
{%if use_redis%}
      - REDIS_URL=redis://redis:6379
{%endif%}
{%if use_database or use_redis%}
    depends_on:
{%if use_database%}
      - {{database_type}}
{%endif%}
{%if use_redis%}
      - redis
{%endif%}
{%endif%}

{%if use_database and database_type == "postgresql"%}
  postgresql:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: {{name}}
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
{%endif%}

{%if use_redis%}
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
{%endif%}

{%if use_database or use_redis%}
volumes:
{%if use_database%}
  postgres_data:
{%endif%}
{%if use_redis%}
  redis_data:
{%endif%}
{%endif%}
'''

NIXOS_CONTAINER_TEMPLATE = '''# container.nix - NixOS container for {{name}}
{ config, pkgs, ... }: {
  containers.{{name}} = {
    autoStart = true;
    privateNetwork = true;
    hostAddress = "192.168.100.10";
    localAddress = "192.168.100.11";
    
    config = { config, pkgs, ... }: {
      services.openssh.enable = true;
      users.users.root.openssh.authorizedKeys.keys = [
        # Add your SSH public key here
      ];
      
      environment.systemPackages = with pkgs; [
        python{{python_version_short}}
        git
        uv
      ];
      
      networking.firewall.allowedTCPPorts = [ {%if project_type == "api"%}8000{%endif%}{%if project_type == "web"%}5000{%endif%} ];
    };
  };
}'''

TEMPLATES = {
    "devenv.nix.j2": DEVENV_NIX_TEMPLATE,
    "justfile.j2": JUSTFILE_TEMPLATE,
    "pyproject.toml.j2": PYPROJECT_TEMPLATE,
    ".envrc.j2": ENVRC_TEMPLATE,
    "Dockerfile.j2": DOCKERFILE_TEMPLATE,
    "docker-compose.yml.j2": DOCKER_COMPOSE_TEMPLATE,
    "container.nix.j2": NIXOS_CONTAINER_TEMPLATE,
}