# The repo interface — a devenv module a project imports through devenv.yaml.
#
# STAGE 1 (CONCEPT.md §13). Nix declares selection and identity; YAML declares
# workflows (§7.4). Three keys and the repo's own primitives:
#
#   devman = {
#     enable  = true;
#     project = "pyjutsu";
#     groups  = [ "base" ];
#   };
#
#   inputs:
#     devman:
#       url: "git+https://github.com/Bullish-Design/devman?ref=main&rev=<commit>"
#   imports:
#     - devman/modules
#
# The file MUST be named devenv.nix. devenv resolves `<input>/<subdir>` to
# `inputs.<input> + /<subdir>` and then looks for `devenv.nix` inside it; a
# `default.nix` is never consulted, and the error names a file you did not
# write (B4).
#
# `git+https` records `rev` and `narHash` in devenv.lock, and **so does
# `git+file`** — its real constraint is that it reads COMMITTED files only, so a
# consumer cannot see an uncommitted edit. Use `path:` for the one repository
# under active edit, `git+file:` for every other local consumer.
#
# This comment said the opposite for six stages (009 P2-5). B4's original probe
# recorded no `rev` for a `git+file` input; `FINDINGS.md` supersedes it with the
# decisive evidence — `nix-meta/flake.lock` and `vendomat/flake.lock` both record
# `rev` and `narHash` for their local inputs — and CONCEPT.md §3.2 has carried
# the corrected form since. `USER.md` and `README.md` tell a developer to pin
# with `git+file:`, so this file was contradicting the guide it belongs to.
#
# The module takes `pkgs` from the consuming repo's devenv, which pins
# `devenv-nixpkgs/rolling`. The NixOS module takes `pkgs` from the machine.
# Neither reads the plane's own `nixpkgs` input (§3.1, B1).
{ pkgs, lib, config, ... }:

