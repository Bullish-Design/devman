# Migration Guide: v0.1.0 to v0.2.0

## Breaking Changes

### 1. TemplateValidator Returns Structured Results

**Before:**
```python
issues = TemplateValidator.validate(ref)
# issues: dict[str, list[str]]
if issues["errors"]:
    for error in issues["errors"]:
        print(error)
```

**After:**
```python
result = TemplateValidator.validate_typed(ref)
# result: ValidationResult
if not result.is_valid:
    for error in result.errors:
        print(f"{error.message} at {error.location}")
```

### 2. TemplateReference.create() Returns Result

**Before:**
```python
try:
    ref = TemplateReference(source_type="file", location=path)
except ValueError as e:
    handle_error(e)
```

**After:**
```python
result = TemplateReference.create("file", path)
if result.is_err():
    handle_error(result.unwrap_err())
else:
    ref = result.unwrap()
```

### 3. CopierConfig.questions Is Now Typed

**Before:**
```python
config.questions["name"]  # type: Any
```

**After:**
```python
config.questions["name"]  # type: Question (typed when loaded via from_yaml_file)
# Can use isinstance() for type checking:
if isinstance(config.questions["name"], StrQuestion):
    default = config.questions["name"].default
```

## Backward Compatibility

The following are maintained for backward compatibility but deprecated:

- `TemplateReference.from_string()` - Use `create()` instead
- `TemplateValidator.validate()` - Use `validate_typed()` instead
- `TemplateValidator.validate_structure()` - Use `validate_structure_typed()` instead
- `CopierConfig.validate_questions()` - Use `validate_questions_structured()` instead
- `devman.cli.DevmanFinder` - Use `devman.domain.finder.DevmanFinder` instead

## New Features

- Structured error types in `devman.domain.errors`
- Use cases in `devman.application.use_cases`
- Value objects in `devman.domain.models`
- Domain finder in `devman.domain.finder`
- `parse_question()` function for type-safe question parsing
