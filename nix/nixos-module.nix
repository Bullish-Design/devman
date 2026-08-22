# The machine interface — one Dagu control plane per machine (CONCEPT.md §4).
#
# STAGE 1. This module owns the Dagu installation, the service, the instance
# config, the state paths, and the queues. It never learns one project fact:
# it states how much may run at once, never what runs (§4).
#
# It takes `pkgs` from the importing machine and calls ./dagu.nix with it. That
# is §3.1's first rule — one package expression, each side's nixpkgs. What the
# two interfaces share is otherwise text: the queue names, the variable name
# `DEVMAN_PROJECT_DIR`, the `.devman/.runs/` path shape, and the registry
# layout (§3.1, §7.1).
#
# What it deliberately does not do:
#   * the watcher (§8) is stage 3. Nothing here makes adding one awkward: it is
#     a second systemd user service reading the same registry.
#   * the CLI (§10) is stage 3.
{ config, lib, pkgs, ... }:

let
  inherit (lib) mkEnableOption mkIf mkOption types;

  cfg = config.services.devman-dagu;
  yaml = pkgs.formats.yaml { };

  # `${DEVMAN_PROJECT_DIR}` is Dagu's own interpolation, resolved at run time
  # (A2, A3). Nix must not eat it, hence the escape. The value arrives as a
  # trigger-time parameter for `working_dir` and from the trigger's environment
  # for `log_dir`; one is not a substitute for the other (A3).
  projectDir = "\${DEVMAN_PROJECT_DIR}";

  # The registry root holds `$HOME`, because a user service has one home per
  # user and Nix cannot know it. The ExecStartPre script below expands it in a
  # double-quoted bash assignment, and substitutes the result into config.yaml.
  registryToken = "@DEVMAN_REGISTRY@";

  # Dagu's own run metadata, resolved per run. Written as a normal Nix string so
  # the `${` escape stays readable next to the shell quoting that surrounds it.
  ctx = ref: "\${context.${ref}}";

  configFile = yaml.generate "devman-dagu-config.yaml" {
    # Loopback only. This is a per-user service holding one developer's own
    # checkouts, and §8 triggers it with a local `dagu enqueue`.
    host = cfg.host;
    port = cfg.port;
    coordinator = {
      host = cfg.host;
      port = cfg.coordinatorPort;
    };

    # Without a mode Dagu warns on every command and demands /setup. The
    # service listens on loopback, so the account gate buys nothing.
    auth.mode = "none";

    # Dagu reads exactly one DAG directory (§9.2), and it is the registry's
    # flat `dags/` view rather than `projects/`. Two measurements force that:
    #
    #   * a DAG is keyed by its file's base name, not by its path under the DAG
    #     directory. Two projects both projecting `check.yaml` are reported as
    #     `duplicate DAG name "check"` and BOTH disappear from `dagu ls`, from
    #     the web UI and from the scheduler, while staying runnable by path.
    #     That is A5's silent-absence hazard arriving by a second route.
    #   * `dagu enqueue <name>` resolves the name as a path under the DAG
    #     directory, so a nested DAG is enqueued as
    #     `<project>/workflows/<file>` while `dagu ls` prints `<file>`. One DAG
    #     with two names is a trap.
    #
    # `dags/<project>-<workflow>.yaml` gives one machine-unique name that `ls`,
    # the scheduler and `enqueue` all agree on. It links to the per-project
    # projection under `projects/`, which stays exactly as §9.2 describes it.
    paths.dags_dir = "${registryToken}/dags";

    # Dagu seeds five example DAGs into an empty DAG directory on first start.
    # The DAG directory is the registry, so without this the registry acquires
    # five workflows belonging to no project, and `dagu ls` shows them beside
    # the real ones.
    skip_examples = true;

    # Every step and every handler runs under one known shell, whatever the
    # developer's login shell is. A user unit usually has no SHELL at all.
    default_shell = "${pkgs.bash}/bin/bash";

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
    # undiscovered workflow is simply absent from `dagu ls`, from the web UI
    # and from the scheduler, while staying runnable by name (A5). The
    # projection needs both — subdirectories for the per-project layout, file
    # symlinks for the group files it links out of the Nix store.
    dag_discovery = {
      recursive = true;
      symlinks = true;
    };
  };

  # Everything §7.2 calls portable is machine state rather than file content,
  # so a group workflow reduces to a queue and its steps (E4).
  baseFile = yaml.generate "devman-dagu-base.yaml" {
    working_dir = projectDir;
    log_dir = "${projectDir}/.devman/.runs/logs";

    # A DAG naming no queue would otherwise land in a queue named after itself,
    # with no limit at all (A1, §15.4).
    queue = cfg.defaultQueue;

    # Prunes both halves — Dagu's machine-side history and the per-project log
    # tree under `log_dir` (D5). `metadata.jsonl` below survives it, because
    # nothing in Dagu owns that file.
    hist_retention_days = cfg.histRetentionDays;

    # §9.2: one line per run, in the triggering project's own working tree,
    # written by Dagu rather than by any workflow. It runs on the success path
    # and the failure path alike.
    #
    # `printf` is a shell builtin, so the handler forks nothing and needs
    # nothing on PATH. The directory already exists: Dagu creates `log_dir`
    # before the first step runs, and `log_dir` is two levels inside it.
    #
    # The redirect uses the SHELL variable `$DEVMAN_PROJECT_DIR`, not Dagu's
    # `${DEVMAN_PROJECT_DIR}`. Measured: Dagu interpolates `${context.*}` in a
    # handler's `run:` and does NOT interpolate the run parameter there, so the
    # `${...}` form reaches the shell as literal text and the append fails with
    # `no such file or directory: ${DEVMAN_PROJECT_DIR}/...`. The parameter does
    # reach the step's environment, which is why the plain form works.
    handler_on.exit = {
      name = "devman-record-run";
      run = ''
        printf '{"dag":"%s","run_id":"%s","attempt":"%s","status":"%s","started_at":"%s","log":"%s"}\n' \
          '${ctx "dag.name"}' '${ctx "run.id"}' '${ctx "attempt.id"}' \
          '${ctx "run.status"}' '${ctx "attempt.started_at"}' '${ctx "paths.log_file"}' \
          >> "$DEVMAN_PROJECT_DIR/.devman/.runs/metadata.jsonl"
      '';
    };
  };

  # Nix evaluation cannot write into $HOME, so the unit installs its two files
  # on every start. `install -m` rather than a symlink: Dagu reads these once at
  # startup, and a store symlink would hide which revision is live.
  installConfig = pkgs.writeShellScript "devman-dagu-install-config" ''
    set -eu
    registry="${cfg.registryDir}"

    # The registry is the devenv module's to fill, but its two directories must
    # exist before Dagu scans one of them.
    "${pkgs.coreutils}/bin/mkdir" -p "$DAGU_HOME" "$registry/projects" "$registry/dags"

    "${pkgs.gnused}/bin/sed" "s|${registryToken}|$registry|g" ${configFile} \
      > "$DAGU_HOME/.config.yaml.new"
    "${pkgs.coreutils}/bin/install" -m 0644 "$DAGU_HOME/.config.yaml.new" "$DAGU_HOME/config.yaml"
    "${pkgs.coreutils}/bin/rm" -f "$DAGU_HOME/.config.yaml.new"

    "${pkgs.coreutils}/bin/install" -m 0644 ${baseFile} "$DAGU_HOME/base.yaml"
  '';
