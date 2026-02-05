# DevMan Refactoring Guide

## Executive Summary

This guide describes the step-by-step refactoring of DevMan from a simple copier template management CLI tool into an opinionated development assistant built on a context-driven, template-based workflow enabled by watchdog and copier

### Current State
- Simple CLI tool for managing copier templates
- Finds `.devman` directories and manages template configurations
- Manual template application and updates

### Target State
- Automated development assistant using file system watching
- Creates copier template repos automatically when files match patterns
- Replaces files with symlinks to generated template outputs
- Self-refining templates through context accumulation
- Jujutsu-based workflow loops for template modifications
- Knowledge graph building over time
- `.devman/` directory symlink mirroring for workflow outputs

---

## Phase 1: Foundation & Core Architecture

### Step 1.1: Add Watchdog Dependency
**Goal**: Introduce file system monitoring capability

**Tasks**:
1. Add `watchdog>=3.0.0` to `pyproject.toml` dependencies
2. Add optional `jujutsu` CLI wrapper (via subprocess) for VCS operations
3. Update development dependencies for new testing requirements

**Files to modify**:
- `pyproject.toml`

**New dependencies**:
```toml
dependencies = [
    # ... existing ...
    "watchdog>=3.0.0",
]
```

---

### Step 1.2: Design `.devman/` Symlink Mirror System
**Goal**: Establish the `.devman/` directory structure for workflow outputs

**Core Concept**:
- Every directory in the managed repository gets a mirrored subdirectory inside `.devman/` at the repo root
- Example: `/project/src/components/` → `.devman/src/components/`
- Workflows can write outputs (summaries, logs, context) to their corresponding `.devman/` paths
- This creates a shadow file system for development metadata

**Tasks**:
1. Create `src/devman/domain/mirror.py` - handles symlink mirror logic
2. Create `src/devman/domain/watcher.py` - watchdog event handler base
3. Update `DevmanDirectory` model to support mirror paths

**New Domain Models**:
```python
# src/devman/domain/mirror.py
class MirrorManager:
    """Manages .devman/ directory mirroring for workflow outputs"""

    def ensure_mirror_path(self, source_path: Path) -> Path:
        """Create/return mirrored path in .devman/ for given source path"""

    def sync_structure(self, root: Path) -> None:
        """Sync directory structure into .devman/ mirror"""
```

**Files to create**:
- `src/devman/domain/mirror.py`
- `src/devman/domain/watcher.py`
- `tests/test_mirror.py`

---

### Step 1.3: Implement Template Pattern Matching
**Goal**: Detect when created files should trigger template generation

**Tasks**:
1. Create `src/devman/domain/patterns.py` for pattern matching logic
2. Define pattern configuration schema in `src/devman/schemas/patterns.py`
3. Support matching on: filename, location, file type, content patterns

**Pattern Configuration Schema**:
```yaml
# .devman/patterns.yaml
patterns:
  - name: "python-module"
    match:
      extension: ".py"
      location: "src/**/*.py"
      not_location: "**/tests/**"
    template:
      repo: "https://github.com/user/python-module-template"

  - name: "react-component"
    match:
      extension: ".tsx"
      location: "src/components/**/*.tsx"
    template:
      repo: "https://github.com/user/react-component-template"
```

**Files to create**:
- `src/devman/domain/patterns.py`
- `src/devman/schemas/patterns.py`
- `tests/test_patterns.py`

---

## Phase 2: Watchdog Integration

### Step 2.1: Implement File System Watcher
**Goal**: Monitor file system for create/modify/delete events

**Tasks**:
1. Create `src/devman/watcher/events.py` - watchdog event handlers
2. Create `src/devman/watcher/manager.py` - watcher lifecycle management
3. Implement event filtering to ignore `.devman/` and `.git/` directories

**Event Handler Flow**:
```
File Created → Match Patterns → Trigger Template Generation → Replace with Symlink
File Modified → Detect Symlink → Generate Diff → Queue Template Update Task
File Deleted → Cleanup Symlink → Archive in .devman/
```

**Files to create**:
- `src/devman/watcher/events.py`
- `src/devman/watcher/manager.py`
- `tests/test_watcher.py`

---

### Step 2.2: Template Repository Management
**Goal**: Automatically create and manage copier template repositories

