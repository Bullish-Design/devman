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
# STAGE 3 adds the other two halves of the plane: the CLI (§10) and the watcher
# (§8). Both come from here and from nowhere else — the CLI because §3.1's
# second rule says what the two interfaces share must be text, and a Python
# program is not text; the watcher because a per-repository one would live only
# as long as somebody's `devenv up` (C1, D7).
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

  # THE SECURITY BOUNDARY, AS A PREDICATE (009 P1-6).
  #
  # `configFile` below always writes `auth.mode = "none"`, and the comment there
  # said "Loopback only". That described the DEFAULT, not an invariant: `host`
  # was an unrestricted string, so `host = "0.0.0.0"` exposed the web UI, the
  # API and the coordinator to the network with no gate at all, and nothing
  # said so. The assertion below turns the sentence into a check.
  #
  # The accepted set is the whole of IPv4 loopback (127.0.0.0/8), IPv6 loopback,
  # and the name `localhost`. Everything else is refused, including `0.0.0.0`
  # and `::` — a wildcard bind is the case this exists for.
  isLoopback = host:
    host == "localhost"
    || host == "::1"
    || host == "[::1]"
    || builtins.match "127\\.[0-9]+\\.[0-9]+\\.[0-9]+" host != null;

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
    # `dags/<project>.<workflow>.yaml` gives one machine-unique name that `ls`,
    # the scheduler and `enqueue` all agree on. It links to the per-project
    # projection under `projects/`, which stays exactly as §9.2 describes it.
    paths.dags_dir = "${registryToken}/dags";

    # Dagu seeds five example DAGs into an empty DAG directory on first start.
    # The DAG directory is the registry, so without this the registry acquires
    # five workflows belonging to no project, and `dagu ls` shows them beside
    # the real ones.
    skip_examples = true;

    # The shell every step and every handler runs under — and this is the ONE
    # place that states it (§7.1's shape: the machine states it once).
    #
    # IT APPLIES ONLY WHEN `$SHELL` IS UNSET, and the comment that used to sit
    # here claimed that was the normal case: "a user unit usually has no SHELL
    # at all". Measured false, twice over. Dagu resolves a step's shell from
    # `$SHELL` first — and it reads it from **whichever process enqueues the
    # run**, exactly as it reads `log_dir` (A3, A7). So the shell a step runs
    # under was, for three stages, the login shell of whoever triggered it: zsh
    # here, from a developer's prompt and from the systemd user manager under
    # the watcher alike.
    #
    # The failure is silent until a workflow uses a shell-specific construct:
    # POSIX-shaped steps behave identically in both. The first one to try —
    # a benchmark campaign reading bash's `$EPOCHREALTIME` — failed with
    # `parameter not set` (STAGE_4_LOG.md, S9, corrected by S13).
    #
    # THE FIX IS IN THE TRIGGER, NOT HERE. `devman run` clears `SHELL` from the
    # environment it hands `dagu enqueue`, beside the two directory names it
    # already clears, so this setting is what governs (src/devman/run.py). Setting
    # `SHELL` on this unit was tried and does nothing for any run the plane
    # makes: the daemon enqueues only under a `schedule:`, which §8 does not use.
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

    # A DAG naming no queue lands in a queue named after itself, at concurrency
    # 1 (S-9 — not "no limit at all", which is what A1 recorded and §15.4 now
    # corrects). The default is still needed, for the reason underneath that
    # number: a per-DAG queue bounds a DAG against ITSELF and bounds the machine
    # against nothing, so 53 projects would run 53 lanes wide with no stated
    # limit anywhere.
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
    #
    # `${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}` — the fallback is §11's, and it
    # is the reason `DEVMAN_SELF_DIR` is a global name rather than a convention.
    # A cross-repo workflow must NOT hold `DEVMAN_PROJECT_DIR`: a parent exports
    # its parameters into every child's environment and outranks the child's own
    # `with.params`, so a parent holding that name drags every child into its
    # directory. It therefore names its own directory `DEVMAN_SELF_DIR` — and
    # without this fallback the handler expanded to `/.devman/.runs/...`, failed
    # with `no such file or directory`, and took the whole run down with it. Both
    # children had already succeeded (S10).
    #
    # The fallback works only because this is a shell script. Dagu itself does
    # NOT support shell-style defaults: `working_dir:
    # ${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}` is kept literal and treated as a
    # relative path, which is why a cross-repo workflow still states its own
    # `working_dir` and `log_dir` (S10).
    handler_on.exit = {
      name = "devman-record-run";
      run = ''
        printf '{"dag":"%s","run_id":"%s","attempt":"%s","status":"%s","started_at":"%s","log":"%s"}\n' \
          '${ctx "dag.name"}' '${ctx "run.id"}' '${ctx "attempt.id"}' \
          '${ctx "run.status"}' '${ctx "attempt.started_at"}' '${ctx "paths.log_file"}' \
          >> "''${DEVMAN_PROJECT_DIR:-$DEVMAN_SELF_DIR}/.devman/.runs/metadata.jsonl"
      '';
    };
  };

  # The CLI (§10), wrapped with the two directories this machine chose.
  #
  # Both are FLAGS rather than `DEVMAN_*` variables, and that is deliberate:
  # Dagu passes every `DEVMAN_*` in the enqueueing process's environment through
  # to the run (`env_passthrough_prefixes` above), and §7.1's list of four names
  # is closed. A fifth would arrive in every workflow's environment.
  #
  # `%h` and `$HOME` become `~`, which the CLI expands itself. The options carry
  # a systemd specifier and a shell form respectively, because that is what the
  # unit and the shell hook each need; the CLI is neither.
  home = lib.replaceStrings [ "%h" "$HOME" ] [ "~" "~" ];
  cliUnwrapped = pkgs.callPackage ./devman-cli.nix { dagu = cfg.package; };
  cli = pkgs.runCommand "devman-${cliUnwrapped.version}"
    {
      nativeBuildInputs = [ pkgs.makeWrapper ];
      meta = cliUnwrapped.meta // { mainProgram = "devman"; };
    } ''
    makeWrapper ${cliUnwrapped}/bin/devman $out/bin/devman \
      --add-flags "--registry ${home cfg.registryDir}" \
      --add-flags "--dagu-home ${home cfg.dagHome}"
  '';

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

    installCli = mkOption {
      type = types.bool;
      default = true;
      description = ''
        Put the `devman` command on the system PATH — `run`, `show`, `doctor`
        (§10), and the watcher's own entry point (§8).

        It ships from here and not from the devenv module. §3.1's second rule
        says what the two interfaces share must be text, and a Python program is
        not text; shipping it from both would also put two `devman` binaries on
        one PATH, resolved by profile order, which is the hazard §3.3 records
        against `devman 0.2.0`. A devenv shell inherits this profile's PATH, so
        one install reaches every repository shell on this machine.
      '';
    };

    watch = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = ''
          Run the watcher: one `watchexec` user service for the whole machine,
          reading the registry for the paths to watch (§8, D7).

          **It is safe to leave on, because it watches nothing by default.**
          Reactivity is opt-in per repository: the watcher fires a workflow only
          for a project that takes a group whose  `triggers.toml` names a glob. A
          machine where no project takes such a group runs a service that exits
          reporting it has nothing to do.

          Not one watcher per repository. A per-repository watcher's only home
          is a devenv `processes.` entry, and those run under `devenv up` and
          nothing else — so reactivity would apply to whichever repositories
          somebody happened to have open (C1, D7).
        '';
      };

      package = mkOption {
        type = types.package;
        default = pkgs.watchexec;
        defaultText = lib.literalExpression "pkgs.watchexec";
        description = "The watchexec the watcher execs. nixpkgs ships 2.5.1 (D7).";
      };

      watchexecArgs = mkOption {
        type = types.listOf types.str;
        default = [ ];
        example = [ "--debounce" "200ms" ];
        description = ''
          Extra arguments for watchexec.

          A debounce coalesces the events of one save into one batch. It is NOT
          the loop break, and it must never be used as one: §8 requires a
          content hash, so that your own edit right after a formatter's write
          still fires. A window would swallow it (E1).
        '';
      };
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
      description = ''
        Bind address for the web UI and the coordinator. Loopback, because the
        plane runs one developer's own checkouts.

        **This is a security boundary, and an assertion enforces it.** The
        generated config sets `auth.mode = "none"`, so a non-loopback bind would
        expose the web UI, the API and the coordinator with no authentication.
        Only 127.0.0.0/8, `::1` and `localhost` evaluate (009 P1-6).
      '';
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

        Renaming a queue is a migration across every workflow that names it.
        Dagu accepts an undeclared name silently and gives it concurrency 1,
        shared by every workflow that names it — so a rename that misses a file
        serialises that file rather than freeing it (§15.4, S-9).
      '';
    };

    defaultQueue = mkOption {
      type = types.str;
      default = "light";
      description = ''
        The queue a workflow naming none inherits from base.yaml. Without it
        Dagu gives each DAG a queue named after itself at concurrency 1, which
        bounds a DAG against itself and the machine against nothing (S-9, E4).

        **It must name a key of `queues`, and an assertion enforces it.** Dagu
        accepts an undeclared name silently and gives it concurrency 1, so a
        typo here serialises the whole machine and says nothing (009 P3-1).
      '';
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
    # An option whose description states an invariant, and whose type does not
    # enforce it, states nothing (009 P1-6, P3-1). Both of these are evaluation
    # time, which is the cheapest place to refuse: the developer learns before
    # the service exists.
    assertions = [
      {
        assertion = isLoopback cfg.host;
        message = ''
          services.devman-dagu.host is "${cfg.host}", and the generated Dagu
          config sets auth.mode = none (CONCEPT.md §4, project 009 P1-6). A
          non-loopback bind would expose the web UI, the API and the coordinator
          to the network with no authentication at all. Keep it on loopback:
          127.0.0.0/8, ::1, or localhost.

          A network bind is a second option — a Dagu auth mode and a token file
          on §9.4's secrets path — and its own charter conversation. It is not
          this option.
        '';
      }
      {
        assertion = builtins.hasAttr cfg.defaultQueue cfg.queues;
        message = ''
          services.devman-dagu.defaultQueue is "${cfg.defaultQueue}", which is
          not a key in services.devman-dagu.queues (${
            builtins.concatStringsSep ", " (builtins.attrNames cfg.queues)
          }).

          Dagu accepts an undeclared queue name silently and gives it
          concurrency 1 (§15.4, S-9), so every workflow on this machine would
          serialise against every other one, and nothing would say why.
        '';
      }
    ];

    warnings = lib.optional (cfg.lingerUsers == [ ]) ''
      services.devman-dagu.lingerUsers is empty. The Dagu user service then runs
      only while its user has a login session, and a configuration change does
      not restart it during activation (CONCEPT.md §4, finding C7). Set it, or
      set users.users.<name>.linger elsewhere in this configuration.
    '';

    users.users = lib.genAttrs cfg.lingerUsers (_: { linger = true; });

    environment.systemPackages =
      lib.optional cfg.installClient cfg.package
      ++ lib.optional cfg.installCli cli;

    systemd.user.services.dagu = {
      description = "Dagu — devman automation plane";
      wantedBy = [ "default.target" ];

      # `SHELL` is DELIBERATELY ABSENT here, and it was present for one commit.
      # Dagu reads `$SHELL` from the process that enqueues a run, so setting it
      # on this unit governs only the runs the daemon enqueues itself — which,
      # under §8, is none. The trigger clears it instead, in one place, so that
      # `default_shell` above governs every path into the plane (S13).
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

    # §8: the watcher. One process for the machine, beside Dagu, from the same
    # module and with the same lifetime — which is the whole reason it is here
    # rather than in a repository (D7).
    #
    # It needs no port and no state of its own beyond `<registry>/watch/`, which
    # is derived like everything else under the registry root (§9.3).
    systemd.user.services.devman-watch = mkIf cfg.watch.enable {
      description = "devman watcher — one watchexec for every registered repository";
      wantedBy = [ "default.target" ];

      # Ordering only. The watcher enqueues through the queue store on disk, so
      # a trigger while Dagu is down is not lost — it waits (E2, A1).
      after = [ "dagu.service" ];

      # `devman watch` resolves its own name from PATH when it re-invokes itself
      # per event, so the CLI has to be on it. Dagu and watchexec are already
      # wrapped onto the CLI's own PATH; naming them here as well keeps the unit
      # readable in `systemctl --user cat`.
      path = [ cli cfg.package cfg.watch.package ] ++ cfg.servicePath;

      serviceConfig = {
        Type = "simple";
        ExecStart = lib.escapeShellArgs (
          [ "${cli}/bin/devman" "watch" ]
          ++ lib.concatMap (a: [ "--watchexec-arg" a ]) cfg.watch.watchexecArgs
        );
        Restart = "on-failure";
        RestartSec = 5;
      };

      # A machine whose registry declares no triggers has nothing to watch. The
      # service still stays up: `devman watch` is a supervisor and it is waiting
      # for the first repository to adopt a reactive group. It costs one wake-up
      # every five seconds and 0.44 ms of work in it (S16).
      startLimitIntervalSec = 60;
      startLimitBurst = 5;

      # THE SET OF WATCHED PATHS IS WATCHEXEC'S COMMAND LINE, so it is fixed
      # when watchexec starts. The MAPPING is re-read on every event, so
      # changing which glob fires which workflow is live either way.
      #
      # `devman watch` closes the gap itself: it re-reads the registry every
      # five seconds and replaces its watchexec child when the path set changes.
      # A repository that adopts reactivity is therefore watched without anybody
      # restarting anything, and `devman doctor` still compares the running
      # watcher's own record against the registry (S16).
      #
      # THE UNIT MUST NOT RESTART ITSELF, and that is why the supervisor
      # replaces a child instead. `systemctl --user restart devman-watch` issued
      # from inside this unit does not return — systemd stops the unit, killing
      # the process that asked — and it produced 15 restarts in 30 seconds with
      # `NRestarts=0`, so `startLimitBurst` above would not stop it (S16).
      #
      # `restartTriggers` covers a devman upgrade. It cannot cover the registry:
      # that changes at shell entry, which no activation sees.
      restartTriggers = [ cli ];
    };
  };
}
