#!/usr/bin/env bash
# examples/complete-workflow.sh
# Complete example using remote templates and security features

set -euo pipefail

echo "🚀 Complete devman workflow with remote templates and security"

# 1. Initialize devman with security defaults
echo "📋 Initializing configuration..."
devman config --init
devman config --set security_enabled=true
devman config --set pre_commit_hooks=true
devman config --set dependency_scanning=true

# 2. Add remote templates
echo "🌐 Adding remote templates..."
devman template add company-python https://github.com/company/python-templates.git \
  --description "Company Python template with standards"

devman template add fastapi-modern gh:tiangolo/full-stack-fastapi-template \
  --description "Modern FastAPI template"

# 3. List available templates
echo "📖 Available templates:"
devman list
devman template list

# 4. Generate project with security features
echo "🏗️ Generating secure project..."
devman generate my-secure-app \
  --template company-python \
  --python 3.11 \
  --security \
  --pre-commit \
  --security-scan \
  --secret-detection

cd my-secure-app

# 5. Verify security setup
echo "🛡️ Security configuration:"
ls -la | grep -E "\.(pre-commit|bandit|safety|secrets)"

# 6. Activate development environment
echo "🔧 Setting up development environment..."
direnv allow  # Activates Nix environment
uv sync       # Install dependencies including security tools

# 7. Install and run security tools
echo "🔒 Installing security hooks..."
just security/install-hooks

# 8. Run comprehensive security scan
echo "🔍 Running security scan..."
just security/check

# Example output shows:
# ✓ Pre-commit hooks installed
# ✓ Bandit security scan passed
# ✓ Safety vulnerability scan passed  
# ✓ Secret detection baseline created
# ✓ Dependency audit completed

# 9. Development workflow with security
echo "💻 Development workflow:"
echo "  just test           # Run tests"
echo "  just security/scan  # Security scan"
echo "  just fmt           # Format code"
echo "  just lint          # Lint with security rules"

# 10. Template updates
echo "🔄 Updating templates..."
devman template update company-python
devman template update --all

echo "✅ Complete setup finished!"
echo ""
echo "🎯 Key features enabled:"
echo "  ✓ Remote template support (Git URLs, gh: shortcuts)"
echo "  ✓ Template registry and caching"
echo "  ✓ Pre-commit security hooks"
echo "  ✓ Dependency vulnerability scanning"
echo "  ✓ Secret detection"
echo "  ✓ Security linting (bandit, safety)"
echo "  ✓ Automated security in Justfile"
echo ""
echo "📝 Generated project includes:"
echo "  • .pre-commit-config.yaml - Security hooks"
echo "  • .bandit - Security linting config"
echo "  • .safety-policy.yml - Vulnerability scanning"
echo "  • .secrets.baseline - Secret detection baseline"
echo "  • justfile - Security commands integrated"
echo ""
echo "🔗 Template sources:"
echo "  • Built-in: python-lib, python-cli, fastapi-api"
echo "  • Remote: company-python, fastapi-modern"
echo "  • Git URLs: https://github.com/org/repo.git"
echo "  • GitHub shortcuts: gh:org/repo"
