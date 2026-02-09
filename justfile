set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set script-interpreter := ["bash", "-eu", "-o", "pipefail"]

test-branch:
    git rev-parse --abbrev-ref HEAD

[script]
test-output-dir:
    root="$(git rev-parse --show-toplevel)"
    branch="$(just --quiet test-branch)"
    output_base="$root/tests/output/$branch"
    mkdir -p "$output_base"

    last="$(ls -1 "$output_base" 2>/dev/null | rg '^[0-9]{5}$' | sort | tail -n 1 || true)"
    if [ -z "$last" ]; then
    next="00001"
    else
    next="$(printf "%05d" "$((10#$last + 1))")"
    fi

    output_dir="$output_base/$next"
    mkdir -p "$output_dir"
    printf "%s\n" "$output_dir"

[script]
test-run:
    output_dir="$(just --quiet test-output-dir)"
    pytest | tee "$output_dir/pytest.log"

devenv-test:
    just test-run

# Generate a file-type seed template instance with asciinema recording.
# Usage: just entrypoint [config_file]
#   config_file  Path to a TOML config (default: sample-config.toml)
entrypoint config="sample-config.toml":
    entrypoint "{{ config }}"
