{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.ruff
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
  # processes.cargo-watch.exec = "cargo-watch";

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

  # https://devenv.sh/tasks/
  tasks."devman:agent-factory-spike-dependencies" = {
    description = "Install local dependencies for the agent-factory round-trip spike";
    after = [ "devenv:python:virtualenv" ];
    before = [ "devenv:enterShell" ];
    exec = ''
      SPIKE_PYTHON="${config.env.DEVENV_STATE}/venv/bin/python"
      SPIKE_SITE_PACKAGES="$(echo "${config.env.DEVENV_STATE}"/venv/lib/python*/site-packages)"
      PYDANTREE_SOURCE="${config.devenv.root}/../pydantree/src"
      PYDANTREE_SITE_PACKAGES="${config.devenv.root}/../pydantree/.devenv/state/venv/lib/python3.13/site-packages"
      TEMPLATEER_SOURCE="${config.devenv.root}/../templateer_v2/src"
      TEMPLATEER_SITE_PACKAGES="${config.devenv.root}/../templateer_v2/.devenv/state/venv/lib/python3.13/site-packages"

      if "$SPIKE_PYTHON" -c \
        'import pydantree_sitter, templateer, tree_sitter_python' \
        >/dev/null 2>&1; then
        exit 0
      fi

      for SPIKE_PATH in \
        "$PYDANTREE_SOURCE" \
        "$PYDANTREE_SITE_PACKAGES" \
        "$TEMPLATEER_SOURCE" \
        "$TEMPLATEER_SITE_PACKAGES"; do
        if [ ! -d "$SPIKE_PATH" ]; then
          echo "agent-factory spike dependency path is missing: $SPIKE_PATH" >&2
          exit 2
        fi
      done

      mkdir -p "$SPIKE_SITE_PACKAGES"
      cat > "$SPIKE_SITE_PACKAGES/_agent_factory_spike_siblings.pth" <<PTH
import sys; sys.path[:0] = ["$PYDANTREE_SOURCE", "$TEMPLATEER_SOURCE", "$PYDANTREE_SITE_PACKAGES", "$TEMPLATEER_SITE_PACKAGES"]
PTH
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
