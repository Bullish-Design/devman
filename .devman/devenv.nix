{ pkgs, config, ... }:

let
  root = config.git.root;
in
{
  packages = with pkgs; [
    git
    jujutsu
    jq
    ripgrep
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    directory = "../";
    venv.enable = true;
    uv.enable = true;
  };

  scripts.devman.exec = ''
    (cd .. && uv sync)
    devman "$@"
  '';

  scripts.test.exec = ''
    (cd .. && uv sync --extra dev)
    (cd .. && pytest)
  '';

  scripts.test-branch.exec = ''
    set -euo pipefail
    git -C "${root}" rev-parse --abbrev-ref HEAD
  '';

  scripts.test-output-dir.exec = ''
    set -euo pipefail

    branch="$(${pkgs.bash}/bin/bash -lc "test-branch")"
    output_base="${root}/tests/output/${branch}"
    mkdir -p "${output_base}"

    last="$(ls -1 "${output_base}" 2>/dev/null | rg "^[0-9]{5}$" | sort | tail -n 1)"
    if [ -z "${last}" ]; then
      next="00001"
    else
      next="$(printf "%05d" "$((10#${last} + 1))")"
    fi

    output_dir="${output_base}/${next}"
    mkdir -p "${output_dir}"

    printf "%s\n" "${output_dir}"
  '';

  scripts.test-run.exec = ''
    set -euo pipefail

    output_dir="$(${pkgs.bash}/bin/bash -lc "test-output-dir")"
    (cd "${root}" && pytest | tee "${output_dir}/pytest.log")
  '';

  processes.test.exec = {
    exec = ''
      set -euo pipefail
      ${pkgs.bash}/bin/bash -lc "test-run"
    '';
    cwd = root;
  };
}
