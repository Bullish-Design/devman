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
    just eval-seed-templates
    just test-run

[script]
eval-seed-templates:
    root="$(git rev-parse --show-toplevel)"
    required=(
      "$root/src/devman/seed_templates/file-type/copier.yml"
      "$root/src/devman/seed_templates/devenv.nix/copier.yml"
      "$root/src/devman/seed_templates/python/copier.yml"
      "$root/src/devman/seed_templates/python/{{project_name}}/pyproject.toml.jinja"
      "$root/src/devman/seed_templates/python/{{project_name}}/src/{{package_name}}/__main__.py.jinja"
    )

    for path in "${required[@]}"; do
      if [ ! -f "$path" ]; then
        echo "Missing seed template asset: $path" >&2
        exit 1
      fi
    done

    echo "Seed template assets validated"

# Generate a file-type seed template instance with asciinema recording.
# Usage: just entrypoint [config_file]
#   config_file  Path to a TOML config (default: sample-config.toml)
[script]
entrypoint config="sample-config.toml":
    root="$(git rev-parse --show-toplevel)"
    cd "$root"

    config="{{ config }}"

    if [ ! -f "$config" ]; then
      echo "Error: config file not found: $config" >&2
      exit 1
    fi

    # ── Parse answers from the TOML config ──────────────────────────
    eval "$(uv run scripts/parse-config.py "$config")"

    template_name="file-type"
    template_src="src/devman/seed_templates/$template_name"

    if [ ! -d "$template_src" ]; then
      echo "Error: seed template not found: $template_src" >&2
      exit 1
    fi

    # ── Build timestamped output directory ──────────────────────────
    timestamp="$(date +%y%m%d%H%M%S)"
    output_dir="output/$template_name/$timestamp"
    term_dir="$output_dir/.term"

    mkdir -p "$term_dir"

    echo "──────────────────────────────────────────────"
    echo " template  : $template_name"
    echo " file_type : $file_type"
    echo " output    : $output_dir"
    echo " recording : $term_dir/session.cast"
    echo "──────────────────────────────────────────────"

    # ── Generate the template instance inside an asciinema session ──
    asciinema rec "$term_dir/session.cast" --command "
      set -e
      echo 'Generating $template_name instance for file_type=$file_type ...'
      copier copy --defaults \
        --data file_type='$file_type' \
        --data description='$description' \
        '$template_src' '$output_dir'
      echo
      echo 'Generated files:'
      find '$output_dir' -not -path '*/.term/*' -not -path '*/.term' | sort
      echo
      echo 'Done.'
    "

    echo
    echo "Instance saved to: $output_dir"
    echo "Recording saved to: $term_dir/session.cast"