**Tasks**:
1. Create `src/devman/templates/repository.py` - template repo operations
2. Implement automatic copier template repo creation
3. Store template repos in `.devman/templates/<pattern-name>/`
4. Initialize template repos with jujutsu (if available) or git

**Template Repo Structure**:
```
.devman/templates/
├── python-module/
│   ├── template/
│   │   └── {{ module_name }}.py.jinja
│   ├── copier.yaml
│   ├── .git/ or .jj/
│   └── context/
│       ├── docs/
│       ├── notes/
│       └── examples/
├── react-component/
│   └── ...
```

**Files to create**:
- `src/devman/templates/repository.py`
- `src/devman/templates/generator.py`
- `tests/test_template_repository.py`

---

### Step 2.3: File Symlink Replacement
**Goal**: Replace matched files with symlinks to template-generated outputs

**Tasks**:
1. Create `src/devman/domain/symlinks.py` - symlink operations
2. Implement safe file → symlink conversion
3. Store original file in `.devman/originals/` for backup
4. Generate file from template and symlink to it

**Workflow**:
```
1. User creates: src/components/Button.tsx
2. Matches pattern: "react-component"
3. Create template repo: .devman/templates/react-component/
4. Backup original: .devman/originals/src/components/Button.tsx.001
5. Generate from template: .devman/generated/src/components/Button.tsx
6. Replace with symlink: src/components/Button.tsx → ../../.devman/generated/src/components/Button.tsx
```

**Files to create**:
- `src/devman/domain/symlinks.py`
- `tests/test_symlinks.py`

---

## Phase 3: Context Accumulation & Refinement

### Step 3.1: Context Management System
**Goal**: Build context for template refinement

**Three Context Types**:

1. **Input Context**: User-provided documentation
   - Stored in: `.devman/templates/<pattern>/context/docs/`
   - Examples: API docs, style guides, examples

2. **Prodding Context**: Automated workflow loops
   - Stored in: `.devman/templates/<pattern>/context/workflows/`
   - Examples: Git hooks, CI outputs, linter results

3. **Validation Context**: Testing and selection
   - Stored in: `.devman/templates/<pattern>/context/validation/`
   - Examples: Test results, pick-best-of-N comparisons

**Tasks**:
1. Create `src/devman/context/manager.py` - context aggregation
2. Create `src/devman/context/types.py` - context type models
3. Implement context indexing for template generation

**Files to create**:
- `src/devman/context/manager.py`
- `src/devman/context/types.py`
- `src/devman/context/indexer.py`
- `tests/test_context.py`

---

### Step 3.2: Workflow Loop System
**Goal**: Enable automated template refinement through workflows

**Tasks**:
1. Create `src/devman/workflows/base.py` - workflow base classes
2. Create `src/devman/workflows/jujutsu.py` - jujutsu branch workflow
3. Implement workflow task queue
4. Create workflow for file edit → diff → template update

**Jujutsu Workflow**:
```
1. File edited (via symlink)
2. Generate diff
3. Create task: "Update template to incorporate diff"
4. Jujutsu: create new branch in template repo
5. Apply changes + run tests
6. If tests pass: merge, regenerate file
7. If tests fail: save results to context, retry
8. Send summary + merge request
```

**Files to create**:
- `src/devman/workflows/base.py`
- `src/devman/workflows/jujutsu.py`
- `src/devman/workflows/tasks.py`
- `tests/test_workflows.py`

---

### Step 3.3: Local LLM Integration
**Goal**: Use local models for simple summarization and context building

**Tasks**:
1. Create `src/devman/llm/client.py` - local LLM client (ollama/llamacpp)
2. Create `src/devman/llm/prompts.py` - prompt templates
3. Implement simple workflows:
   - Summarize directory contents
   - Generate questions about code
   - Combine multiple context sources
   - Extract patterns from examples

**Simple Workflows**:
- Directory summarizer: Creates markdown summary in `.devman/summaries/`
- Pattern extractor: Analyzes examples to suggest template patterns
- Question generator: Asks clarifying questions to build context
- Research consolidator: Combines context into guides

**Files to create**:
- `src/devman/llm/client.py`
- `src/devman/llm/prompts.py`
- `src/devman/llm/workflows.py`
- `tests/test_llm.py`

---

## Phase 4: Knowledge Graph Building

### Step 4.1: Trial & Error Logging
**Goal**: Record experiments and outcomes for knowledge building

