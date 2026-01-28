set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# devenv.nix defines the stable command interfaces; this Justfile is the
# experimentation layer for test workflows and output tweaks.

devman *args:
    uv sync
    devman {{args}}

test *args:
    uv sync --extra dev
    pytest {{args}}

test-branch:
    git rev-parse --abbrev-ref HEAD

test-output-dir:
    root="$(git rev-parse --show-toplevel)"
    branch="$(just test-branch)"
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

test-run:
    output_dir="$(just test-output-dir)"
    pytest | tee "$output_dir/pytest.log"

devenv-test:
    just test-run
