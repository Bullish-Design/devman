{ pkgs, lib, config, inputs, ... }:

let
  # One Dagu expression for the shell, the package and the Home Manager module.
  dagu = pkgs.callPackage ./nix/dagu.nix { };

  # The interpreter that runs the tests. It is an explicit store path, not the
  # venv: `flake.nix` `python-tests` takes pytest from nixpkgs too, so the fast
  # loop and the check run the same pytest and pyyaml. A bare `pytest` on PATH
  # would resolve against the venv first.
  pytestPython = pkgs.python313.withPackages (ps: [ ps.pytest ps.pyyaml ]);
in
{
  # The shell does not install the devman package. Two `devman` binaries on
  # one PATH was a measured hazard. Tests run the source with `python -m devman`.
  packages = [
    pkgs.git
    pkgs.ruff
    dagu
    pkgs.watchexec
    pkgs.hyperfine
    inputs.codex-cli.packages.${pkgs.system}.default
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
  };

  enterShell = ''
    git --version
  '';

  # Task names are part of the contract (PLAN.md Stage 0): library workflows
  # call them. devenv owns each implementation; Dagu owns the composition.
  tasks = {
    "base:check".exec = "ruff check . && ruff format --check .";
    "base:unit".exec = "${pytestPython}/bin/pytest -m 'not e2e'";
    "base:e2e".exec = "${pytestPython}/bin/pytest -m e2e";
    "base:test".exec = "nix flake check";
    "format:fmt".exec = "ruff format .";
    "release:build".exec = "nix build .#devman --out-link result-devman";

    # The agent gets text and no tools: the commit is the whole prompt, so the
    # run cannot read or write outside this pipeline. `head -c` bounds the
    # input, because an unbounded diff is an unbounded bill. `set -u` makes a
    # broken hand-off loud.
    "agent:review".exec = ''
      set -euo pipefail
      {
        printf '%s\n\n' "$AGENT_PROMPT"
        git show --stat --patch "$AGENT_REF"
      } | head -c 60000 | claude -p --output-format text >> "$AGENT_REPORT"
    '';

    # Same shape as `agent:review`. `git diff --staged` reads jj's colocated
    # git index. The script runs on the local GPU endpoint named by
    # `$GPU_LLM_BASE_URL`; it is a standalone `uv run --script` and never joins
    # this package's dependencies. $MESSAGE_FILE holds only the message.
    "gitman:commit-message".exec = ''
      set -euo pipefail
      prompt='Write a commit message for this diff. One summary line, 50
      characters or fewer, imperative mood. A blank line, then body lines only
      if the diff needs one explained. No markdown fences, no "here is a
      commit message" preamble — output only the message text.'
      {
        printf '%s\n\n' "$prompt"
        git diff --staged
      } | head -c 60000 | uv run --script scripts/gpu_complete.py > "$MESSAGE_FILE"
    '';
  };

  enterTest = ''
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}
