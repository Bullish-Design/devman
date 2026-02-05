# Boomtube Refactor Analysis

**Date**: 2026-02-05
**Purpose**: Analyze using Boomtube library for all symlinking functionality in devman
**Boomtube Repository**: https://github.com/Bullish-Design/boomtube

## Executive Summary

Boomtube is a Python library and CLI tool that manages project-local symlinks with intelligent migration capabilities. It provides declarative symlink configuration via YAML, bidirectional file/directory migration with conflict detection, and variable interpolation for flexible path management.

**Recommendation**: Boomtube is well-suited for managing devman's symlinking needs, particularly for `.git`, `.venv`, and project-specific configurations. It provides robust migration, safety features, and a clean declarative interface.

---

## 1. Boomtube Overview

### Core Capabilities

1. **Declarative Symlink Management**
   - YAML-based configuration (`boomtube.yaml`)
   - Link specification with source (link) and target paths
   - Auto-detection of file vs directory types
   - Named links for better logging/reporting

2. **Safe Migration**
   - Bidirectional file/directory merging
   - Timestamp-based conflict resolution (mtime comparison)
   - SHA-256 content hashing for duplicate detection
   - Non-destructive conflict copies with timestamped suffixes
   - Preserves both sides' unique content

3. **Variable System**
   - Built-in variables: `{project_root}`, `{project_name}`
   - User-defined variables with interpolation
   - Lazy resolution with cycle detection
   - Cross-variable references

