# Project 038 dual projection comparison — 2026-09-12

## Scope

This comparison used the compatibility registry at
`$HOME/.local/share/devman` and active plane generation 2 at
`$HOME/.local/state/vendomat/devman/active`.

The old registry has 51 metadata projects. The active plane has 46. The 46
active projects are exactly the intersection. The old-only metadata projects
are:

`copyroom`, `docman`, `fleetman`, `flora-037-part-e`, and `mypi-agent`.

The old DAG directory also has three broken `my-ai` symlinks without a matching
metadata project. They are stale compatibility output, not a project in the
comparison set.

## Results by dimension

| Dimension | Result | Decision |
|---|---|---|
| Project identity | 46 of 46 exact | No mismatch. |
| Project path | 46 of 46 exact | No mismatch. |
| Groups | 46 of 46 exact | No mismatch. `observantic` remains `base`, `release`. |
| Workflow identity | 146 generated names exact | Devman metadata is represented differently: old metadata stores group workflows plus a separate `local` list; plane metadata records overlay workflows in the workflow map. The generated identity is unchanged. Intentional. |
| Source identity | Generated bodies exact | Old sources use Nix store paths. Plane sources use relative policy paths or absolute central overlay paths. The source comment is the only generated-file difference. Intentional. |
| Policy identity | 46 expected changes | Old metadata records a Nix plan store path. Plane metadata records `plane:2`. This is the generation identity. Intentional. |
| Parameters and defaults | Exact in generated DAGs | No mismatch. |
| Trigger mappings | 46 of 46 exact | No mismatch. |
| Generated Dagu content | 146 of 146 match | `diff` matched every file after replacing only line 3, the generated source-file comment. |
| Working and log paths | Exact in generated DAGs | No mismatch. Every generated DAG has its project `working_dir` and `.devman/.runs/logs` path. |
| Queue names and limits | Exact for all 146 common DAGs | Aggregate differences in the old root are only the five old-only projects: 10 `light` and 5 `normal` DAGs. |
| Schedule fields | Exact for all common DAGs | The common set has 46 `maintain` schedules at `5 0 * * *` and Devman’s `plane-report` at `20 0 * * *`. |
| Run output and metadata | Projection body and run paths exact | The machine base handler remains unchanged. The existing VM proof covers `metadata.jsonl` and log recording. This read-only sweep did not launch a new repository task. |

## Exact commands

Project metadata was compared with:

```sh
python - <<'PY'
from pathlib import Path
import json

old_root = Path.home()/".local/share/devman/projects"
new_root = Path.home()/".local/state/vendomat/devman/active/projects"
old = {p.name: json.loads((p/"metadata.json").read_text())
       for p in old_root.iterdir() if (p/"metadata.json").is_file()}
new = {p.name: json.loads((p/"metadata.json").read_text())
       for p in new_root.iterdir() if (p/"metadata.json").is_file()}
common = sorted(old.keys() & new.keys())
assert len(common) == 46
for field in ("project", "path", "groups", "local", "triggers", "writes"):
    assert all(old[n].get(field) == new[n].get(field) for n in common), field
PY
```

Generated files were compared with:

```sh
diff -q \
  <(sed '3s@.*@#   <normalized source file>@' "$OLD_DAG") \
  <(sed '3s@.*@#   <normalized source file>@' "$NEW_DAG")
```

The full loop returned:

```text
normalized_dag_matches=146 normalized_dag_mismatches=0 old_only_dags=15
```

The 15 old-only regular DAGs belong to the five old-only metadata projects.

## Gate decision

There are no unexplained projection mismatches in the 46-project intersection.
The five old-only projects and the three broken `my-ai` links remain explicit
compatibility-state findings. Their removal requires the migration decisions
recorded in `MIGRATION_2026-09-12.md` and a later cleanup phase.
