# The machine interface — a NixOS module that runs one Dagu instance.
#
# INVESTIGATION B SCRATCH (CONCEPT.md §12.3). This is the smallest honest
# module: enough to prove that one flake can carry a NixOS module and a devenv
# module at one version. It is not stage 1. It does not project workflows
# (§9.2), it does not resolve group precedence (§7.3), and it does not read the
# registry.
#
# What it does hold, because the reconciled charter measured it and a module
# that ignored it would prove nothing:
#
#   * a systemd USER service, not a system service (§4). Every workflow step
#     runs a developer's own devenv in a developer's own checkout.
#   * DAGU_HOME at ~/.local/share/dagu, beside the registry, not /var/lib (§4).
#   * config.yaml with queues, `env_passthrough_prefixes`, and both
#     `dag_discovery` knobs (§5.2, §7.1, A2, A5).
#   * base.yaml with `working_dir`, `log_dir`, and a default queue (§7.2, E4).
#   * a restart when config.yaml changes (§5.2, E4).
#
# It takes `pkgs` from the importing machine and calls ./dagu.nix with it. That
# is the §3.1 anti-drift rule as written: one package expression, each side's
# nixpkgs. Investigation B is the test of whether that holds.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf mkOption types;

  cfg = config.services.devman-dagu;
  yaml = pkgs.formats.yaml { };

  # `${DEVMAN_PROJECT_DIR}` is Dagu's own interpolation, resolved at run time
  # (A2, A3). Nix must not eat it, hence the escape.
  projectDir = "\${DEVMAN_PROJECT_DIR}";

  configFile = yaml.generate "dagu-config.yaml" {
    queues = {
      enabled = true;
      config = lib.mapAttrsToList
        (name: max_concurrency: { inherit name max_concurrency; })
        cfg.queues;
    };

    # Without this no DEVMAN_* variable reaches a DAG. The daemon does not
    # inherit the caller's environment (A2).
    env_passthrough_prefixes = [ "DEVMAN_" ];

    # Both default to off, and neither failure announces itself: an
    # undiscovered workflow is simply absent from `dagu ls` (A5).
    dag_discovery = {
      recursive = true;
      symlinks = true;
    };
  };

  baseFile = yaml.generate "dagu-base.yaml" {
    working_dir = projectDir;
    log_dir = "${projectDir}/.devman/.runs/logs";
    queue = cfg.defaultQueue;
    hist_retention_days = 7;
  };

  # Nix evaluation cannot write into $HOME, so the unit installs its own two
  # files on every start. `install -m` rather than a symlink: Dagu reads these
  # once at startup and a store symlink would hide which revision is live.
  installConfig = pkgs.writeShellScript "dagu-install-config" ''
    set -eu
    mkdir -p "$DAGU_HOME/dags"
    install -m 0644 ${configFile} "$DAGU_HOME/config.yaml"
    install -m 0644 ${baseFile} "$DAGU_HOME/base.yaml"
  '';
in
{
  options.services.devman-dagu = {
    enable = mkEnableOption "the devman automation plane's Dagu user service";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./dagu.nix { };
      defaultText = lib.literalExpression "pkgs.callPackage ./dagu.nix { }";
      description = "The Dagu package to run. Defaults to the plane's own expression, evaluated under the machine's nixpkgs.";
    };

    dagHome = mkOption {
      type = types.str;
      default = "%h/.local/share/dagu";
      description = "DAGU_HOME. A systemd specifier, because a user service has one home per user (§4).";
    };

    queues = mkOption {
      type = types.attrsOf types.ints.positive;
      default = { exclusive = 1; };
      example = { exclusive = 1; light = 4; };
      description = "Queue names and their concurrency limits. The machine states how much may run at once, never what runs (§4).";
    };

    defaultQueue = mkOption {
      type = types.str;
      default = "exclusive";
      description = "The queue a workflow that names none inherits from base.yaml (E4).";
    };
  };

  config = mkIf cfg.enable {
    systemd.user.services.dagu = {
      description = "Dagu — devman automation plane";
      wantedBy = [ "default.target" ];

      environment.DAGU_HOME = cfg.dagHome;

      serviceConfig = {
        Type = "simple";
        ExecStartPre = "${installConfig}";
        ExecStart = "${lib.getExe cfg.package} start-all";
        Restart = "on-failure";
        RestartSec = 5;
      };

      # §5.2: a config change requires a restart, or the CLI honours the new
      # config while the server does not, and the server reports an error
      # naming the setting you already added. A new DAG file needs no restart.
      restartTriggers = [ configFile baseFile ];
    };
  };
}
