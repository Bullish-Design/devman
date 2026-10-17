# Contract lane results

Focused contract tests: 38 passed, including real Dagu validation.

Full unit run before integration: 151 passed, 14 failed, 8 deselected. Failures came from existing fixtures outside this lane that omit `queue`, or prepend a queue before the new explicit queue fixture. The contract now refuses those sources as required.