**Tasks**:
1. Create `src/devman/knowledge/trials.py` - trial logging system
2. Store trials in `.devman/knowledge/trials/`
3. Record: attempt, outcome, context, timestamp
4. Enable workflow loops to record their iterations

**Trial Log Structure**:
```yaml
# .devman/knowledge/trials/python-module/001.yaml
trial_id: "001"
pattern: "python-module"
timestamp: "2026-02-04T10:30:00Z"
attempt:
  template_version: "abc123"
  context_used: ["docs/api.md", "examples/module1.py"]
  generated_file: "src/utils/parser.py"
outcome:
  tests_passed: false
  errors: ["Import error: missing typing module"]
  validation_score: 0.3
next_action: "Add typing to template dependencies"
```

**Files to create**:
- `src/devman/knowledge/trials.py`
- `src/devman/knowledge/analyzer.py`
- `tests/test_knowledge.py`

---

### Step 4.2: Knowledge Consolidation
**Goal**: Build "the way" of doing things from accumulated trials

**Tasks**:
1. Create `src/devman/knowledge/consolidator.py` - pattern extraction from trials
2. Use LLM to analyze trial logs and extract best practices
3. Generate development guides in `.devman/knowledge/guides/`
4. Update template configurations based on consolidated knowledge

**Consolidation Workflow**:
```
1. Accumulate N trials for a pattern
2. Local LLM analyzes trials
3. Extract common success patterns
4. Extract common failure patterns
5. Generate guide: "Python Module Best Practices"
6. Update template with learned patterns
7. Archive old template versions
```

**Files to create**:
- `src/devman/knowledge/consolidator.py`
- `src/devman/knowledge/guides.py`
- `tests/test_consolidation.py`

---

## Phase 5: CLI & Daemon Mode

### Step 5.1: Refactor CLI for Daemon Mode
**Goal**: Enable long-running watcher process

**Current CLI**: Single-shot commands
**New CLI**: Daemon mode + management commands

**New Commands**:
```bash
# Start daemon
devman watch [--daemon]

# Manage patterns
devman patterns list
devman patterns add <pattern-file>
devman patterns test <file-path>

# Manage templates
devman templates list
devman templates update <pattern-name>
devman templates context add <pattern> <context-file>

# Knowledge operations
devman knowledge trials <pattern>
devman knowledge consolidate <pattern>
devman knowledge guides

# Mirror operations
devman mirror sync
devman mirror clean
```

**Tasks**:
1. Refactor `src/devman/cli.py` for new command structure
2. Create `src/devman/daemon/manager.py` - daemon process management
3. Add PID file and signal handling
4. Implement graceful shutdown

**Files to modify**:
- `src/devman/cli.py`

**Files to create**:
- `src/devman/daemon/manager.py`
- `src/devman/daemon/signals.py`
- `tests/test_daemon.py`

---

### Step 5.2: Configuration Management
**Goal**: Unified configuration for all new features

**Configuration File**: `.devman/config.yaml`
```yaml
devman:
  version: "2.0.0"

  # Watcher settings
  watcher:
    enabled: true
    ignore_patterns: [".git/*", ".devman/*", "node_modules/*"]

  # Pattern matching
  patterns:
    config_file: ".devman/patterns.yaml"
    auto_reload: true

  # Template settings
  templates:
    storage: ".devman/templates/"
    vcs: "jujutsu"  # or "git"
    auto_update: true

  # Mirror settings
  mirror:
    enabled: true
    auto_sync: true

  # LLM settings
  llm:
    provider: "ollama"  # or "llamacpp"
    model: "llama2"
    endpoint: "http://localhost:11434"

  # Knowledge settings
  knowledge:
    trials_storage: ".devman/knowledge/trials/"
    guides_storage: ".devman/knowledge/guides/"
    consolidate_after_trials: 10
```

**Tasks**:
1. Create `src/devman/schemas/config.py` - pydantic config schema
2. Update `src/devman/config.py` for new settings
3. Add configuration validation and migration

**Files to modify**:
- `src/devman/config.py`

**Files to create**:
- `src/devman/schemas/config.py`
- `tests/test_config_v2.py`

---

## Phase 6: Testing & Migration

### Step 6.1: Comprehensive Testing
**Goal**: Ensure all new components work together

**Test Categories**:
1. **Unit Tests**: Each new module
2. **Integration Tests**: Watchdog → Template → Symlink flow
3. **End-to-End Tests**: Full workflow from file creation to template refinement
4. **Performance Tests**: Handle large repositories efficiently