4. **Robustness**
   - Symlink-aware directory traversal (doesn't follow symlinks during migration)
   - Parent directory auto-creation
   - Validation via Pydantic models
   - Comprehensive error handling

---

## 2. Architecture Analysis

### Module Breakdown

#### `fsops.py` - File System Operations
**Relevance**: ⭐⭐⭐⭐⭐

Core primitives for symlink operations:
- `symlink_to()`: Creates symlinks with parent directory creation
- `is_symlink()`: Safe symlink detection with OSError handling
- `readlink_abs()`: Resolves symlink targets to absolute paths
- `normalize_path()`: Path normalization for cross-platform comparison
- `remove_path()`: Safe removal without following inner symlinks

**Strengths**:
- Handles edge cases (broken symlinks, special files)
- Doesn't follow symlinks during removal (prevents data loss)
- Absolute path resolution for comparison

**Potential Issues**:
- No dry-run capability
- Limited atomic operation support

#### `apply.py` - Symlink Application Logic
**Relevance**: ⭐⭐⭐⭐⭐

Main orchestration layer:
- `detect_kind()`: Auto-detects file vs directory based on:
  1. Explicit `kind` in spec
  2. Existing link path type
  3. Existing target path type
  4. Heuristic (dot-folders without extensions = dir)
- `apply_link()`: Handles symlink creation/replacement with migration
- `apply_all()`: Batch processing of link specs

**Strengths**:
- Intelligent type detection
- Idempotent operations (no-op if already correct)
- Migration integrated into application flow
- Clear logging of operations

**Considerations**:
- Always creates target directories (might not be desired in all cases)
- Migration is opt-out (enabled by default)
- No validation of target existence before symlinking

#### `migrate.py` - Migration Logic
**Relevance**: ⭐⭐⭐⭐

Sophisticated bidirectional merge:
- `migrate_file()`: Single file reconciliation
- `migrate_dir()`: Recursive directory merge
- Conflict detection with timestamp comparison (1ms epsilon)
- Content-based deduplication

**Algorithm**:
```
For each file/directory pair (A=project, B=target):
1. If only A exists → copy A to B
2. If only B exists → copy B to A
3. If both exist:
   a. If content identical → skip (log as identical)
   b. If mtime(A) > mtime(B) + ε → copy A to B (A is newer)
   c. If mtime(B) > mtime(A) + ε → copy B to A (B is newer)
   d. If mtimes within ε → create conflict copy on B side
```

**Strengths**:
- Preserves all unique content
- Timestamp-based automatic resolution
- SHA-256 content comparison
- Non-destructive (conflict copies rather than overwrites)

**Limitations**:
- No user interaction for conflicts
- Conflict copies accumulate on target side
- No git-aware merging
- Timestamp comparison can fail with clock skew

#### `config.py` & `models.py` - Configuration
**Relevance**: ⭐⭐⭐⭐

Pydantic-based validation:
- `LinkSpec`: Individual symlink specification
  - Validates relative paths for `link`
  - Disallows `~` expansion in links (must be relative to project root)
  - `kind`: auto/file/dir
  - `migrate`: boolean flag
- `BoomtubeConfig`: Top-level config
  - Version checking (must be 1)
  - Variable definitions
  - Link array

**Strengths**:
- Strong validation before execution
- Clear error messages
- Type safety via Pydantic

**Limitations**:
- No schema for complex conditions (OS-specific links, etc.)
- No templating beyond variable substitution
- Single config file (no includes/extends)

#### `resolve.py` - Variable Resolution
**Relevance**: ⭐⭐⭐

Lazy variable resolver with cycle detection:
- DFS-based resolution
- Supports `{var}` syntax
- Built-ins: `{project_root}`, `{project_name}`
- User vars can reference other vars and built-ins

**Example**:
```yaml
vars:
  cache_root: "{project_root}/../.cache"
  project_cache: "{cache_root}/{project_name}"

links:
  - link: .git
    target: "{project_cache}/.git"
```

**Strengths**:
- Flexible path composition
- Lazy evaluation (only resolves what's needed)
- Clear error messages for missing vars

**Limitations**:
- No functions/filters (can't do path manipulation, env vars, etc.)
- No conditional logic
- Recursion limit (50 levels)

#### `hashing.py` - Content Comparison
**Relevance**: ⭐⭐⭐

Simple but effective:
- SHA-256 with chunked reading (1MB chunks)
- Size comparison short-circuit
- `files_identical()` for deduplication

**Strengths**:
- Memory-efficient for large files
- Cryptographically strong

**Considerations**:
- No caching of hashes
- No content-defined chunking (for partial matches)

---

## 3. Use Cases for Devman

### Ideal Scenarios

#### 1. `.git` Directory Relocation
```yaml
# boomtube.yaml
version: 1
vars:
  workspace_cache: "/workspace/.cache/{project_name}"

links:
  - name: "Git repository"
    link: .git
    target: "{workspace_cache}/.git"
    kind: dir
    migrate: true
```

**Benefits**:
- Automatic migration of existing `.git` directory
- Preserves all git history and state
- Bidirectional sync (handles existing cache content)

#### 2. Python Virtual Environment
```yaml
links:
  - name: "Python venv"
    link: .venv
    target: "{workspace_cache}/.venv"
    kind: dir
    migrate: false  # venvs shouldn't be migrated
```

**Benefits**:
- Clean project directory
- Shared cache location
- No migration needed (venvs are environment-specific)

#### 3. Project-Specific Configs
```yaml
links:
  - link: .env.local
    target: "{workspace_cache}/.env.local"
    kind: file
    migrate: true

  - link: .ruff_cache
    target: "{workspace_cache}/.ruff_cache"
    kind: dir
    migrate: true
```

**Benefits**:
- Persistent configs across project copies
- Safe migration of existing configs

### Complex Scenarios

#### 4. Multi-Project Workspace
```yaml
vars:
  shared_cache: "/workspace/.shared-cache"
  eslint_config: "{shared_cache}/eslint-config"

links:
  - link: .eslintrc.json
    target: "{eslint_config}/.eslintrc.json"
    kind: file
```

**Use Case**: Multiple projects sharing common configurations.

#### 5. OS-Specific Paths
**Limitation**: Boomtube doesn't natively support OS-specific configurations.

**Workaround**: Multiple config files with CLI flag:
```bash
boomtube apply --config boomtube.linux.yaml
boomtube apply --config boomtube.darwin.yaml
```

---

## 4. Strengths

### 1. **Declarative & Version-Controlled**
- Symlink configuration lives in the repository
- Easy to review, audit, and replicate
- Clear intent vs imperative scripts

### 2. **Intelligent Migration**
- Handles existing files/directories gracefully
- Bidirectional merge prevents data loss
- Timestamp-based automatic resolution
- Content deduplication

### 3. **Safety Features**
- Pydantic validation prevents misconfigurations
- Non-destructive operations (conflict copies)
- Doesn't follow symlinks during traversal
- Path normalization prevents relative path issues

### 4. **Idempotent**
- Running `boomtube apply` multiple times is safe
- Only makes changes when needed
- Detects and preserves correct symlinks

### 5. **Flexible Variable System**
- Avoids hardcoded paths
- Supports path composition
- Built-in project context

### 6. **Clear Logging**
- Reports all operations
- Migration statistics
- Conflict warnings

---

## 5. Limitations & Gaps

### 1. **No Conditional Logic**
**Issue**: Can't specify OS-specific or environment-specific links in a single config.

**Impact**: Need multiple config files or wrapper scripts for cross-platform projects.

**Workaround**:
```bash
# In setup script
if [[ "$OSTYPE" == "darwin"* ]]; then
    boomtube apply --config boomtube.darwin.yaml
else
    boomtube apply --config boomtube.linux.yaml
fi
```

### 2. **No Environment Variable Support**
**Issue**: Can't reference `$HOME`, `$XDG_CACHE_HOME`, etc. in config.

**Impact**: Less flexible for user-specific paths.

**Workaround**: Shell script wrapper that generates config:
```bash
export BOOMTUBE_CACHE="$HOME/.cache/devman"
boomtube apply
```

### 3. **Migration Conflicts Require Manual Resolution**
**Issue**: When mtime tie occurs, creates conflict copy on target side.

**Impact**: User must manually resolve conflicts.

**Severity**: Low (conflicts are rare with proper workflow).

### 4. **No Dry-Run Mode**
**Issue**: Can't preview changes without executing.

**Impact**: Harder to test configurations safely.

**Severity**: Medium (can mitigate with git + backup).

### 5. **No Cleanup of Old Symlinks**
**Issue**: Removing a link from config doesn't remove the symlink.

**Impact**: Manual cleanup required.

**Severity**: Low (explicit removal is arguably safer).

### 6. **Target Existence Not Validated**
**Issue**: Can create broken symlinks if target doesn't exist.

**Impact**: Broken symlinks in project.

**Mitigation**: Boomtube creates target directories for `kind: dir`, but files must pre-exist or be created by migration.

### 7. **No Hook System**
**Issue**: Can't run custom scripts before/after symlinking.

**Impact**: Need wrapper scripts for complex workflows.

**Example Use Case**: Running `git init` after migrating `.git`, or `python -m venv` after symlinking `.venv`.

### 8. **Single Config File**
**Issue**: No include/extends mechanism.

**Impact**: Can't compose configurations or share common patterns.

---

## 6. Integration with Devman

### Current Devman Context

Based on the repository's purpose (development environment management), likely use cases:

1. **Git Directory Management**: Relocate `.git` to shared cache
2. **Virtual Environments**: Symlink `.venv` to cache
3. **Cache Directories**: Symlink tool caches (`.ruff_cache`, `.pytest_cache`, etc.)
4. **Configuration Files**: Symlink persistent configs (`.env.local`, etc.)

### Proposed Integration Approach

#### Option A: Direct Integration (Recommended)
Use Boomtube as-is with `boomtube.yaml` in project roots.

**Setup**:
```yaml
# boomtube.yaml (in project template)
version: 1
vars:
  devman_cache: "/workspace/.devman-cache/{project_name}"

links:
  - name: "Git repository"
    link: .git
    target: "{devman_cache}/.git"
    kind: dir
    migrate: true

  - name: "Python venv"
    link: .venv
    target: "{devman_cache}/.venv"
    kind: dir
    migrate: false

  - name: "Ruff cache"
    link: .ruff_cache
    target: "{devman_cache}/.ruff_cache"
    kind: dir
    migrate: true
```

**Devman Workflow**:
```bash
# When initializing a project
devman init my-project
cd my-project
boomtube apply  # Called automatically by devman

# When cloning an existing project
devman clone <url>
cd <project>
boomtube apply  # Migrates existing .git to cache
```

**Pros**:
- Clean separation of concerns
- Leverage Boomtube's robustness
- Declarative configuration
- Easy to audit and modify

**Cons**:
- Additional dependency
- Users must understand Boomtube config
- No deep integration with devman logic

#### Option B: Embed Boomtube Library
Import Boomtube as a Python library within devman.

**Example**:
```python
from boomtube.config import load_config
from boomtube.apply import apply_all
from boomtube.resolve import build_context

def devman_setup_project(project_path: Path):
    config_path = project_path / "boomtube.yaml"
    if config_path.exists():
        cfg = load_config(config_path)
        ctx = build_context(project_path, cfg.vars)
        apply_all(project_path, cfg.links, ctx)
```

**Pros**:
- Tighter integration
- Can extend/customize behavior
- Single dependency install

**Cons**:
- More coupling
- Must maintain compatibility with Boomtube updates
- Need to handle Boomtube's exceptions

#### Option C: Fork & Customize
Fork Boomtube and add devman-specific features.

**Potential Enhancements**:
- Add OS-specific link support
- Environment variable interpolation
- Hook system for pre/post actions
- Dry-run mode
- Interactive conflict resolution

**Pros**:
- Full control
- Can tailor to devman's exact needs

**Cons**:
- Maintenance burden
- Divergence from upstream
- Duplication of effort

### Recommendation: **Option A** (Direct Integration)

**Rationale**:
1. Boomtube's current feature set covers 90% of use cases
2. Clean separation allows both projects to evolve independently
3. Workarounds exist for limitations
4. Can always switch to Option B or C later if needed

---

## 7. Migration Strategy

### Phase 1: Evaluation (Current)
- ✅ Analyze Boomtube capabilities
- ⬜ Create proof-of-concept `boomtube.yaml` for devman
- ⬜ Test on sample projects
- ⬜ Identify gaps

### Phase 2: Integration Design
- ⬜ Design devman + Boomtube interaction model
- ⬜ Create Boomtube config templates for common project types
- ⬜ Document symlinking strategy
- ⬜ Plan error handling

### Phase 3: Implementation
- ⬜ Add Boomtube as dependency
- ⬜ Create `devman init` integration
- ⬜ Create `devman clone` integration
- ⬜ Implement config generation
- ⬜ Add validation checks

### Phase 4: Testing
- ⬜ Unit tests for integration points
- ⬜ Integration tests with real projects
- ⬜ Edge case testing (existing dirs, broken symlinks, etc.)
- ⬜ Cross-platform testing

### Phase 5: Documentation & Rollout
- ⬜ User documentation for `boomtube.yaml` format
- ⬜ Migration guide for existing devman projects
- ⬜ Troubleshooting guide
- ⬜ Release notes

---

## 8. Risk Assessment

### High Risk ⚠️
None identified. Boomtube's non-destructive approach minimizes data loss risk.

### Medium Risk ⚡
1. **Migration Conflicts**: Timestamp ties create conflict copies.
   - **Mitigation**: Document conflict resolution process; conflicts are rare.

2. **Broken Symlinks**: Misconfigured targets lead to broken links.
   - **Mitigation**: Validate config in devman before calling Boomtube; provide clear error messages.

3. **Cross-Platform Path Issues**: Path separators, case sensitivity.
   - **Mitigation**: Use Boomtube's `normalize_path()`; test on all platforms.

### Low Risk ℹ️
1. **Dependency Updates**: Boomtube API changes.
   - **Mitigation**: Pin version; monitor releases.

2. **Performance**: Large directory migrations could be slow.
   - **Mitigation**: Document; consider progress indicators.

---

## 9. Alternatives Considered

### A. Custom Implementation
**Pros**: Full control, no dependencies
**Cons**: Reinvent the wheel, migration logic is complex

### B. GNU Stow
**Pros**: Battle-tested, simple
**Cons**: No migration, no variable system, Perl dependency

### C. Dotbot
**Pros**: Popular in dotfiles community
**Cons**: Less flexible, no migration, Python 2 legacy

### D. Shell Scripts
**Pros**: No dependencies, simple
**Cons**: Error-prone, no validation, no migration safety

**Verdict**: Boomtube provides the best balance of features, safety, and simplicity.

---

## 10. Open Questions

1. **Should devman auto-generate `boomtube.yaml` or require users to create it?**
   - Recommendation: Auto-generate with sensible defaults; allow user customization.

2. **How to handle projects without `boomtube.yaml`?**
   - Recommendation: Treat as no-op; optionally prompt user to create one.

3. **Should `.git` migration be opt-in or opt-out?**
   - Recommendation: Opt-in (via flag or config) for safety.

4. **How to handle Boomtube errors in devman context?**
   - Recommendation: Catch and wrap exceptions with devman-specific guidance.

5. **Should devman expose Boomtube CLI or wrap it?**
   - Recommendation: Expose directly (`devman symlink = boomtube apply`) for transparency.

---

## 11. Recommendations

### Immediate Actions
1. ✅ Create this analysis document
2. ⬜ Create proof-of-concept `boomtube.yaml` for a devman test project
3. ⬜ Test migration scenarios (existing `.git`, existing `.venv`)
4. ⬜ Document edge cases and workarounds

### Short-Term (1-2 weeks)
1. ⬜ Add Boomtube to devman dependencies
2. ⬜ Implement basic integration (`devman init` generates `boomtube.yaml`)
3. ⬜ Create test suite for integration
4. ⬜ Write user documentation

### Medium-Term (1-2 months)
1. ⬜ Gather user feedback on symlinking strategy
2. ⬜ Identify missing features and evaluate fork vs workaround
3. ⬜ Add CI/CD testing for symlink scenarios
4. ⬜ Create troubleshooting guide

### Long-Term (3-6 months)
1. ⬜ Contribute enhancements back to Boomtube (if forked)
2. ⬜ Explore advanced use cases (multi-project workspaces, shared caches)
3. ⬜ Consider deep integration (if Option B becomes preferable)

---

## 12. Conclusion

**Boomtube is an excellent fit for devman's symlinking needs.** Its declarative approach, intelligent migration, and robust safety features align well with devman's goals of managing development environments.

**Key Strengths**:
- ✅ Handles complex migration scenarios safely
- ✅ Declarative, version-controlled configuration
- ✅ Flexible variable system
- ✅ Idempotent and safe

**Acceptable Limitations**:
- ⚠️ No OS-specific conditionals (workaround: wrapper scripts)
- ⚠️ No environment variable support (workaround: shell integration)
- ⚠️ No dry-run mode (workaround: git + backups)

**Recommended Path**: Integrate Boomtube directly (Option A) with auto-generated configs for common scenarios. This provides immediate value with minimal maintenance burden while keeping options open for deeper integration later.

---

## Appendix A: Example Configs

### Minimal Python Project
```yaml
version: 1
vars:
  cache: "/workspace/.cache/{project_name}"

links:
  - link: .venv
    target: "{cache}/.venv"
    kind: dir
```

### Full-Featured Project
```yaml
version: 1
vars:
  workspace_cache: "/workspace/.cache/{project_name}"
  shared_configs: "/workspace/.shared-configs"

links:
  - name: "Git repository"
    link: .git
    target: "{workspace_cache}/.git"
    kind: dir
    migrate: true

  - name: "Python virtual environment"
    link: .venv
    target: "{workspace_cache}/.venv"
    kind: dir
    migrate: false

  - name: "Ruff cache"
    link: .ruff_cache
    target: "{workspace_cache}/.ruff_cache"
    kind: dir
    migrate: true

  - name: "Pytest cache"
    link: .pytest_cache
    target: "{workspace_cache}/.pytest_cache"
    kind: dir
    migrate: true

  - name: "Environment file"
    link: .env.local
    target: "{workspace_cache}/.env.local"
    kind: file
    migrate: true

  - name: "Shared ESLint config"
    link: .eslintrc.json
    target: "{shared_configs}/eslintrc.json"
    kind: file
    migrate: false
```

### Node.js Project
```yaml
version: 1
vars:
  cache: "/workspace/.cache/{project_name}"

links:
  - link: .git
    target: "{cache}/.git"
    kind: dir

  - link: node_modules
    target: "{cache}/node_modules"
    kind: dir

  - link: .next
    target: "{cache}/.next"
    kind: dir

  - link: .turbo
    target: "{cache}/.turbo"
    kind: dir
```

---

## Appendix B: Boomtube API Reference (for Library Integration)

### Key Functions

```python
# config.py
def load_config(config_path: Path) -> BoomtubeConfig:
    """Load and validate YAML config."""

# resolve.py
def build_context(project_root: Path, user_vars: dict[str, str] | None) -> dict[str, str]:
    """Build variable context with built-ins and user vars."""

# apply.py
def apply_all(project_root: Path, specs: list[LinkSpec], ctx: dict[str, str]) -> None:
    """Apply all link specs."""

def apply_link(project_root: Path, spec: LinkSpec, ctx: dict[str, str]) -> None:
    """Apply single link spec."""

# fsops.py
def symlink_to(link: Path, target: Path) -> None:
    """Create symlink."""

def is_symlink(path: Path) -> bool:
    """Check if path is a symlink."""

def normalize_path(path: Path, *, base: Path | None = None) -> Path:
    """Normalize path for comparison."""
```

### Exception Types
```python
from boomtube.config import ConfigError
from boomtube.resolve import VarResolutionError
```

### Usage Example
```python
from pathlib import Path
from boomtube.config import load_config, ConfigError
from boomtube.apply import apply_all
from boomtube.resolve import build_context, VarResolutionError

def devman_apply_symlinks(project_path: Path) -> None:
    config_path = project_path / "boomtube.yaml"

    try:
        cfg = load_config(config_path)
        ctx = build_context(project_path, cfg.vars)
        apply_all(project_path, cfg.links, ctx)
        print(f"✅ Applied {len(cfg.links)} symlinks")
    except ConfigError as e:
        print(f"❌ Config error: {e}")
        raise
    except VarResolutionError as e:
        print(f"❌ Variable error: {e}")
        raise
    except PermissionError as e:
        print(f"❌ Permission denied: {e}")
        raise
```

---

**Document Version**: 1.0
**Author**: Claude (AI Assistant)
**Last Updated**: 2026-02-05
