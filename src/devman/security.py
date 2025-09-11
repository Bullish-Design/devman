# src/devman/security.py
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from .exceptions import DevmanError


class SecurityConfig(BaseModel):
    """Security configuration for projects."""

    enable_pre_commit: bool = True
    enable_dependency_scan: bool = True
    enable_secret_detection: bool = True
    enable_security_linting: bool = True
    enable_vulnerability_scan: bool = True
    bandit_enabled: bool = True
    safety_enabled: bool = True

    # Pre-commit hook versions
    pre_commit_hooks_version: str = "v4.5.0"
    ruff_version: str = "v0.1.0"
    mypy_version: str = "v1.7.0"
    bandit_version: str = "1.7.5"
    detect_secrets_version: str = "v1.4.0"


class SecurityManager:
    """Manages security configuration and tooling."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.console = Console()

    def generate_pre_commit_config(self, destination: Path) -> None:
        """Generate comprehensive pre-commit configuration."""
        if not self.config.enable_pre_commit:
            return

        hooks_config = {
            "repos": [
                {
                    "repo": "https://github.com/pre-commit/pre-commit-hooks",
                    "rev": self.config.pre_commit_hooks_version,
                    "hooks": [
                        {"id": "trailing-whitespace"},
                        {"id": "end-of-file-fixer"},
                        {"id": "check-yaml"},
                        {"id": "check-added-large-files"},
                        {"id": "check-merge-conflict"},
                        {"id": "check-toml"},
                        {"id": "debug-statements"},
                        {"id": "name-tests-test", "args": ["--pytest-test-first"]},
                    ],
                },
                {
                    "repo": "https://github.com/astral-sh/ruff-pre-commit",
                    "rev": self.config.ruff_version,
                    "hooks": [{"id": "ruff", "args": ["--fix"]}, {"id": "ruff-format"}],
                },
                {
                    "repo": "https://github.com/pre-commit/mirrors-mypy",
                    "rev": self.config.mypy_version,
                    "hooks": [{"id": "mypy", "additional_dependencies": ["types-all"], "args": ["--strict"]}],
                },
            ]
        }

        # Add security-specific hooks
        if self.config.enable_secret_detection:
            hooks_config["repos"].append(
                {
                    "repo": "https://github.com/Yelp/detect-secrets",
                    "rev": self.config.detect_secrets_version,
                    "hooks": [{"id": "detect-secrets", "args": ["--baseline", ".secrets.baseline"]}],
                }
            )

        if self.config.bandit_enabled:
            hooks_config["repos"].append(
                {
                    "repo": "https://github.com/PyCQA/bandit",
                    "rev": self.config.bandit_version,
                    "hooks": [{"id": "bandit", "args": ["-r", "src/", "-f", "json", "-o", "bandit-report.json"]}],
                }
            )

        (destination / ".pre-commit-config.yaml").write_text(
            yaml.dump(hooks_config, default_flow_style=False, sort_keys=False)
        )

    def generate_security_configs(self, destination: Path, package_name: str) -> None:
        """Generate security-related configuration files."""

        # Bandit configuration
        if self.config.bandit_enabled:
            bandit_config = {
                "tests": [
                    "B201",
                    "B301",
                    "B302",
                    "B303",
                    "B304",
                    "B305",
                    "B306",
                    "B307",
                    "B308",
                    "B309",
                    "B310",
                    "B311",
                    "B312",
                    "B313",
                    "B314",
                    "B315",
                    "B316",
                    "B317",
                    "B318",
                    "B319",
                    "B320",
                    "B321",
                    "B322",
                    "B323",
                    "B324",
                    "B325",
                    "B401",
                    "B402",
                    "B403",
                    "B404",
                    "B405",
                    "B406",
                    "B407",
                    "B408",
                    "B409",
                    "B410",
                    "B411",
                    "B412",
                    "B413",
                    "B501",
                    "B502",
                    "B503",
                    "B504",
                    "B505",
                    "B506",
                    "B507",
                    "B601",
                    "B602",
                    "B603",
                    "B604",
                    "B605",
                    "B606",
                    "B607",
                    "B608",
                    "B609",
                    "B610",
                    "B611",
                    "B701",
                    "B702",
                    "B703",
                ],
                "skips": ["B101", "B601"],  # Skip assert and shell injection in tests
                "exclude_dirs": ["tests", "venv", ".venv"],
            }

            (destination / ".bandit").write_text(yaml.dump(bandit_config))

        # Safety configuration
        if self.config.safety_enabled:
            safety_config = {"security": {"ignore-vulnerabilities": [], "continue-on-vulnerability-error": False}}

            (destination / ".safety-policy.yml").write_text(yaml.dump(safety_config))

        # Detect secrets baseline
        if self.config.enable_secret_detection:
            self._initialize_secrets_baseline(destination)

        # Security-focused ruff configuration
        self._generate_security_ruff_config(destination)

    def generate_security_justfile_commands(self) -> Dict[str, str]:
        """Generate security-related Justfile commands."""
        commands = {}

        if self.config.enable_pre_commit:
            commands.update(
                {
                    "security-install-hooks": "pre-commit install",
                    "security-run-hooks": "pre-commit run --all-files",
                }
            )

        if self.config.bandit_enabled:
            commands["security-bandit"] = "bandit -r src/ -f json -o bandit-report.json"

        if self.config.safety_enabled:
            commands["security-safety"] = "safety check --json --output safety-report.json"

        if self.config.enable_dependency_scan:
            commands.update(
                {
                    "security-dep-scan": "uv pip check",
                    "security-audit": "pip-audit --format=json --output=audit-report.json",
                }
            )

        if self.config.enable_vulnerability_scan:
            commands["security-vuln-scan"] = "python -m pip_audit --format=json --output=vulnerability-report.json"

        # Comprehensive security check
        commands["security-check"] = (
            " && ".join(
                [
                    "just security-bandit" if self.config.bandit_enabled else "",
                    "just security-safety" if self.config.safety_enabled else "",
                    "just security-dep-scan" if self.config.enable_dependency_scan else "",
                    "just security-run-hooks" if self.config.enable_pre_commit else "",
                ]
            )
            .replace(" &&  && ", " && ")
            .strip(" && ")
        )

        return {k: v for k, v in commands.items() if v}

    def install_security_tools(self, destination: Path) -> None:
        """Install security tools and dependencies."""
        tools = []

        if self.config.enable_pre_commit:
            tools.append("pre-commit")

        if self.config.bandit_enabled:
            tools.append("bandit[toml]")

        if self.config.safety_enabled:
            tools.append("safety")

        if self.config.enable_dependency_scan:
            tools.extend(["pip-audit", "pip-tools"])

        if tools:
            # Add to pyproject.toml dev dependencies
            pyproject_path = destination / "pyproject.toml"
            if pyproject_path.exists():
                self._add_dev_dependencies(pyproject_path, tools)

    def run_security_scan(self, project_path: Path) -> Dict[str, bool]:
        """Run comprehensive security scan and return results."""
        results = {}

        if self.config.bandit_enabled:
            results["bandit"] = self._run_bandit(project_path)

        if self.config.safety_enabled:
            results["safety"] = self._run_safety(project_path)

        if self.config.enable_dependency_scan:
            results["dependency_scan"] = self._run_dependency_scan(project_path)

        if self.config.enable_secret_detection:
            results["secret_detection"] = self._run_secret_detection(project_path)

        return results

    def _initialize_secrets_baseline(self, destination: Path) -> None:
        """Initialize detect-secrets baseline."""
        try:
            subprocess.run(
                ["detect-secrets", "scan", "--baseline", ".secrets.baseline"],
                cwd=destination,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Create empty baseline if detect-secrets not available
            baseline = {
                "version": "1.4.0",
                "plugins_used": [
                    {"name": "ArtifactoryDetector"},
                    {"name": "AWSKeyDetector"},
                    {"name": "Base64HighEntropyString", "limit": 4.5},
                    {"name": "BasicAuthDetector"},
                    {"name": "CloudantDetector"},
                    {"name": "GitHubTokenDetector"},
                    {"name": "HexHighEntropyString", "limit": 3.0},
                    {"name": "PrivateKeyDetector"},
                    {"name": "SlackDetector"},
                    {"name": "StripeDetector"},
                ],
                "filters_used": [
                    {"path": "detect_secrets.filters.allowlist.is_line_allowlisted"},
                    {"path": "detect_secrets.filters.common.is_baseline_file"},
                ],
                "results": {},
                "generated_at": "2024-01-01T00:00:00Z",
            }

            import json

            (destination / ".secrets.baseline").write_text(json.dumps(baseline, indent=2))

    def _generate_security_ruff_config(self, destination: Path) -> None:
        """Generate security-focused ruff configuration."""
        ruff_security_rules = [
            "S",  # flake8-bandit
            "B",  # flake8-bugbear
            "A",  # flake8-builtins
            "C4",  # flake8-comprehensions
            "T20",  # flake8-print
            "SIM",  # flake8-simplify
            "PIE",  # flake8-pie
            "PL",  # pylint
        ]

        # This would be added to pyproject.toml ruff configuration
        security_config = {
            "select": ruff_security_rules,
            "ignore": [
                "S101",  # Use of assert
                "S311",  # Standard pseudo-random generators are not suitable for security/cryptographic purposes
            ],
        }

        return security_config

    def _add_dev_dependencies(self, pyproject_path: Path, tools: List[str]) -> None:
        """Add security tools to pyproject.toml dev dependencies."""
        try:
            import tomli_w
            import tomllib

            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            if "project" not in data:
                data["project"] = {}
            if "optional-dependencies" not in data["project"]:
                data["project"]["optional-dependencies"] = {}
            if "dev" not in data["project"]["optional-dependencies"]:
                data["project"]["optional-dependencies"]["dev"] = []

            existing_deps = data["project"]["optional-dependencies"]["dev"]
            for tool in tools:
                if tool not in existing_deps:
                    existing_deps.append(tool)

            with open(pyproject_path, "wb") as f:
                tomli_w.dump(data, f)

        except ImportError:
            # Fallback: append to file manually
            content = pyproject_path.read_text()
            for tool in tools:
                if tool not in content:
                    content = content.replace("dev = [", f'dev = [\n    "{tool}",')
            pyproject_path.write_text(content)

    def _run_bandit(self, project_path: Path) -> bool:
        """Run bandit security scan."""
        try:
            result = subprocess.run(
                ["bandit", "-r", "src/", "-f", "json", "-o", "bandit-report.json"],
                cwd=project_path,
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _run_safety(self, project_path: Path) -> bool:
        """Run safety vulnerability scan."""
        try:
            result = subprocess.run(
                ["safety", "check", "--json", "--output", "safety-report.json"], cwd=project_path, capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _run_dependency_scan(self, project_path: Path) -> bool:
        """Run dependency vulnerability scan."""
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json", "--output=audit-report.json"], cwd=project_path, capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _run_secret_detection(self, project_path: Path) -> bool:
        """Run secret detection scan."""
        try:
            result = subprocess.run(
                ["detect-secrets", "scan", "--baseline", ".secrets.baseline"], cwd=project_path, capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