let
  inherit (lib) mkEnableOption mkIf mkOption types;

  cfg = config.devman;

  # THE IDENTITY GRAMMAR, AT THE REPO BOUNDARY (009 P1-5).
  #
  # `devman.project` was a bare `types.str`, so `bad@project` registered — and
  # then `devman run` rendered `bad@project.check`, which the pinned Dagu
  # refuses. Worse characters reached path construction: the name becomes
  # `projects/<project>/`, `dags/<project>.<workflow>.yaml`, and the sweep loops
  # below. A slash, an empty name or `..` selects a registry subpath.
  #
  # The character set is Dagu's own, measured (S-11). The leading character is
  # restricted further so `-flag` and `.hidden` cannot be names.
  #
  # It is duplicated in `src/devman/registry.py`, because §3.1 says what the two
  # interfaces share must be TEXT and a Python function is not text.
  # `tests/fixtures/identity.json` is the shared table, and three readers assert
  # against it — the unit suite, the conformance suite against the pinned Dagu,
  # and a `flake.nix` check that reads the same file with `fromJSON`.
  #
  # This is a `throw` rather than a `types.strMatching`, for the reason the group
  # throw below gives: "does not match a regex" does not tell an author what to
  # do. It fires at evaluation time, which is before any path exists.
  identityGrammar = "[A-Za-z0-9][A-Za-z0-9._-]*";

  projectName =
    if builtins.match identityGrammar cfg.project != null then
      cfg.project
    else
      throw ("devman: '" + cfg.project + "' cannot be a project name. "
        + "A name holds letters, digits, '.', '-' and '_', and starts with a letter "
        + "or a digit. Dagu refuses every other character in a DAG name (S-11), and "
        + "the name becomes a registry directory and a DAG file name (§9.2). "
        + "Set devman.project to a name that matches, and enter the shell again.");

  # ---------------------------------------------------------------------------
  # §7.3 resolution, at evaluation time
  #
  # Groups resolve in the order the repo lists them, each shadowing the last.
  # Shadowing is whole-file, never a field merge. The repo's own
  # `.devman/workflows/` is the final layer and is applied by the projection
  # script below, because which files are in a working tree is a run-time fact.
  groupsRoot = ../groups;

  # One group's workflows, as `<name> -> <store file>`.
  #
  # `builtins.readFile` rather than the path itself, and the reason is devenv's
  # evaluation cache. Interpolating a path copies the file to the store, and
  # devenv does not notice when that file's CONTENT changes: the projection then
  # keeps pointing at the previous store path, shell entry after shell entry.
  # `readFile` is a read the cache tracks, so an edited group file re-evaluates.
  #
  # A repository pinning a `git+https` rev never meets this, because a changed
  # group file is a changed rev. A repository importing `./modules` — this one,
  # adopting itself (criterion 16) — meets it on every edit.
  groupFiles = group:
    let
      dir = groupsRoot + "/${group}/workflows";
    in
    if !builtins.pathExists (groupsRoot + "/${group}") then
      throw "devman: group '${group}' does not exist. There is no ${toString (groupsRoot + "/${group}")}."
    else if !builtins.pathExists dir then
    # A group may ship no workflows at all. Two shapes use this branch, and the
    # second was measured at stage 7.
    #
    # A TRIGGERS-ONLY GROUP is how a repository opts into reactivity without
    # also inheriting somebody's workflows, which is what keeps §7.4's "an
    # inherited workflow you never trigger costs nothing" true — a *triggered*
    # workflow costs plenty (§8).
    #
    # A TOMBSTONE is a group that has been deleted. The throw above is an
    # EVALUATION failure, so a repository that re-pins to a rev where its group
    # is gone cannot enter its shell at all — a flag day rather than a
    # migration. A directory that ships no `workflows/` evaluates and projects
    # nothing, so a stale pin keeps working and the repository renames its group
    # when it is next edited (STAGE_7_LOG.md, I-6 and S-3).
    #
    # A tombstone MUST hold at least one file, because git cannot carry an empty
    # directory, and MUST NOT hold a `triggers.toml`, because the mapping would
    # keep firing a workflow the repository no longer projects.
      { }
    else
      lib.mapAttrs'
        (file: _:
          let name = lib.removeSuffix ".yaml" file; in
          # The codec's one refusal, at evaluation time (§9.2, S-12). A dot in a
          # workflow name would make the last dot of `<project>.<workflow>`
          # ambiguous, and the DAG name no longer injective. A group ships to
          # every repository that takes it, so this is the cheapest place to
          # find it: the group author sees it, once, instead of every taker.
          if lib.hasInfix "." name then
            throw ("devman: group '${group}' ships '${file}', and a workflow name may not hold a '.'. "
              + "A DAG name is <project>.<workflow>, and the last '.' is the separator (§9.2). "
              + "A project name may hold dots; a workflow name may not.")
          else
            lib.nameValuePair
              name
              (pkgs.writeText "devman-${group}-${file}" (builtins.readFile (dir + "/${file}"))))
        (lib.filterAttrs
          (file: kind: kind == "regular" && lib.hasSuffix ".yaml" file)
          (builtins.readDir dir));

  # The whole of §7.3's group resolution, as `<name> -> { group; file; shadows; }`.
  #
  # `shadows` is the groups this name displaced, in the order the repo listed
  # them. It costs nothing at evaluation time and it is what makes the registry
  # record the resolution rather than only its result: `devman show` prints
  # which group a file came from, and `doctor` diffs a repo's own override
  # against the group version it shadows (§10 check 4, §15.6). The same field is
  # what §12.4's measurement reads.
  resolved = lib.foldl'
    (acc: group:
      acc // lib.mapAttrs
        (name: file: {
          inherit group file;
          shadows =
            if acc ? ${name}
            then acc.${name}.shadows ++ [ acc.${name}.group ]
            else [ ];
        })
        (groupFiles group))
    { }
    cfg.groups;

  # ---------------------------------------------------------------------------
  # Reactivity — which glob fires which workflow (§8)
  #
  # `groups/<group>/triggers.toml` is a table of `<glob> = <workflow>`.
  # It is GROUP CONTENT, and where it sits was the sharpest design question in
  # stage 3, because three obvious homes are all closed:
  #
  #   * not in the workflow file — Dagu rejects an unknown top-level key
  #     outright, and §7.2 says a workflow is Dagu configuration from the first
  #     line to the last (A5).
  #   * not a Nix option here — that would make the machine learn a project fact
  #     (§4), and §7.4 says there is no per-workflow Nix option.
  #   * not a second file the watcher reads at run time — the watcher would then
  #     need §7.3's resolution too, and there would be two implementations of it.
  #
  # So it is resolved here, at evaluation time, exactly as workflows are, and
  # recorded in the registry entry. The watcher reads the entry and nothing else.
  #
  # Resolution is WHOLE-FILE, like §7.3's: the last group the repository lists
  # that ships a `triggers.toml` wins outright. There is no merge, for the same
  # reason §7.3 refuses one — the result would be hard to predict from either
  # file alone.
  #
  # TOML READ WITH `readFile`, FOR TWO REASONS, AND NOT FOR A THIRD.
  #
  #   1. It is the construct stage 1's S8 measured as tracked by devenv's
  #      evaluation cache. `import` is untested there, and this file's content
  #      decides what the machine does when a developer saves — it must not go
  #      stale silently.
  #   2. A mapping is DATA. A `.nix` file would let a group evaluate arbitrary
  #      Nix, including an import from a derivation, in every repository that
  #      takes it. Workflows are inert YAML for the same reason (§7.2).
  #
  # The reason it is NOT: a first draft of S7 blamed `import` for a stale
  # mapping, and the cause was elsewhere — a group file inside a `path:` flake
  # input is invisible to devenv's evaluation cache whatever construct reads it,
  # until `.devenv/nix-eval-cache.db` is deleted. Both constructs behave the same
  # there, and the entry says so.
  groupTriggers = group:
    let
      file = groupsRoot + "/${group}/triggers.toml";
    in
    if builtins.pathExists file
    then { inherit group; map = builtins.fromTOML (builtins.readFile file); }
    else null;

  triggers = lib.foldl'
    (acc: group: let t = groupTriggers group; in if t == null then acc else t)
    null
    cfg.groups;

  # ---------------------------------------------------------------------------
  # The projection (§9.2), and the rare path that performs it
  #
  #   <registry>/projects/<project>/metadata.json
  #   <registry>/projects/<project>/workflows/<workflow>.yaml -> the winner
  #   <registry>/dags/<project>.<workflow>.yaml               -> the line above
  #
  # `dags/` is Dagu's flat view of `projects/`. A DAG is keyed by its file's
  # base name, so two projects both projecting `check.yaml` are reported as a
  # duplicate and both vanish from `dagu ls`, from the web UI and from the
  # scheduler. See nix/nixos-module.nix, which points `dags_dir` at it.
  #
  # THE SEPARATOR IS A DOT, AND THIS IS ONE OF TWO PLACES THAT RENDERS IT.
  #
  # The other is `Registry.dag_name()` in `src/devman/registry.py`, which is the
  # codec's home and carries the measurement. The two must agree byte for byte:
  # this side writes the link and the CLI side reads it, so a disagreement makes
  # every trigger in every repository refuse. There is no shared text layer for
  # a Python function and a shell script, which is why the rule lives in a
  # comment on both sides rather than in a file neither can import (§3.1).
  #
  #   join with `.`;  a dot is REFUSED in the workflow half, never the project
  #
  # `<project>-<workflow>` was not injective — `devman-b` + `check` and `devman`
  # + `b-check` render one name (S6, S-12).
  #
  # STAGE 6: THE PER-PROJECT FILE IS GENERATED, NOT SYMLINKED, AND THE REASON IS
  # THE SCHEDULE.
  #
  # `projects/<p>/workflows/<w>.yaml` used to be a symlink to the group file, so
  # every projected DAG inherited `working_dir: ${DEVMAN_PROJECT_DIR}` and
  # `log_dir: ${DEVMAN_PROJECT_DIR}/…` from the machine's `base.yaml`. Both
  # interpolate from **whoever enqueues**, which is fine for `devman run` and
  # impossible for Dagu's own scheduler: under `schedule:` the enqueueing process
  # is the daemon, which has one environment for the whole machine, so both
  # fields stayed literal and the run worked in a directory named
  # `${DEVMAN_PROJECT_DIR}` (`STAGE_4_LOG.md`, S2).
  #
  # Measured on a throwaway carrying a byte copy of the installed `base.yaml`: a
  # per-project file that STATES the three values schedules correctly — the
  # daemon dispatched on the minute, `working_dir` and the variable resolved, the
  # logs landed under the project, and the machine's inherited exit handler
  # appended to that project's `metadata.jsonl` (`STAGE_5_LOG.md` S12,
  # `STAGE_6_LOG.md` S2).
  #
  # So the generated file is a HEADER plus the source body, byte for byte:
  #
  #     env:
  #       - DEVMAN_PROJECT_DIR: /home/you/project      # or DEVMAN_SELF_DIR (§11)
  #     working_dir: /home/you/project
  #     log_dir: /home/you/project/.devman/.runs/logs
  #     <the group file, or this repository's own override, unchanged>
  #
  # `env:` rather than `params:`, because the header must not have to edit a
  # `params:` block the workflow already declares. Measured: with `env:` set and
  # `params: [DEVMAN_PROJECT_DIR: ""]` also present, the step and the exit
  # handler both saw the env value, and the workflow's other parameters kept
  # their own defaults (S2).
  #
  # THE HEADER ADDS; IT NEVER OVERWRITES. A body that states its own
  # `working_dir` or `log_dir` keeps them — that is §11's cross-repo workflow,
  # which must also be given `DEVMAN_SELF_DIR` rather than `DEVMAN_PROJECT_DIR`,
  # because a workflow that triggers other workflows must not hold the name it
  # passes to its children.
  #
  # The cost is stated in `STAGE_6_LOG.md` S1 rather than discovered: a
  # repository's own `.devman/workflows/x.yaml` is no longer read live by Dagu.
  # Editing it needs one shell entry to re-project.
  #
  # This script forks. It runs only when the rendered entry differs from the one
  # on disk, which the guard in `enterShell` decides without forking at all.
  # STAGE 3 OF PROJECT 009 MOVED THE PROJECTION INTO PYTHON, AND THIS IS ALL
  # THAT IS LEFT OF IT HERE.
  #
  # What used to be here decided the directory variable with
  # `grep -q 'DEVMAN_SELF_DIR'`, decided the `env:` header with
  # `grep -q '^env:'`, built the entry with `@PATH@` substitution, and validated
  # no identity at all. Each of those four was a finding — P1-1, P1-1's severe
  # case, P2-1 and P1-5 — and `src/devman/` already answered every one of them
  # correctly from a parsed document. The renderer lives there now, and this
  # file states the plan and runs it.
  #
  # `renderer` is built under THIS repository's nixpkgs, exactly as
  # `installClient` builds `nix/dagu.nix`. The reason is the guard and not the
  # charter: a `devman` found on PATH is a run-time fact, so its identity could
  # not enter `planFile`, so the guard could not observe it. See
  # `nix/renderer.nix`, which carries the amendment to §3.1.
  # THE RENDERER'S SOURCE IS INVISIBLE TO DEVENV'S EVALUATION CACHE, AND THIS
  # IS THE SAME MEASUREMENT `groupFiles` ABOVE RECORDS, ONE LAYER DOWN.
  #
  # `nix/renderer.nix` builds a `fileset.toSource` over `../src`. Interpolating
  # a path copies it to the store, and devenv does not notice when the CONTENT
  # of a copied path changes — so an edited `src/devman/project.py` kept
  # producing the previous renderer's store path, shell entry after shell entry.
  #
  # Measured while writing stage 3, and it looked exactly like a bug in the new
  # code: the projection refused correctly and then published one workflow
  # anyway, because the renderer actually running was a build from before that
  # behaviour was fixed. `planFile` recorded that stale path, so the guard was
  # satisfied — everything agreed with everything, and all of it was old.
  #
  # `builtins.readFile` IS a read the cache tracks, which is why `groupFiles`
  # uses it. Hashing every source file the renderer is built from puts the same
  # tracked read on this derivation: change any of them and the hash changes,
  # the derivation changes, `planFile` changes, and the guard re-projects.
  #
  # A repository pinning a `git+https` rev never meets this — a changed source
  # is a changed rev. devman adopting itself (criterion 16) meets it on every
  # edit, which is the case this exists for.
  rendererSource = lib.concatMapStrings
    (file: builtins.readFile (../src/devman + "/${file}"))
    (builtins.attrNames
      (lib.filterAttrs
        (file: kind: kind == "regular" && lib.hasSuffix ".py" file)
        (builtins.readDir ../src/devman)));

  renderer = (pkgs.callPackage ../nix/renderer.nix {
    dagu = pkgs.callPackage ../nix/dagu.nix { };
  }).overrideAttrs (_: {
    devmanSourceHash = builtins.hashString "sha256" rendererSource;
  });

  # ONE FILE HOLDING EVERYTHING NIX DERIVED, AND ITS STORE PATH IS THE GUARD.
  #
  # `plan` used to record the projection script's store path. That path changed
  # when a group file changed, but NOT when `triggers.toml` changed — triggers
  # reached the entry by a different route — so `plan` equality did not imply
  # the projection was current, and the guard had to compare the whole rendered
  # entry instead. Comparing the whole entry is what forced the entry to be
  # rendered twice, once in bash and once in Python, and that is P2-1.
  #
  # Fixed by construction: this is one `writeText` holding the groups, the
  # resolved workflows, the triggers and the renderer's own store path, so its
  # path is a hash of all of it. Any change to any derived fact changes the
  # path. `plan` equality therefore really does imply that every derived field
  # is unchanged, which leaves the guard two run-time facts to compare — where
  # this checkout sits, and which overrides exist.
  #
  # The next reader will want to delete the `plan` comparison as redundant. It
  # is not: it is the only thing that notices a changed group file, a changed
  # trigger map, or a changed renderer.
  planFile = pkgs.writeText "devman-plan-${projectName}.json" (builtins.toJSON {
    schema = 4;
    project = projectName;
    groups = cfg.groups;
    # §7.3's OUTCOME, not its inputs. `shadows` is what `doctor` check 4 diffs
    # an override against, and `source` is the store path that won.
    workflows = lib.mapAttrs
      (_: w: { inherit (w) group shadows; source = "${w.file}"; })
      resolved;
    inherit triggers;
    renderer = "${renderer}";
  });

  # ---------------------------------------------------------------------------
  # THE REGISTRY ENTRY'S SCHEMA — the history, kept because each step has a
  # reason a later reader will otherwise re-litigate.
  #
  # SCHEMA 2 added `workflows`, and it exists for `doctor` (§10) rather than for
  # the projection, which never reads it. Schema 1 recorded the inputs to §7.3's
  # resolution — `groups` and `local` — and not its outcome, so nothing on disk
  # said which file won or what it displaced. Four of §10's six checks want the
  # outcome, and check 4 — "shadowed files and their drift" — cannot be computed
  # from schema 1 at all: to diff a repo's `.devman/workflows/check.yaml`
  # against the group version it shadows, something must record which group
  # version that was. §12.4's measurement asks the same question.
  #
  #   "workflows": {
  #     "check": {"group":"base","shadows":[],"source":"/nix/store/..."}
  #   }
  #
  # `local` stays, and the two are read together: a name in `local` is the
  # winner, and `workflows.<name>.source` is then what it shadows. Nix knows the
  # group half at evaluation time; which files are in a working tree is a
  # run-time fact, which is why `local` is still filled by the hook.
  #
  # SCHEMA 3 adds `triggers`, for the same reason schema 2 added `workflows`:
  # the watcher and `doctor` need the OUTCOME of a resolution that only Nix can
  # perform. It is `null` for a repository that takes no group declaring any,
  # which is every repository until one opts in.
  #
  # SCHEMA 4 changes what `plan` MEANS, and adds no field. It was the projection
  # script's store path; it is now `planFile`'s. The difference is that the
  # script's path did not change when `triggers.toml` changed, so `plan`
  # equality did not imply the projection was current — which is why the guard
  # compared the whole entry, which is why the entry was rendered twice, which
  # is P2-1 (009 stage 3). `doctor` reports a schema it does not know rather
  # than misreading it.
  #
  # The entry itself is written by `src/devman/project.py`, in a fixed layout so
  # that the guard below can slice three fields out of it without forking.

  # A thin wrapper, and rule 8's whole point: Python for the logic, shell for
  # the exec. `--root` and `--local` are run-time facts and stay arguments;
  # everything Nix knows is in the plan.
  projectScript = pkgs.writeShellScript "devman-project-${projectName}" ''
    exec ${renderer}/bin/devman-project apply \
      --plan ${planFile} \
      --registry "$2" \
      --root "$1" \
      "''${@:3}"
  '';

