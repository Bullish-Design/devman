#!/usr/bin/env bash
set -euo pipefail

DEVMAN_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

tmp_dir="$(mktemp -d)"

cleanup() {
    just -f "$DEVMAN_PATH/justfile" container-clean-all >/dev/null 2>&1 || true
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

"$DEVMAN_PATH/devman.py" --help | rg "DevMan CLI for managing local development environments."

"$DEVMAN_PATH/devman.py" init \
    --devman-dir "$tmp_dir/.devman" \
    --template "python-devenv" \
    --project-name "test-project"

"$DEVMAN_PATH/devman.py" validate --devman-dir "$tmp_dir/.devman"

"$DEVMAN_PATH/devman.py" clean --devman-dir "$tmp_dir/.devman" --dry-run

"$DEVMAN_PATH/devman.py" clean --devman-dir "$tmp_dir/.devman" --all

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n "$DEVMAN_PATH/devman.py" test --devman-dir "$tmp_dir/.devman"
fi
