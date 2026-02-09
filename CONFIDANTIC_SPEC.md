# Confidantic Specification

## 1. Purpose

**Confidantic** is a centralized configuration manager for Devman environments built as small modular components in `devenv.sh`-driven systems.

It provides:

- A Python library with Pydantic-powered config models.
- A strict, ergonomic parsing layer for `.toml` and `.jsonl` files.
- A shared base class (`BaseConfig`) for reusable validation, environment integration, and Devman-aware defaults.
- A convention-first layout rooted at:

```
<project>/.devman/.config/
```

Confidantic is intended to be the default config substrate for Devman templates, instances, and helper libraries.

---

## 2. Goals and non-goals

### Goals

1. **Single source of configuration truth** for Devman-managed project components.
2. **Composable modular configs** suitable for `devenv.sh` component composition.
3. **Typed validation** using Pydantic models with clear error output.
4. **Safe defaults** with deterministic behavior and explicit merge rules.
5. **Devman integration** for run metadata, store paths, and template/instance awareness.
6. **Low-friction reuse** through a standard `BaseConfig` class.

### Non-goals

1. Replacing `just` as task execution interface.
2. Replacing Devman’s store model, instance model, or symlink strategy.
3. Building an imperative config mutation daemon.

---

## 3. Design constraints (inherits Devman core principles)

1. **Just-first remains mandatory**: Confidantic config is consumed by tasks invoked via `just`.
2. **Store-authoritative design**: runtime state still belongs in Devman store locations; repo-local `.devman/.config/` is config definition and local consumption surface.
3. **Idempotent reads/parsing**: loading config must not mutate files.
4. **Safe by default**: strict schema validation and explicit override semantics.
5. **Works without `jj`** but can capture `jj` context when available.

---

## 4. Filesystem contract

All Confidantic-managed configuration lives under:

```
.devman/.config/
```

Recommended layout:

```
.devman/.config/
  confidantic.toml                 # root registry + policy
  profiles/
    default.toml                   # base profile
    local.toml                     # developer-local overrides (optional, usually gitignored)
    ci.toml                        # CI-specific profile
  modules/
    devman.toml                    # devman-specific settings
    run_capture.toml               # logging/artifact capture behavior
    tooling.toml                   # tool-level settings (linters/formatters/etc.)
  data/
    allowlists.jsonl               # line-delimited records
    routes.jsonl                   # line-delimited records
```

### Reserved paths

- `.devman/.config/confidantic.toml`
- `.devman/.config/profiles/`
- `.devman/.config/modules/`
- `.devman/.config/data/`

No other Devman subsystem should claim these names for incompatible formats.

---

## 5. Data model and schema system

Confidantic is built on a core class hierarchy:

- `BaseConfig` (abstract reusable base)
- `TomlConfig(BaseConfig)`
- `JsonlConfig(BaseConfig)`
- Domain configs (e.g. `DevmanConfig`, `RunCaptureConfig`, `ToolingConfig`)

### 5.1 `BaseConfig` required capabilities

`BaseConfig` must provide:

1. **Load helpers**
   - `from_file(path)`
   - `from_mapping(mapping)`
   - `from_env(prefix=...)` (optional merge layer)
2. **Validation helpers**
   - schema-level validation with rich error context
   - cross-field validation hooks
3. **Merge helpers**
   - deterministic merge order (base < profile < env < explicit override)
   - explicit deep merge policy with list behavior defined per field
4. **Introspection helpers**
   - `model_fingerprint()` for cache keys
   - `to_redacted_dict()` for safe logging
5. **Devman context hooks**
   - path resolution helpers for project root / `.devman/.config`
   - run context injection (run id, simulate mode, store paths)

### 5.2 TOML parsing

- TOML files are parsed as structured config modules.
- Unknown-key behavior should be configurable per model:
  - strict (for core modules)
  - permissive (for extension modules)
- Validation errors must include:
  - file path
  - field path
  - expected type/rule

### 5.3 JSONL parsing

- JSONL files represent record collections.
- Each line is parsed into a typed record model.
- Parser must emit stable line-indexed error messages.
- Optional mode: skip invalid lines with warnings; default mode: fail-fast.

---

## 6. Configuration composition model

Confidantic uses layered composition:

1. **Root registry** (`confidantic.toml`) defines active modules and profile selection strategy.
2. **Profile layer** (`profiles/*.toml`) provides environment- or context-specific defaults.
3. **Module layer** (`modules/*.toml`) provides domain-specific schemas.
4. **Data layer** (`data/*.jsonl`) provides record-oriented extensions.
5. **Env/CLI overrides** applied last (explicitly declared keys only).

### Deterministic precedence

Lowest to highest:

1. module defaults (coded)
2. module files
3. selected profile
4. environment overrides
5. runtime explicit overrides

Every resolved configuration should be serializable to a normalized snapshot for debugging.

---

## 7. Devman integration points

Confidantic should expose first-class integration for Devman workflows.