in
{
  options.devman = {
    enable = mkEnableOption "devman automation plane membership for this repository";

    project = mkOption {
      type = types.str;
      description = ''
        Project identity, never a path (§9.1).

        Required, with no default. Identity that defaults to the directory name
        breaks criterion 11 by construction: rename the directory and the repo
        re-registers as new and loses its run history (C5).

        **A name holds letters, digits, `.`, `-` and `_`, and starts with a
        letter or a digit.** The character set is Dagu's own, measured (S-11),
        and the name becomes a registry directory and a DAG file name — so a
        slash, a `..` or an empty name would select a registry subpath (009
        P1-5). `src/devman/registry.py` states the same grammar for the CLI, and
        `tests/fixtures/identity.json` is the shared table that proves the two
        agree.
      '';
    };

    groups = mkOption {
      type = types.listOf types.str;
      default = [ "base" ];
      example = [ "base" "format" ];
      description = "Workflow groups this repository inherits, in precedence order (§7.3). `[ ]` is legal: the repository then has only its own `.devman/workflows/`.";
    };

    registryDir = mkOption {
      type = types.str;
      default = "$HOME/.local/share/devman";
      description = "The registry root (§9.2). `$HOME` is expanded by the shell hook, not by Nix. It must match `services.devman-dagu.registryDir` on the machine.";
    };

    installClient = mkOption {
      type = types.bool;
      default = true;
      description = "Put the Dagu client on PATH, so a trigger in this repo can run `dagu enqueue` locally (E2). Calls the same nix/dagu.nix the NixOS module calls, under this repo's nixpkgs (§3.1).";
    };
  };

  config = mkIf cfg.enable {
    packages = lib.optional cfg.installClient (pkgs.callPackage ../nix/dagu.nix { });

    # -------------------------------------------------------------------------
    # §5.2: registration runs in enterShell, guarded by a content hash.
    #
    # Two rules govern every line below, and both are requirements rather than
    # observations (C1, C2):
    #
    #   * IT MUST BE IDEMPOTENT. devenv runs the whole hook twice per
    #     `devenv shell` — once in a throwaway subprocess that only snapshots
    #     `env`, once for real.
    #   * IT MUST FORK NOTHING on the common path. Its cost is charged twice, on
    #     the critical path of every shell the developer opens. A `sed` and a
    #     `cat` cost +23 ms per entry; bash parameter expansion and `$(<file)`
    #     cost +4 ms.
    #
    # And one consequence that shapes what the hook may say: THE BRANCH THAT
    # WRITES CANNOT REPORT. devenv discards the capture subprocess's stdout and
    # its stderr, and that is the firing that performs the write; by the time
    # the real shell runs the hook the entry already matches. There is no
    # "devman: registered" line and there cannot be one (C5). Everything the
    # developer must see is on a branch that does not write — a refusal here, or
    # `devman doctor` later.
    #
    # Nothing here uses `return`: the hook is sourced, so a `return` would skip
    # the rest of devenv's own shell setup.
    enterShell = ''
      devman_root="$DEVENV_ROOT"
      devman_reg="${cfg.registryDir}"
      devman_meta="$devman_reg/projects/${projectName}/metadata.json"

      # §15.2: `.devman/` IS THE REPOSITORY'S. devman reserves three names
      # inside it — `workflows/`, `.runs/` and `triggers.toml` — and never
      # reads, writes or inspects anything else there. The third arrived with
      # 009 P3-3, as §7.3's last layer applied to triggers.
      #
      # There used to be a whitelist here: any other top-level entry made
      # registration refuse and report. It was removed by decision at stage 7,
      # and the reason is that it contradicted §7.4. The plane's whole claim is
      # that it names the smallest vocabulary it has to and leaves the rest to
      # the repository; a directory the repository already owned is not the
      # place to make an exception. `.devman/` is open for whatever else a
      # repository or an add-on wants to keep there.
      #
      # Nothing replaces it, deliberately. A `doctor` check that listed
      # unrecognised entries would be the same opinion with a softer voice, and
      # §15.7 says `doctor` does not guess.
      #
      # So there is no directory listing on this path at all, which also makes
      # the hook cheaper than the version that policed it.

      devman_disk=""
      [ -f "$devman_meta" ] && devman_disk=$(<"$devman_meta")

      # §7.3'S LAST LAYER IS A GENERATED COPY SINCE STAGE 6, SO THE GUARD HAS TO
      # NOTICE AN EDIT AND NOT ONLY AN ADD OR A REMOVE (S-5a).
      #
      # `local` records names, and a name does not change when a file is edited
      # in place. So an edited `.devman/workflows/*.yaml` did not reach Dagu at
      # the next shell entry: the entry matched, nothing was re-projected, and
      # the next run executed the PREVIOUS version, silently, with `doctor`
      # reporting nothing wrong.
      #
      # THE TEST IS EXACT RATHER THAN A DIGEST. A `sha256sum` per override is a
      # fork, which §5.2 forbids here, and a hash built with parameter expansion
      # over a few kilobytes of bash is both slow and probabilistic. What is both
      # forkless and exact is to compare the thing that actually matters: the
      # projection Dagu reads must END WITH the override's body, byte for byte.
      # `devman_project` writes a generated header and then the body unchanged,
      # so tail equality is the whole test.
      #
      # THE TAIL IS TAKEN BY SLICE, NOT BY `%`, AND THAT IS A MEASUREMENT.
      # `''${devman_have%"$devman_body"}` reads as the obvious way to say it and
      # costs 5.6 ms per firing over devman's five overrides — 11 ms per shell
      # entry, which breaks criterion 7 on its own. The slice below is the same
      # test and costs 0.76 ms: bash's pattern removal scans, a slice does not.
      # The two `$(<file)` reads are 0.37 ms together and do NOT fork, which is
      # the part §5.2 put in doubt.
      #
      #   pre-R-8, names only  0.132 ms per firing   0.26 ms per shell entry
      #   R-8, tail slice      1.409 ms per firing   2.82 ms per shell entry
      #
      # A repository with no override pays the glob and nothing else, which is
      # every repository until it writes one.
      #
      # It is also stronger than a recorded digest, because it compares against
      # the projection instead of against a number this hook wrote earlier: a
      # projection edited, truncated or half-written in place is caught too,
      # which is §9.3's promise.
      #
      # An override that is empty — or holds only newlines, which `$(<file)`
      # strips to the same thing — is not compared. There is no body to match,
      # and a header alone is its correct projection.
      devman_local=""
      devman_local_args=()
      devman_names="${lib.concatStringsSep " " (lib.attrNames resolved)}"
      devman_stale=""
      for devman_f in "$devman_root"/.devman/workflows/*.yaml; do
        [ -e "$devman_f" ] || continue
        devman_b="''${devman_f##*/}"
        devman_local="$devman_local, \"''${devman_b%.yaml}\""
        devman_local_args+=(--local "''${devman_b%.yaml}")
        devman_names="$devman_names ''${devman_b%.yaml}"

        devman_proj="$devman_reg/projects/${projectName}/workflows/$devman_b"
        if [ -f "$devman_proj" ]; then
          devman_body=$(<"$devman_f")
          devman_have=$(<"$devman_proj")
          if [ -n "$devman_body" ] \
             && [ "''${devman_have: -''${#devman_body}}" != "$devman_body" ]; then
            devman_stale=1
          fi
        else
          devman_stale=1
        fi
      done
      devman_local="''${devman_local#, }"

      # §7.3'S LAST LAYER NOW COVERS TRIGGERS TOO (009 P3-3), AND THE GUARD HAS
      # TO NOTICE AN EDIT TO IT FOR THE SAME REASON S-5a EXISTS.
      #
      # `.devman/triggers.toml` is this repository's own trigger layer. It is
      # read at RUN time by the renderer, like `.devman/workflows/`, because
      # which files are in a working tree is a run-time fact — so Nix cannot put
      # it in `planFile` and `plan` equality cannot cover it.
      #
      # The projection keeps a verbatim copy beside the registry entry, and this
      # compares the two. Two `$(<file)` reads and a string compare: exact,
      # forkless, and the same shape as the override tail-test above. A
      # repository that ships no such file pays one `[ -f ]` on each side.
      devman_trig="$devman_root/.devman/triggers.toml"
      devman_trig_kept="$devman_reg/projects/${projectName}/triggers.toml"
      if [ -f "$devman_trig" ]; then
        if [ ! -f "$devman_trig_kept" ]; then
          devman_stale=1
        else
          devman_trig_now=$(<"$devman_trig")
          devman_trig_was=$(<"$devman_trig_kept")
          [ "$devman_trig_now" = "$devman_trig_was" ] || devman_stale=1
        fi
      elif [ -f "$devman_trig_kept" ]; then
        devman_stale=1
      fi

      # §9.3 SAYS THE PROJECTION IS RECONSTRUCTABLE BY ENTERING THE SHELL, AND
      # THE GUARD USED TO CHECK TOO LITTLE FOR THAT TO BE TRUE.
      #
      # It compared the rendered ENTRY against disk, plus one `[ -d dags ]`. So
      # deleting the whole registry was repaired by re-entering (stage 2, S13)
      # and deleting ONE `dags/` link was not: the entry still matched, the
      # directory still existed, and the workflow stayed unrunnable by name
      # until somebody changed this file. Measured twice — once by a link a
      # colliding projection took over, once by removing one by hand
      # (`STAGE_5_LOG.md`, S7).
      #
      # One `[ -L ]` per projected workflow, which is a bash builtin and forks
      # nothing (§5.2). It tests existence and not the target, deliberately:
      # reading a symlink costs a fork, and a link pointing at ANOTHER project's
      # file is `devman doctor`'s projection check, on a path that is allowed to
      # spend a process.
      #
      # IT TESTS THE CURRENT SHAPE, WHICH IS WHAT MAKES THE CODEC MIGRATE ITSELF
      # (S-12). A repository last projected under `<project>-<workflow>` has no
      # link at this name, so the guard fires, the projection runs, and it comes
      # out on the new shape with the old link swept. Entering the shell is the
      # whole migration; nothing else has to be run anywhere.
      devman_relink=""
      for devman_n in $devman_names; do
        [ -L "$devman_reg/dags/${projectName}.$devman_n.yaml" ] || devman_relink=1
      done

      # THE GUARD COMPARES THREE SLICED FIELDS, AND IT USED TO COMPARE THE
      # WHOLE ENTRY (009 stage 3).
      #
      # It could, because bash rendered the entry itself, from a template with
      # `@PATH@` and `@LOCAL@` placeholders. That is what made a repository path
      # holding a quote, a backslash or a colon-space corrupt the entry (P2-1),
      # and it is why the projection could not move to a writer that encodes
      # JSON properly: proper encoding does not match naive substitution, so the
      # guard would fire on every shell entry, forever.
      #
      # So the guard stopped comparing bytes it renders and started comparing
      # three fields it slices out of the entry Python wrote:
      #
      #     disk "path"   == $DEVENV_ROOT     this repository has not moved
      #     disk "plan"   == ${planFile}      nothing Nix derived has changed
      #     disk "local"  == $devman_local    the override set has not changed
      #
      # `plan` covers every derived field by construction — see `planFile`. The
      # two run-time facts are the other two. The whole-entry compare lost
      # nothing.
      #
      # The slices fork nothing; the hook already sliced `path` this way.
      # `src/devman/project.py` writes the entry in a fixed layout SO THAT these
      # three anchors are sliceable, and says so.
      devman_recorded=""
      devman_plan=""
      devman_locals=""
      case "$devman_disk" in
        *'"path": "'*)
          devman_recorded="''${devman_disk#*'"path": "'}"
          devman_recorded="''${devman_recorded%%'"'*}"
          ;;
      esac
      case "$devman_disk" in
        *'"plan": "'*)
          devman_plan="''${devman_disk#*'"plan": "'}"
          devman_plan="''${devman_plan%%'"'*}"
          ;;
      esac
      case "$devman_disk" in
        *'"local": ['*)
          devman_locals="''${devman_disk#*'"local": ['}"
          devman_locals="''${devman_locals%%']'*}"
          ;;
      esac

      # THE ONE THING A FORKLESS COMPARISON CANNOT DO, STATED RATHER THAN
      # SILENTLY BROKEN (P2-1, and rule 5).
      #
      # Python encodes `path` as JSON. Bash compares the slice against the raw
      # `$DEVENV_ROOT`. For a path holding `"`, `\` or a control character the
      # two differ FOREVER: the projection would then run on every shell entry,
      # idempotent and silently expensive. Spaces, `: `, `#` and every non-ASCII
      # character keep working — those are P2-1's real cases and the Python
      # writer handles them. Only these three are out, and the restriction is
      # now a refusal that explains itself instead of a silence.
      #
      # This `case` forks nothing, which is what §5.2 requires of this path.
      #
      # ITS SOURCE TEXT IS ALSO ITS RUNNABLE TEXT, AND THAT IS DELIBERATE. The
      # `flake.nix` check `hook-path-refusal` cuts the block out of THIS FILE
      # between the two sentinels and runs it against a table of paths, so what
      # is tested is the bytes the hook uses rather than a copy of them. An
      # earlier draft matched `*$'\n'*`, which the Nix string layer rewrites, so
      # the extracted text was not what ran; `[[:cntrl:]]` needs no escape at
      # either layer and covers every control character rather than two.
      #
      # devman-hook: path-refusal begin
      devman_badroot=""
      case "$devman_root" in
        *'"'*) devman_badroot='a double quote' ;;
        *'\'*) devman_badroot='a backslash' ;;
        *[[:cntrl:]]*) devman_badroot='a control character' ;;
      esac
      # devman-hook: path-refusal end

      if [ -n "$devman_badroot" ]; then
        echo "devman: refusing to register '${projectName}'" >&2
        echo "devman:   its path holds $devman_badroot:" >&2
        echo "devman:   $devman_root" >&2
        echo "devman:   the shell-entry guard compares that path without forking," >&2
        echo "devman:   and cannot compare it against its own JSON encoding (§5.2)." >&2
        echo "devman:   Every other character works, including spaces, ': ' and" >&2
        echo "devman:   every non-ASCII character." >&2
        echo "devman:   Move this checkout, or rename the directory." >&2

      elif [ -n "$devman_recorded" ] && [ "$devman_recorded" != "$devman_root" ] \
           && [ -d "$devman_recorded" ]; then
        # §9.1: refuse a duplicate, but only when the recorded path still
        # exists. A recorded path that is gone means the project moved, and the
        # entry is replaced — which is what keeps criterion 11 working (C5).
        echo "devman: refusing to register '${projectName}'" >&2
        echo "devman:   already registered at $devman_recorded, which still exists" >&2
        echo "devman:   this repo is        $devman_root" >&2
        echo "devman:   set a different devman.project in one of them" >&2

      else
        # §9.2: the ignore rule goes in `.git/info/exclude`, never `.gitignore`.
        # `.gitignore` may be a read-only store symlink, in which case the
        # append fails on every entry forever; it is tracked, so writing to it
        # dirties the tree the rule exists to keep clean; and `devenv init`
        # writes to it too (C4).
        #
        # `git rev-parse --git-path info/exclude` is the documented way to find
        # it, and it forks. The two shapes it resolves are cheap to read
        # directly: a `.git` directory holds `info/exclude`, and a `.git` FILE
        # is a linked worktree, whose `commondir` points back at the main
        # repository — which is why the literal path fails there. A repo with no
        # `.git` gets no rule, and that is correct: there is nothing to ignore.
        devman_ex=""
        if [ -d "$devman_root/.git" ]; then
          devman_ex="$devman_root/.git/info/exclude"
        elif [ -f "$devman_root/.git" ]; then
          devman_gd=$(<"$devman_root/.git")
          devman_gd="''${devman_gd#gitdir: }"
          devman_gd="''${devman_gd%%$'\n'*}"
          case "$devman_gd" in /*) ;; *) devman_gd="$devman_root/$devman_gd" ;; esac
          if [ -f "$devman_gd/commondir" ]; then
            devman_cd=$(<"$devman_gd/commondir")
            devman_cd="''${devman_cd%%$'\n'*}"
            case "$devman_cd" in
              /*) devman_ex="$devman_cd/info/exclude" ;;
              *) devman_ex="$devman_gd/$devman_cd/info/exclude" ;;
            esac
          else
            devman_ex="$devman_gd/info/exclude"
          fi
        fi

        if [ -n "$devman_ex" ] && [ -d "''${devman_ex%/*}" ]; then
          devman_cur=""
          [ -f "$devman_ex" ] && devman_cur=$(<"$devman_ex")
          if [[ $'\n'"$devman_cur"$'\n' != *$'\n.devman/.runs/\n'* ]]; then
            printf '%s\n' ".devman/.runs/" >> "$devman_ex"
          fi
        fi

        # The guard. `[ -d ]` on the Dagu view as well as the entry, so that
        # deleting the registry and re-entering restores it exactly
        # (criterion 17).
        if [ "$devman_recorded" != "$devman_root" ] \
           || [ "$devman_plan" != "${planFile}" ] \
           || [ "$devman_locals" != "$devman_local" ] \
           || [ ! -d "$devman_reg/dags" ] \
           || [ -n "$devman_relink" ] || [ -n "$devman_stale" ]; then
          ${projectScript} "$devman_root" "$devman_reg" "''${devman_local_args[@]}"
        fi
      fi

      unset devman_root devman_reg devman_meta devman_b devman_f \
            devman_disk devman_local devman_local_args devman_names devman_n \
            devman_relink devman_stale devman_proj devman_body devman_have \
            devman_recorded devman_plan devman_locals devman_badroot \
            devman_trig devman_trig_kept devman_trig_now devman_trig_was \
            devman_ex devman_gd devman_cd devman_cur
    '';
  };
}
