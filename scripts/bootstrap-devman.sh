#!/usr/bin/env bash
# scripts/bootstrap-devman.sh
# Migrate existing project to devman structure using git

set -euo pipefail

PROJECT_NAME="${1:-$(basename $(pwd))}"
TEMPLATE="${2:-python-lib}"
PYTHON_VERSION="${3:-3.11}"
BRANCH_NAME="devman-migration"

echo "🚀 Bootstrapping $PROJECT_NAME with devman"

# Ensure we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "❌ Uncommitted changes found. Please commit or stash them first."
    exit 1
fi

# Store current branch and working directory
ORIGINAL_BRANCH=$(git branch --show-current)
WORKING_DIR=$(pwd)

echo "📦 Current project: $PROJECT_NAME"
echo "🌿 Creating branch: $BRANCH_NAME"
echo "📋 Template: $TEMPLATE"
echo "🐍 Python: $PYTHON_VERSION"

# Create and switch to migration branch
git checkout -b "$BRANCH_NAME" 2>/dev/null || {
    echo "⚠️  Branch $BRANCH_NAME exists, switching to it"
    git checkout "$BRANCH_NAME"
}

# Generate devman template in temp directory
echo "🏗️  Generating devman template..."

# Use uv run to ensure dependencies are available
uv run python -m devman.cli generate "$PROJECT_NAME" \
    --template "$TEMPLATE" \
    --python "$PYTHON_VERSION" \
    --security \
    --force

# Store original project metadata
echo "📊 Extracting project metadata..."
if [ -f "pyproject.toml" ]; then
    OLD_NAME=$(grep '^name = ' pyproject.toml | cut -d'"' -f2 || echo "$PROJECT_NAME")
    OLD_DESC=$(grep '^description = ' pyproject.toml | cut -d'"' -f2 || echo "")
    OLD_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2 || echo "0.1.0")
else
    OLD_NAME="$PROJECT_NAME"
    OLD_DESC=""
    OLD_VERSION="0.1.0"
fi

# Copy non-template files to generated project
echo "📁 Copying original files to template..."
GENERATED_DIR="$WORKING_DIR/$PROJECT_NAME"

# Copy back original source files
if [ -d "src/" ]; then
    rm -rf "$GENERATED_DIR/src/"
    cp -r "src/" "$GENERATED_DIR/"
fi

# Copy tests
if [ -d "tests/" ]; then
    rm -rf "$GENERATED_DIR/tests/"
    cp -r "tests/" "$GENERATED_DIR/"
fi

# Copy other important files
PRESERVE_FILES=(
    "README.md"
    "CHANGELOG.md" 
    "LICENSE"
    "docs/"
    "scripts/"
    "data/"
)

for file in "${PRESERVE_FILES[@]}"; do
    if [ -e "$file" ]; then
        cp -r "$file" "$GENERATED_DIR/" && echo "✅ Copied $file"
    fi
done

# Update project metadata in generated version
if [ -f "$GENERATED_DIR/pyproject.toml" ]; then
    sed -i "s/^name = .*/name = \"$OLD_NAME\"/" "$GENERATED_DIR/pyproject.toml"
    sed -i "s/^description = .*/description = \"$OLD_DESC\"/" "$GENERATED_DIR/pyproject.toml"
    sed -i "s/^version = .*/version = \"$OLD_VERSION\"/" "$GENERATED_DIR/pyproject.toml"
fi

# Test the generated project
echo "🧪 Testing generated project..."
cd "$GENERATED_DIR"

# Setup environment
if command -v direnv > /dev/null && [ -f .envrc ]; then
    direnv allow
fi

# Install dependencies
if command -v uv > /dev/null; then
    uv sync
elif command -v pip > /dev/null; then
    pip install -e ".[dev]"
fi

# Run tests
TEST_PASSED=false
if [ -f justfile ] && command -v just > /dev/null; then
    if just test; then
        TEST_PASSED=true
        echo "✅ Tests passed with just"
    fi
elif command -v pytest > /dev/null; then
    if pytest -q; then
        TEST_PASSED=true
        echo "✅ Tests passed with pytest"
    fi
elif [ -f pyproject.toml ] && command -v python > /dev/null; then
    if python -m pytest -q 2>/dev/null; then
        TEST_PASSED=true
        echo "✅ Tests passed with python -m pytest"
    fi
fi

# Run security checks
if [ -f justfile ] && command -v just > /dev/null; then
    echo "🔒 Running security checks..."
    just security/check 2>/dev/null && echo "✅ Security checks passed" || echo "⚠️  Security checks failed or not available"
fi

cd "$WORKING_DIR"

# Apply changes to working directory if tests passed
if [ "$TEST_PASSED" = true ]; then
    echo "🔄 Applying devman structure to working directory..."
    
    # Copy generated files back to working directory
    cp -r "$GENERATED_DIR"/* .
    cp -r "$GENERATED_DIR"/.[^.]* . 2>/dev/null || true
    
    # Clean up generated directory
    rm -rf "$GENERATED_DIR"
    
    echo "✅ Migration successful! Review changes and commit:"
    echo "   git add ."
    echo "   git commit -m 'Migrate to devman structure'"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Review pyproject.toml dependencies"
    echo "   2. Update README.md with new workflow" 
    echo "   3. Test devenv setup: direnv allow"
    echo "   4. Merge to main when ready"
else
    echo "❌ Tests failed. Generated project available at: $GENERATED_DIR"
    echo "   Review and fix issues, then manually copy if desired"
    echo "   Return to original: git checkout $ORIGINAL_BRANCH"
fi

echo ""
echo "🎯 Migration Summary:"
echo "   Branch: $BRANCH_NAME"
echo "   Template: $TEMPLATE"
echo "   Tests: $([ "$TEST_PASSED" = true ] && echo "✅ PASSED" || echo "❌ FAILED")"

if [ "$TEST_PASSED" = true ]; then
    echo ""
    echo "🔍 Files changed:"
    git status --porcelain | head -10
    [ $(git status --porcelain | wc -l) -gt 10 ] && echo "   ... and $(( $(git status --porcelain | wc -l) - 10 )) more"
fi
