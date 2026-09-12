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
    # THE FIX IS IN THE TRIGGER, AND IN THE UNIT — two enqueue owners, two
    # clearings. `devman run` clears `SHELL` from the environment it hands `dagu
    # enqueue`, beside the two directory names it already clears
    # (`src/devman/run.py`), which covers the CLI, the watcher and the hook. The
    # unit sets `UnsetEnvironment=SHELL`, which covers the runs the daemon
    # enqueues itself under a `schedule:`.
    #
    # This comment said the daemon enqueues nothing. That was true when it was
    # written and false from the moment stage 7 shipped two scheduled workflows
    # (009 P1-3, `STAGE_9_LOG.md` S-7). `doctor`'s `daemon shell` check is the
    # durable form: clearing per enqueue owner is a whack-a-mole invariant, so
    # something has to read the running process and say what is actually there.
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
  # to the run (`env_passthrough_prefixes` above), and §7.1's shared contract
  # is closed. A new shared name would arrive in every workflow's environment.
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
      --add-flags "--state ${home cfg.stateDir}" \
      --add-flags "--dagu-home ${home cfg.dagHome}"
  '';

  # Nix evaluation cannot write into $HOME, so the unit installs its two files
  # on every start. `install -m` rather than a symlink: Dagu reads these once at
  # startup, and a store symlink would hide which revision is live.
  installConfig = pkgs.writeShellScript "devman-dagu-install-config" ''
    set -eu
    registry="${cfg.registryDir}"
    state="${cfg.stateDir}"

    # The registry and the state root are the devenv module's to fill, but
    # their directories must exist before Dagu scans one of them (§11 Stage 3).
    "${pkgs.coreutils}/bin/mkdir" -p "$DAGU_HOME" "$registry/projects" "$registry/dags" "$state/projects"

    "${pkgs.gnused}/bin/sed" "s|${registryToken}|$registry|g" ${configFile} \
      > "$DAGU_HOME/.config.yaml.new"
    "${pkgs.coreutils}/bin/install" -m 0644 "$DAGU_HOME/.config.yaml.new" "$DAGU_HOME/config.yaml"
    "${pkgs.coreutils}/bin/rm" -f "$DAGU_HOME/.config.yaml.new"

    "${pkgs.coreutils}/bin/install" -m 0644 ${baseFile} "$DAGU_HOME/base.yaml"
  '';

  # The active plane is an atomic symlink. A path unit turns its replacement
  # into a deferred Dagu restart, because Dagu has no public reload operation.
  #
  # THE MARKERS ARE THE MAINTENANCE GATE'S HALF THAT LIVES HERE (§5, project
  # 038). `reload.pending` is written before the wait starts and removed only
  # after Dagu restarts, so `devman run` (`src/devman/run.py`) can refuse an
  # enqueue for the whole window rather than only the instant of the restart.
  # `devman doctor` reads both markers to say why a reload has not finished.
  #
  # THIS CLOSES THE RACE ONLY FOR THE `devman run` PATH. Dagu's own scheduled
  # enqueues, and the watcher's, do not pass through `devman run`'s Python
  # entry point, so a scheduled or watcher-fired run can still start in the gap
  # between the wait loop emptying and `systemctl try-restart` executing. That
  # is an accepted, documented limitation (§5.3) rather than an absolute
  # guarantee — nobody has built the daemon-side hook a full close would need.
  registryChangePath = lib.replaceStrings [ "$HOME" ] [ "%h" ] cfg.registryDir;
  reloadScript = pkgs.writeShellScript "devman-dagu-reload" ''
    set -eu
    registry="${cfg.registryDir}"
    state="${cfg.stateDir}"
    "${pkgs.coreutils}/bin/mkdir" -p "$state"
    pending="$state/reload.pending"
    blocked="$state/reload.blocked"
    last="$state/reload.target"

    # THE PLACEHOLDER GUARD. `installConfig`'s own `mkdir -p` (above) creates
    # `$registry` as a bare directory the first time `dagu.service` starts on a
    # machine with no generation activated yet, before Vendomat has ever
    # activated one — and that creation is itself a change to the watched
    # path, so the path unit fires for it. `readlink` on a bare directory
    # fails, which is exactly how this tells a placeholder from a real
    # activation: only Vendomat's atomic symlink replacement produces a target
    # (`GenerationStore._activate_number`).
    target="$(${pkgs.coreutils}/bin/readlink "$registry" 2>/dev/null || true)"
    if [ -z "$target" ]; then
      exit 0
    fi

    # THE SAME-GENERATION GUARD. A write inside the active generation that
    # does not move the pointer — `installConfig`'s `mkdir -p` populating a
    # fresh generation's `projects/` or `dags/` directory, or the
    # compatibility `project apply` path writing a projection — can retrigger
    # this path unit on its own (measured against the NixOS service test:
    # three triggers from one activation, two of them from writes below the
    # pointer rather than a pointer change). Restarting Dagu for a generation
    # that is already active earns nothing and risks the run-start race for no
    # reason, so skip the whole dance when the target has not changed.
    if [ -f "$last" ] && [ "$(${pkgs.coreutils}/bin/cat "$last")" = "$target" ]; then
      exit 0
    fi

    mark() {
      "${pkgs.coreutils}/bin/date" -u +%FT%TZ > "$1.new"
      "${pkgs.coreutils}/bin/mv" -f "$1.new" "$1"
    }

    mark "$pending"
    "${pkgs.coreutils}/bin/rm" -f "$blocked"

    waited=0
    max=${toString cfg.reloadMaxWaitSec}

    # MEASURED: `dagu ps` prints the literal line "No running processes" when
    # idle — it is never empty (Dagu 2.15.0). `[ -n "$(dagu ps)" ]` is
    # therefore true whether or not anything is running, and this loop never
    # terminated on its own; a restart happened only when `dagu ps` itself
    # transiently failed and `2>/dev/null` emptied its output by accident.
    # Caught by the VM test once `reload.pending` made a stuck loop visible
    # (project 038, §5) — matching every case not empty is what an idle Dagu
    # actually prints, not the absence of output.
    while [ "$(${lib.getExe cfg.package} ps 2>/dev/null || true)" != "No running processes" ]; do
      if [ "$waited" -ge "$max" ]; then
        mark "$blocked"
        echo "devman-dagu-reload: gave up after ''${max}s waiting for dagu ps to empty" >&2
        echo "devman-dagu-reload: Dagu was NOT restarted; the previous generation is still serving runs" >&2
        echo "devman-dagu-reload: once the run finishes, run: systemctl --user restart devman-dagu-reload.service" >&2
        exit 1
      fi
      ${pkgs.coreutils}/bin/sleep 1
      waited=$((waited + 1))
    done

    ${pkgs.systemd}/bin/systemctl --user try-restart dagu.service
    "${pkgs.coreutils}/bin/rm" -f "$pending"
    printf '%s' "$target" > "$last.new"
    "${pkgs.coreutils}/bin/mv" -f "$last.new" "$last"
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
        The registry root (§9.2) — `dags/` and the `workflows/` projection.
        `$HOME` is expanded by the unit's ExecStartPre, not by Nix, because a
        user service has one home per user. It must match `devman.registryDir`
        in every repository that registers.

        **Not moved to `~/.config/devman` yet** — see `devman.registryDir`'s
        description in `modules/devenv.nix` for why (§6.2a is the blocker).
      '';
    };

    stateDir = mkOption {
      type = types.str;
      default = "$HOME/.local/state/devman";
      description = ''
        The state root (§11 Stage 3) — `metadata.json` and the kept copies of
        each repository's own `.devman/triggers.toml` and `.devman/writes.toml`,
        regenerated on every shell entry. `$HOME` is expanded by the unit's
        ExecStartPre, not by Nix. It must match `devman.stateDir` in every
        repository that registers.
      '';
    };

    reloadMaxWaitSec = mkOption {
      type = types.ints.positive;
      default = 300;
      description = ''
        How long the reload adapter waits for `dagu ps` to empty before it
        gives up and leaves the running Dagu process alone (§5, project 038).

        **5 minutes is a stated bound, not a measurement** — nobody has timed
        the longest run this machine's workflows are expected to take (the
        same honesty `queues` states about `llm`). Raise it for a machine that
        runs long jobs; the cost of raising it is a later reload, not a lost
        run.

        On timeout the adapter writes `reload.blocked` under
        `services.devman-dagu.stateDir` and exits non-zero, so
        `systemctl --user status devman-dagu-reload.service` and
        `devman doctor` both show it. The active Dagu process, and the
        generation it is running, are both untouched. Restart the reload
        service by hand once the run finishes:
        `systemctl --user restart devman-dagu-reload.service`.
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

        # THE SIXTH NAME, AND IT IS THE ONLY ONE WHOSE LIMIT IS NOT ABOUT THIS
        # MACHINE (§7.1 as amended by project 022, forced by 020's measurement).
        #
        # The other five bound a local resource — cores, the GPU, a lock. `llm`
        # bounds a QUOTA HELD SOMEWHERE ELSE: requests per minute, tokens per
        # minute, and money, shared by every repository on this machine at once.
        # 020 §3 is the argument. For CPU work a queue buys only a quieter peak,
        # because the machine does the same total work either way. For a metered
        # resource it buys correctness: 54 concurrent calls against a per-minute
        # limit return `429` and a partial fan-out, and the same 54 at a time
        # succeed for the same money. A queue converts a breached limit into a
        # longer wall clock, which is the one trade this workload needs.
        #
        # Sharing `heavy` was the alternative and it tunes neither: `heavy` is
        # sized against local builds, and a number that is right for a compiler
        # is right for an API quota only by accident. `gpu` is already the local
        # inference server (`groups/changelog/`), which is not metered at all.
        #
        # **2 IS A STATED BOUND AND NOT A MEASUREMENT**, exactly as the other
        # five are (AGENTS_GUIDE.md §1: "nobody has measured it"). devman cannot
        # measure another vendor's quota, and the honest thing is to say so
        # rather than to imply a number was derived. It is deliberately below
        # every published per-minute floor, because the failure it prevents is
        # not slowness — it is 54 runs recorded green or red for a reason
        # unrelated to the work.
        llm = 2;
      };
      description = ''
        Queue names and their concurrency limits (§7.1). The machine states how
        much may run at once, never what runs (§4).

        **`llm` is the one whose limit is not about this machine.** Its
        concurrency stands in for an external, shared, metered quota rather than
        for a local resource, and 2 is a stated bound rather than a measured one
        (§7.1 as amended by 022).

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
      # on this unit would govern only the runs the daemon enqueues itself. The
      # trigger clears it for every other path, in one place, so that
      # `default_shell` governs (S13, `src/devman/run.py`).
      #
      # THE DAEMON DOES ENQUEUE, and the sentence that used to sit here said it
      # did not: "the daemon enqueues only under a `schedule:`, which §8 does not
      # use". Two workflows have carried a `schedule:` since stage 7 —
      # `groups/base/workflows/maintain.yaml` and
      # `.devman/workflows/plane-report.yaml` — so the claim has been false for a
      # whole stage, and every scheduled run took the user manager's `SHELL`
      # rather than `default_shell`. That is S9's failure with nobody at the
      # prompt to see it. The superseded state is recorded in
      # `009-code-review/STAGE_9_LOG.md` S-7 (rule 1).
      #
      # `UnsetEnvironment` is the form that works. `SHELL` is INHERITED from the
      # systemd user manager, so `environment.SHELL = null` removes nothing —
      # there is nothing set on the unit to remove.
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

        # The daemon's own half of S13 (009 P1-3). Every other path into the
        # plane clears `SHELL` in `devman run`; a scheduled run has no such
        # path, because Dagu enqueues it itself from this process. Unsetting it
        # here is what makes `default_shell` govern both.
        #
        # `UnsetEnvironment`, not `environment.SHELL = null`: the variable is
        # inherited from the systemd user manager, so there is nothing on the
        # unit for a null to remove.
        UnsetEnvironment = "SHELL";
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

    # Vendomat changes the active registry by replacing one symlink. Watch that
    # pointer and restart Dagu after the replacement. The reload script waits
    # for active runs. The Dagu state directory stays outside the generation,
    # so this restart does not lose run history.
    systemd.user.paths.devman-dagu-reload = {
      wantedBy = [ "paths.target" ];
      pathConfig = {
        PathChanged = registryChangePath;
        Unit = "devman-dagu-reload.service";
      };
    };

    systemd.user.services.devman-dagu-reload = {
      description = "reload Dagu after the active devman plane changes";
      environment.DAGU_HOME = cfg.dagHome;
      path = cfg.servicePath;
      serviceConfig = {
        Type = "oneshot";
        ExecStart = reloadScript;
      };
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
