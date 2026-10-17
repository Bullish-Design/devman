# Agent C evidence

The initial command ran against the pre-refactor implementation:

```text
uv run --frozen pytest tests/test_review_048_health.py tests/e2e/test_review_048_dagu.py -q
```

It failed six tests. The failures reproduce F1 to F4:

- F1: compile accepted `working_dir` and replaced the published DAG.
- F2: compile accepted a base without the required exit handler.
- F3: compile accepted `queue: ghost` in the base.
- F4: status and doctor stayed green after a broken manifest or base.
- F4: status and doctor stayed green after workflow input changed.

The complete initial output is in `initial-failures.txt`. These tests are
expected to pass after the contract, base, and compile-health lanes land.
