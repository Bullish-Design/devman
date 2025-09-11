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

# Store current branch
ORIGINAL_BRANCH=$(git branch --show-current)

echo "📦 Current project: $PROJECT_NAME"
echo "🌿 Creating branch: $BRANCH_NAME"
echo "📋 Template: $TEMPLATE"
echo "🐍 Python: $PYTHON_VERSION"

# Create and switch to migration branch
git checkout -b "$BRANCH_NAME" 2>/dev/null || {
    echo "⚠️  Branch $BRANCH_NAME exists, switching to it"
    git checkout "$BRANCH_NAME"
}

# Backup current files list
echo "📋 Cataloging existing files..."
find . -type f -not -path './.git/*' > /tmp/original_files.txt

# Generate devman template in temp directory
TEMP_DIR=$(mktemp -d)
echo "🏗️  Generating devman template..."
cd "$TEMP_DIR"

#devman generate "$PROJECT_NAME" \
uv sync
devman generate "$PROJECT_NAME" \
#uv run python -m devman.cli generate "$PROJECT_NAME" \
    --template "$TEMPLATE" \
    --python "$PYTHON_VERSION" \
    --security \
    --force

cd - > /dev/null

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

# Copy devman structure over current project
echo "🔄 Applying devman structure..."
cp -r "$TEMP_DIR/$PROJECT_NAME"/* .
cp -r "$TEMP_DIR/$PROJECT_NAME"/.[^.]* . 2>/dev/null || true

# Restore project metadata
if [ -f "pyproject.toml" ]; then
    sed -i "s/^name = .*/name = \"$OLD_NAME\"/" pyproject.toml
    sed -i "s/^description = .*/description = \"$OLD_DESC\"/" pyproject.toml
    sed -i "s/^version = .*/version = \"$OLD_VERSION\"/" pyproject.toml
fi

# Copy back original source files, preserving devman structure
echo "📁 Restoring original source files..."

# Restore src/ directory if it exists in original
if [ -d .git ] && git show HEAD:src > /dev/null 2>&1; then
    rm -rf src/
    git checkout HEAD -- src/ 2>/dev/null || echo "⚠️  No src/ in original"
fi

# Restore tests/ if it exists
if [ -d .git ] && git show HEAD:tests > /dev/null 2>&1; then
    rm -rf tests/
    git checkout HEAD -- tests/ 2>/dev/null || echo "⚠️  No tests/ in original"
fi

# Restore other important files
PRESERVE_FILES=(
    "README.md"
    "CHANGELOG.md" 
    "LICENSE"
    "docs/"
    "scripts/"
    "data/"
    ".gitignore"
)

for file in "${PRESERVE_FILES[@]}"; do
    if [ -d .git ] && git show HEAD:"$file" > /dev/null 2>&1; then
        rm -rf "$file" 2>/dev/null || true
        git checkout HEAD -- "$file" 2>/dev/null && echo "✅ Restored $file"
    fi
done

# Merge dependencies if needed
if [ -f pyproject.toml ]; then
    echo "🔗 Syncing dependencies..."
    # Try to merge old dependencies via git
    if git show HEAD:pyproject.toml > /tmp/old_pyproject.toml 2>/dev/null; then
        echo "📦 Found old pyproject.toml, manual dependency review recommended"
    fi
fi

# Clean up temp directory
rm -rf "$TEMP_DIR"

# Install dependencies and run tests
echo "⚙️  Setting up development environment..."
if command -v direnv > /dev/null && [ -f .envrc ]; then
    direnv allow
fi

if command -v uv > /dev/null; then
    uv sync
elif command -v pip > /dev/null; then
    pip install -e ".[dev]"
fi

# Run test suite
echo "🧪 Running test suite..."
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

# Run security checks if available
if [ -f justfile ] && command -v just > /dev/null; then
    echo "🔒 Running security checks..."
    just security/check 2>/dev/null && echo "✅ Security checks passed" || echo "⚠️  Security checks failed or not available"
fi

# Summary
echo ""
echo "🎯 Migration Summary:"
echo "   Branch: $BRANCH_NAME"
echo "   Template: $TEMPLATE"
echo "   Tests: $([ "$TEST_PASSED" = true ] && echo "✅ PASSED" || echo "❌ FAILED")"
echo ""

if [ "$TEST_PASSED" = true ]; then
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
    echo "❌ Migration completed but tests failed."
    echo "   Review test failures and fix before committing."
    echo "   Return to original: git checkout $ORIGINAL_BRANCH"
fi

echo ""
echo "🔍 Files changed:"
git status --porcelain | head -10
[ $(git status --porcelain | wc -l) -gt 10 ] && echo "   ... and $(( $(git status --porcelain | wc -l) - 10 )) more"