in
{
  options.services.devman-dagu = {
    enable = mkEnableOption "the devman automation plane's Dagu user service";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./dagu.nix { };
      defaultText = lib.literalExpression "pkgs.callPackage ./dagu.nix { }";
      description = "The Dagu package to run. Defaults to the plane's own expression, evaluated under the machine's nixpkgs (§3.1).";
    };

    installClient = mkOption {
      type = types.bool;
      default = true;
      description = "Put the Dagu client on the system PATH, so a trigger can run `dagu enqueue` locally. Only a local process resolves `log_dir` into the project that triggered the run (E2).";
    };

    dagHome = mkOption {
      type = types.str;
      default = "%h/.local/share/dagu";
      description = "DAGU_HOME. A systemd specifier, because a user service has one home per user (§4).";
    };

    registryDir = mkOption {
      type = types.str;
      default = "$HOME/.local/share/devman";
      description = ''
        The registry root (§9.2). `$HOME` is expanded by the unit's
        ExecStartPre, not by Nix, because a user service has one home per user.
        It must match `devman.registryDir` in every repository that registers.
      '';
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = "Bind address for the web UI and the coordinator. Loopback, because the plane runs one developer's own checkouts.";
    };

    # §4: a second Dagu is a port collision, not a state collision, so the
    # ports are options — a developer running a project-local Dagu moves one
    # rather than choosing between the two.
    port = mkOption {
      type = types.port;
      default = 8080;
      description = "The web UI port. Dagu's own default (D3).";
    };

    coordinatorPort = mkOption {
      type = types.port;
      default = 50055;
      description = "The coordinator port. Dagu's own default, and the one a second instance fails on first: `bind: address already in use`, exit 1 (D3).";
    };

    queues = mkOption {
      type = types.attrsOf types.ints.positive;
      default = {
        light = 4;
        normal = 2;
        heavy = 1;
        gpu = 1;
        exclusive = 1;
      };
      description = ''
        Queue names and their concurrency limits (§7.1). The machine states how
        much may run at once, never what runs (§4).

        Renaming a queue is a migration across every workflow that names it, and
        Dagu accepts an undefined queue silently, with no limit at all (§15.4).
      '';
    };

    defaultQueue = mkOption {
      type = types.str;
      default = "light";
      description = "The queue a workflow naming none inherits from base.yaml. Without it Dagu invents a queue named after the DAG and applies no limit (A1, E4).";
    };

    histRetentionDays = mkOption {
      type = types.ints.positive;
      default = 7;
      description = "Prunes Dagu's machine-side run history and the per-project log tree under `log_dir` alike (D5). `metadata.jsonl` survives it, because nothing in Dagu owns that file.";
    };

    servicePath = mkOption {
      type = types.listOf types.str;
      default = [
        "%h/.nix-profile"
        "/etc/profiles/per-user/%u"
        "/run/current-system/sw"
        "/nix/var/nix/profiles/default"
      ];
      description = ''
        Profile roots prepended to the service's PATH. `bin` and `sbin` of each
        are added, and systemd expands `%h` and `%u` per user.

        §4 says a user service already has the developer's Nix profile. That is
        true of the login environment and **not** of the unit: NixOS pins
        `Environment=PATH=` to coreutils, findutils, gnugrep, gnused and
        systemd, so without this a step calling `devenv` reports
        `command not found`. Every workflow step runs `devenv tasks run` (§6),
        so the plane cannot run at all without it.
      '';
    };

    lingerUsers = mkOption {
      type = types.listOf types.str;
      default = [ ];
      example = [ "andrew" ];
      description = ''
        Users whose service manager must run without a login session (§4).

        Two things need this. The plane is not running at all on a machine
        nobody has logged into. And `switch-to-configuration` reaches exactly
        the users `logind` lists, so without lingering a config change never
        restarts the service either (C7).
      '';
    };
  };

  config = mkIf cfg.enable {
    warnings = lib.optional (cfg.lingerUsers == [ ]) ''
      services.devman-dagu.lingerUsers is empty. The Dagu user service then runs
      only while its user has a login session, and a configuration change does
      not restart it during activation (CONCEPT.md §4, finding C7). Set it, or
      set users.users.<name>.linger elsewhere in this configuration.
    '';

    users.users = lib.genAttrs cfg.lingerUsers (_: { linger = true; });

    environment.systemPackages = lib.optional cfg.installClient cfg.package;

    systemd.user.services.dagu = {
      description = "Dagu — devman automation plane";
      wantedBy = [ "default.target" ];

      environment.DAGU_HOME = cfg.dagHome;

      # Prepended to NixOS's own minimal unit PATH, which the default
      # `enableDefaultPath` appends after this list. See `servicePath`.
      path = cfg.servicePath;

      serviceConfig = {
        Type = "simple";
        ExecStartPre = "${installConfig}";
        ExecStart = "${lib.getExe cfg.package} start-all";
        Restart = "on-failure";
        RestartSec = 5;
      };

      # §4: a port conflict never resolves on its own. Unbounded, the restart
      # retries every five seconds forever and fills the journal. Five attempts
      # in a minute, then systemd gives up and `systemctl --user status dagu`
      # holds the named port and the named error.
      startLimitIntervalSec = 60;
      startLimitBurst = 5;

      # §5.2: the instance config is read once, at startup. A missed restart is
      # not an error — the CLI reads the new config, the run runs, every exit
      # code is zero, and one INFO line in the server's log gives the wrong
      # concurrency (C7, superseding E's earlier account).
      #
      # `restartTriggers` alone is sufficient. `switch-to-configuration` visits
      # the user scope and applies the same unit comparison it applies to system
      # units, so the unit stops and starts inside the activation. Measured on
      # nixpkgs 26.11.20260705.d407951 — it is a property of
      # switch-to-configuration, not of NixOS in general (C7).
      #
      # A new DAG *file* needs no restart: discovery is a directory scan and the
      # running daemon picks one up immediately (A5).
      restartTriggers = [ configFile baseFile ];
    };
  };
}