**Tasks**:
1. Create integration test suite
2. Create E2E test scenarios
3. Add performance benchmarks
4. Update CI/CD pipeline

**Files to create**:
- `tests/integration/test_watch_workflow.py`
- `tests/integration/test_template_workflow.py`
- `tests/e2e/test_full_lifecycle.py`
- `tests/performance/test_large_repo.py`

---

### Step 6.2: Migration Path for Existing Users
**Goal**: Smooth transition from v1 to v2

**Migration Strategy**:
1. Detect v1 `.devman` directories
2. Offer migration command: `devman migrate`
3. Convert existing templates to new structure
4. Generate default patterns from existing usage
5. Preserve backward compatibility for basic operations

**Tasks**:
1. Create `src/devman/migration/v1_to_v2.py`
2. Implement detection and conversion logic
3. Create migration guide documentation

**Files to create**:
- `src/devman/migration/__init__.py`
- `src/devman/migration/v1_to_v2.py`
- `docs/MIGRATION_V1_TO_V2.md`
- `tests/test_migration.py`

---

## Phase 7: Documentation & Polish

### Step 7.1: Comprehensive Documentation
**Goal**: Document the new system thoroughly

**Documentation Structure**:
```
docs/
├── README.md - Overview and quick start
├── ARCHITECTURE.md - System architecture
├── PATTERNS.md - Pattern matching guide
├── TEMPLATES.md - Template creation guide
├── WORKFLOWS.md - Workflow system guide
├── KNOWLEDGE.md - Knowledge graph system
├── LLM.md - LLM integration guide
└── examples/
    ├── python-project/
    ├── react-app/
    └── monorepo/
```

**Tasks**:
1. Write architectural overview
2. Create pattern configuration examples
3. Document template creation best practices
4. Provide workflow examples
5. Create video tutorials (optional)

---

### Step 7.2: Example Templates & Patterns
**Goal**: Provide starter templates for common use cases

**Starter Templates**:
1. Python module template
2. Python test file template
3. React component template
4. Markdown documentation template
5. Configuration file template

**Tasks**:
1. Create example templates in `examples/templates/`
2. Create example patterns in `examples/patterns/`
3. Test examples in realistic scenarios

**Files to create**:
- `examples/templates/python-module/`
- `examples/templates/react-component/`
- `examples/patterns/python-patterns.yaml`
- `examples/patterns/javascript-patterns.yaml`

---

## Implementation Timeline & Priorities

### Priority 1: Core Foundation (Weeks 1-2)
- [ ] Phase 1.1: Add dependencies
- [ ] Phase 1.2: Implement mirror system
- [ ] Phase 1.3: Pattern matching
- [ ] Phase 2.1: Basic watchdog integration

**Success Criteria**: Can watch directory and detect file creation patterns

### Priority 2: Automation Loop (Weeks 3-4)
- [ ] Phase 2.2: Template repository management
- [ ] Phase 2.3: Symlink replacement
- [ ] Phase 3.1: Basic context management

**Success Criteria**: Creating a file triggers template generation and symlink replacement

### Priority 3: Intelligence (Weeks 5-6)
- [ ] Phase 3.2: Workflow loops
- [ ] Phase 3.3: Local LLM integration
- [ ] Phase 4.1: Trial logging

**Success Criteria**: Templates improve based on usage and feedback

### Priority 4: Knowledge & CLI (Weeks 7-8)
- [ ] Phase 4.2: Knowledge consolidation
- [ ] Phase 5.1: Daemon mode CLI
- [ ] Phase 5.2: Configuration management

**Success Criteria**: System learns and generates best practice guides

### Priority 5: Polish (Weeks 9-10)
- [ ] Phase 6.1: Comprehensive testing
- [ ] Phase 6.2: Migration tools
- [ ] Phase 7.1: Documentation
- [ ] Phase 7.2: Example templates

**Success Criteria**: Production-ready with docs and examples

---

## Files to Keep vs. Remove

### Files to Keep (Core Domain Logic)
- ✅ `src/devman/domain/models.py` - Core models (DevmanDirectory, ProjectRoot)
- ✅ `src/devman/domain/finder.py` - Directory finding logic
- ✅ `src/devman/domain/protocols.py` - Interface definitions
- ✅ `src/devman/constants.py` - Constants
- ✅ `pyproject.toml` - Project metadata
- ✅ `README.md` - Project overview (update for v2)