### 7.1 Template + instance awareness

- Resolve `.devman/.config` whether `.devman` is a symlink into store or local directory.
- Preserve compatibility with store-authoritative instance layouts.

### 7.2 Run metadata compatibility

Provide utilities to emit config provenance into run metadata (`meta.json`), such as:

- resolved profile name
- loaded module paths
- config fingerprint/hash
- parse/validation timestamp

### 7.3 Just-first runtime handoff

Confidantic can produce a resolved env projection (e.g., `DEVMAN_*` vars), but execution remains:

```bash
just <recipe>
```

No alternate task runner is introduced.

---

## 8. Python package API (proposed)

```python
from confidantic import BaseConfig, load_config, load_jsonl_records
from confidantic.models import DevmanConfig, RunCaptureConfig
```

### Core functions

- `load_config(name: str, profile: str | None = None) -> BaseConfig`
- `load_config_bundle(profile: str | None = None) -> ConfigBundle`
- `load_jsonl_records(path: Path, record_model: type[T]) -> list[T]`
- `discover_config_root(start: Path | None = None) -> Path`

### Expected behavior

- All APIs default to `.devman/.config` discovery.
- Callers can override root for tests/fixtures.
- Errors are typed (`ConfigNotFound`, `ConfigValidationError`, `ConfigMergeError`).

---

## 9. Validation and safety policies

1. **No silent fallback on malformed core config**.
2. **Unknown critical keys fail in strict modules**.
3. **Redaction support** for secrets before logging.
4. **Path normalization** to avoid ambiguous relative path handling.
5. **Schema version field** in `confidantic.toml` for forward migration.

Example root file:

```toml
schema_version = 1
profile = "default"
modules = ["devman", "run_capture", "tooling"]
strict = true
```

---

## 10. CUE interop and research track

Confidantic should maintain a near-term research track around **CUELang** integration, especially given Devman’s modular `devenv.sh` usage patterns.

### 10.1 Research note

- Evaluate CUELang as a schema/export layer alongside Pydantic.
- Explore generation of `.cue` definitions directly from Confidantic Pydantic models.
- Assess where CUE adds value for cross-tool configuration publication and validation in mixed ecosystems.

### 10.2 Proposed interop shape

1. Pydantic models remain the Python runtime source for in-process validation.
2. A generated CUE layer mirrors selected model schemas.
3. Simple CLI + `just` recipes can export derived config targets (`json`, `yaml`, and other required artifacts) from CUE when needed.

### 10.3 devenv integration expectations

- Since this system runs in `devenv.sh` contexts, ensure CUE tooling can be declared in development environments where this interop is enabled.
- Keep CUE optional at first (feature-flagged or profile-gated), then promote if reliability and ergonomics prove strong.
- Document conversion boundaries (what is guaranteed round-trippable vs one-way export).

---

## 11. Minimal bootstrap for new components

Any new Devman library/component should be able to:

1. Depend on Confidantic.
2. Subclass `BaseConfig` for module-specific schema.
3. Read `.devman/.config` with one call.
4. Receive validated values + helper methods (paths, redacted output, fingerprints).

This enables consistent “from the jump” integration with Devman config patterns.

---

## 12. Test strategy

Confidantic should ship with tests covering:

1. **TOML schema validation** (valid, invalid, unknown keys).
2. **JSONL parsing** (line-level error reporting).
3. **Merge precedence correctness**.
4. **Idempotent loading** (same inputs => same outputs/fingerprint).
5. **Symlink-aware config root discovery**.
6. **Devman metadata projection** into run `meta.json` payloads.

Fixture strategy:

- Include fixture repos with `.devman` symlinked and non-symlinked variants.
- Include sample `devenv.sh` modular compositions that import Confidantic-backed settings.

---

## 13. Migration and adoption plan

### Phase 1: Introduce library and spec

- Add Confidantic package/module with `BaseConfig` and parser primitives.
- Add docs + examples using `.devman/.config` contract.

### Phase 2: Opt-in integration

- Add optional loading in Devman components that currently parse ad hoc TOML.
- Emit compatibility warnings for legacy config locations.

### Phase 3: Standardize

- Make Confidantic the default path for new templates/components.
- Publish schema conventions for shared module names and fields.

---

## 14. Documentation requirements

When implementing Confidantic:

1. Add developer docs describing extension via `BaseConfig`.
2. Add template docs showing expected `.devman/.config` structure.
3. Add operational docs for profile selection and override semantics.
4. Include troubleshooting section with representative validation failures.

---

## 15. Acceptance criteria

Confidantic is ready when:

1. A component can load validated config from `.devman/.config` with no ad hoc parsing.
2. `.toml` and `.jsonl` parsing are both typed and tested.
3. Error output is actionable (path + field/line + reason).
4. Integration preserves Devman principles (just-first, store-authoritative, idempotent/safe).
5. At least one fixture demonstrates end-to-end usage in a modular `devenv.sh` setup.
