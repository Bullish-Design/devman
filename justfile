DEVMAN_DIR := env_var_or_default("DEVMAN_DIR", ".devman")

default: help

help:
    #!/usr/bin/env bash
    set -euo pipefail
    just --list

container-create:
    #!/usr/bin/env bash
    set -euo pipefail
    devman_dir="{{DEVMAN_DIR}}"
    ./devman.py init --devman-dir "$devman_dir"

container-test:
    #!/usr/bin/env bash
    set -euo pipefail
    ./devman.py test

container-clean:
    #!/usr/bin/env bash
    set -euo pipefail
    ./devman.py clean --dry-run

container-shell:
    #!/usr/bin/env bash
    set -euo pipefail
    devman_dir="{{DEVMAN_DIR}}"
    if [[ ! -d "$devman_dir" ]]; then
        echo "DevMan directory '$devman_dir' does not exist. Run 'just container-create' first." >&2
        exit 1
    fi
    exec "${SHELL:-bash}"

container-list:
    #!/usr/bin/env bash
    set -euo pipefail
    devman_dir="{{DEVMAN_DIR}}"
    if [[ -d "$devman_dir" ]]; then
        ls -al "$devman_dir"
    else
        echo "DevMan directory '$devman_dir' does not exist."
    fi

container-clean-all:
    #!/usr/bin/env bash
    set -euo pipefail
    ./devman.py clean --all