### Files to Refactor Heavily
- 🔄 `src/devman/cli.py` - Expand for daemon mode
- 🔄 `src/devman/config.py` - Expand for new configuration
- 🔄 `src/devman/schemas/` - Add new schemas

### Files to Archive (Legacy)
- 📦 `src/devman/application/use_cases.py` - Replace with workflows
- 📦 `src/devman/templates.py` - Replace with template repository system
- 📦 `src/devman/domain/templates.py` - Replace with new template system

### Files to Remove (Obsolete)
- ❌ Most existing test files - Replace with new test architecture
- ❌ `MIGRATION.md` - Superseded by new migration guide
- ❌ `scripts/generate_example.py` - Replaced by template system
- ❌ `scripts/validate_copier.py` - Built into workflow system

---

## Risk Mitigation

### Technical Risks

**Risk**: Watchdog performance issues on large repositories
- **Mitigation**: Implement smart filtering, debouncing, and selective watching

**Risk**: Symlink compatibility across platforms
- **Mitigation**: Test on Windows/Mac/Linux, provide fallback mechanisms

**Risk**: Template generation failures
- **Mitigation**: Always backup originals, provide rollback mechanism

**Risk**: Local LLM availability/performance
- **Mitigation**: Make LLM features optional, degrade gracefully

### User Experience Risks

**Risk**: Automatic file replacement feels invasive
- **Mitigation**: Provide opt-in mode, clear user communication, easy disable

**Risk**: Learning curve too steep
- **Mitigation**: Excellent documentation, simple starter patterns, progressive disclosure

**Risk**: Breaking existing workflows
- **Mitigation**: Careful migration path, backward compatibility layer

---

## Success Metrics

### Technical Metrics
- ⏱️ File creation → template generation < 2 seconds
- 🎯 Pattern matching accuracy > 95%
- 💾 Memory usage < 100MB in daemon mode
- 🔄 Template refinement convergence in < 10 iterations

### User Experience Metrics
- 📚 Time to first working template < 5 minutes
- 😊 User satisfaction with automation
- 🎓 Learning curve reduction (subjective)
- 🚀 Development velocity increase

### Knowledge Metrics
- 📈 Guide quality improves over time
- 🎯 Template success rate increases
- 📊 Context relevance scores
- 🔬 Trial-to-success ratio decreases

---

## Next Steps

1. **Review this guide** with stakeholders
2. **Prioritize phases** based on team capacity
3. **Set up development environment** with watchdog and jujutsu
4. **Create feature branch** for Phase 1 work
5. **Begin implementation** following priority order
6. **Iterate rapidly** with user feedback

---

## Appendix: .devman/ Directory Structure

```
.devman/
├── config.yaml                    # Main configuration
├── patterns.yaml                  # Pattern matching rules
├── devenv.yaml                    # Development environment (existing)
├── devenv.nix                     # Nix config (existing)
│
├── templates/                     # Template repositories
│   ├── python-module/
│   │   ├── template/
│   │   ├── copier.yaml
│   │   ├── .jj/ or .git/
│   │   └── context/
│   │       ├── docs/
│   │       ├── notes/
│   │       ├── workflows/
│   │       └── validation/
│   └── react-component/
│       └── ...
│
├── generated/                     # Template-generated files
│   ├── src/
│   │   └── components/
│   │       └── Button.tsx        # Actual generated file
│   └── ...
│
├── originals/                     # Backup of replaced files
│   └── src/
│       └── components/
│           └── Button.tsx.001
│
├── knowledge/                     # Knowledge graph data
│   ├── trials/
│   │   ├── python-module/
│   │   │   ├── 001.yaml
│   │   │   └── 002.yaml
│   │   └── react-component/
│   │       └── ...
│   └── guides/
│       ├── python-best-practices.md
│       └── react-component-patterns.md
│
├── workflows/                     # Workflow outputs
│   ├── tasks.db                  # Task queue
│   └── logs/
│       └── 2026-02-04.log
│
└── <mirrored-structure>/         # Mirrored repo structure
    ├── src/
    │   └── components/
    │       └── summaries/        # Workflow outputs
    │           └── overview.md
    └── docs/
        └── notes/
            └── architecture.md
```

This structure supports the entire workflow system while keeping development metadata organized and accessible.
