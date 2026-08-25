{ pkgs, lib, config, inputs, ... }:

let
  # The plane's orchestrator (CONCEPT.md §4). nixpkgs packages no Dagu at any
  # version, so this repo carries the expression and both interfaces call the
  # same file — this shell now, the NixOS module at stage 1 (§3.1).
  dagu = pkgs.callPackage ./nix/dagu.nix { };
in
{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.ruff
    dagu
    inputs.codex-cli.packages.${pkgs.system}.default
    inputs.claude-code.packages.${pkgs.system}.default
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;
  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    uv.enable = true;
    #ruff.enable = true;

  };
  # https://devenv.sh/processes/
  #
  # `processes.dagu` is DELIBERATELY ABSENT (CONCEPT.md §4, §13 stage 1).
  #
  # It used to start one instance here with `devenv up`, which is how the
  # investigations got a Dagu to measure. It cannot stay. Dagu binds a web port
  # and a coordinator port, and a second instance fails on the coordinator with
  # `bind: address already in use` even when it has its own DAGU_HOME — so a
  # project-local Dagu in THIS repo holds the ports the plane's own user service
  # needs, and criterion 16 says devman adopts itself (D3).
  #
  # Stage 1 installs the service from `nix/nixos-module.nix`. Until then, run a
  # throwaway instance by hand with its own DAGU_HOME rather than restoring this
  # line.
  #
  # `env.DAGU_HOME` is DELIBERATELY ABSENT, and its removal is stage 3's.
  #
  # It used to point at `${config.devenv.state}/dagu`, which was right while the
  # investigations started Dagu by hand from `processes.dagu`. The plane's own
  # service now owns `~/.local/share/dagu`, so the variable pointed a developer's
  # `dagu` at an empty home inside this repository's devenv state: `dagu ls`
  # listed nothing and `dagu enqueue` reached a Dagu that has never heard of the
  # registry.
  #
  # Nothing needs it. `devman run` states `--dagu-home` rather than inheriting
  # one, because an unset `DAGU_HOME` makes `dagu` build a fresh home and seed
  # five example DAGs (S2). A person who wants to talk to the plane directly
  # exports it themselves, and `STAGE_3_PROMPT.md` §4 says how.

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  

  enterShell = ''
    hello
    git --version
    #echo
    # Create a wrapper script to ensure Nix ruff is used
    export PATH="${pkgs.ruff}/bin:$PATH"
    # Remove any pip-installed ruff from the environment
    unset VIRTUAL_ENV_RUFF
    #echo

  '';

  # devman adopts itself (CONCEPT.md §14, criterion 16). Three lines, and the
  # repo's own primitives below.
  #
  # There is no `devman` input in devenv.yaml: this repository IS the plane, so
  # it imports `./modules` directly. Every other repository pins a rev with
  # `git+file` (§3.2): it records `rev` and `narHash` in the lock and reads
  # committed files only. This repository imports its own modules directly so
  # its active working tree remains visible.
  # `base` for the workflows, `format` for the reactivity (§8).
  #
  # The `python` group was deleted at stage 7: a language's decomposition is a
  # devenv task graph, not a Dagu file (PROPOSAL.md §1.1).
  #
  # `format` is the group that fires on a save, and taking it is the whole
  # opt-in (groups/format/README.md). devman adopts its own reactive group
  # for the same reason criterion 16 has it adopt its own workflows: a plane
  # nobody runs against themselves is a plane nobody has tested.
  # `release` is stage 4's, and devman is one of the two repositories that made
  # it a group rather than one repository's own file (§16's promotion rule —
  # a group begins when a second repository wants the same file). It ships one
  # workflow that nothing ever fires on its own, so inheriting it costs nothing
  # (§7.4) — which is exactly the argument that does NOT hold for
  # `format`, and the difference is that a release is triggered by a
  # person (groups/release/README.md).
  devman = {
    enable = true;
    project = "devman";
    groups = [ "base" "format" "release" ];
  };

  # https://devenv.sh/tasks/
  #
  # The two task names the `base` group calls (groups/base/README.md). devenv
  # owns each implementation; Dagu owns the composition (§6).
  tasks = {
    "base:check".exec = "ruff check .";
    "base:test".exec = "nix flake check";

    # What `python-format`'s workflow runs when a `.py` file is saved. The group
    # names a task and never a tool (§7.1), so this line is the whole of what
    # this repository decides about formatting.
    "format:fmt".exec = "ruff format .";

    # What `release` builds here: the CLI the machine installs. The artifact
    # goes under `.devman/.runs/artifacts/`, which is §9.2's own name for the
    # place a run's output goes — created at registration, git-ignored, and
    # addressed relatively because `working_dir` is already this project.
    #
    # `--out-link` rather than `--print-out-paths` alone: the link is what makes
    # the artifact visible in the report the workflow writes, and it also roots
    # the build against the garbage collector until the next release.
    "release:build".exec = ''
      nix build .#devman --out-link .devman/.runs/artifacts/devman
    '';

    # What `.devman/workflows/agent-review.yaml` runs. The workflow names a task
    # and the task names the tool, which is §6's split — swap `claude` for
    # `codex` here and no workflow changes.
    #
    # THE AGENT IS GIVEN TEXT AND NO TOOLS. The commit is piped in as the prompt,
    # so the run cannot read or write anything outside this pipeline whatever it
    # decides to do. An agent with repository access, fired by a timer with
    # nobody watching, is the shape §10 of STAGE_4_PROMPT.md warns about; this
    # one cannot reach the repository at all.
    #
    # `head -c` bounds the input: an unbounded diff is an unbounded bill.
    #
    # `$AGENT_REPORT`, `$AGENT_REF` and `$AGENT_PROMPT` come from the workflow's
    # parameters through the step's environment. `set -u` is what makes a broken
    # hand-off loud rather than a report written to a file called nothing.
    "agent:review".exec = ''
      set -euo pipefail
      {
        printf '%s\n\n' "$AGENT_PROMPT"
        git show --stat --patch "$AGENT_REF"
      } | head -c 60000 | claude -p --output-format text >> "$AGENT_REPORT"
    '';

    # What `.devman/workflows/gitman-commit-message.yaml` runs. Same shape as
    # `agent:review`: the diff is piped in as the whole prompt, the agent gets
    # no tools and no repo access, and `head -c` bounds the input.
    #
    # `git diff --staged` reads jj's colocated git index, which gitman keeps in
    # sync on every `save` — so this sees the change a lane is about to record,
    # not the change it already did.
    #
    # $MESSAGE_FILE holds nothing but the message: no report header, no run id,
    # so `gitman save -m "$(cat "$MESSAGE_FILE")"` can use it unmodified.
    #
    # Runs on the local GPU rather than `claude -p` — `scripts/gpu_complete.py`
    # is a standalone `uv run --script` (PEP 723 inline deps: pydantic-ai +
    # openai), never installed into this package, so the GPU-only dependency
    # never reaches `pyproject.toml` or the shipped `devman` CLI (cli.py's own
    # note: this CLI ships from the NixOS module only). It calls out to
    # `llgym serve`'s OpenAI-compatible shim over the `inferference` engine —
    # devman does not start that server, only calls it, and the script fails
    # plainly if nothing answers on `$GPU_LLM_BASE_URL`.
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

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
