import json
import subprocess
from pathlib import Path


def test_parse_config_outputs_json_for_shell_safe_consumption(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
[file_type_template]
file_type = "pyproject.toml"
description = "Python project configuration"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["python", "scripts/parse-config.py", str(config)],
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)

    assert payload == {
        "file_type": "pyproject.toml",
        "description": "Python project configuration",
    }


def test_json_parse_flow_preserves_punctuation_and_apostrophes(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    description = "Python project's config: punctuation, spaces, and commas!"
    config.write_text(
        f"""
[file_type_template]
file_type = "pyproject.toml"
description = {json.dumps(description)}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    bash_snippet = r'''
set -euo pipefail
config_json="$(python scripts/parse-config.py "$1")"
mapfile -t parsed < <(python - "$config_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
print(payload["file_type"])
print(payload.get("description", ""))
PY
)
file_type="${parsed[0]}"
description="${parsed[1]}"
printf '%s\n%s\n' "$file_type" "$description"
'''

    proc = subprocess.run(
        ["bash", "-c", bash_snippet, "--", str(config)],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = proc.stdout.splitlines()

    assert lines == ["pyproject.toml", description]
