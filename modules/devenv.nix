# The repo interface — a devenv module a project imports through devenv.yaml.
#
# STAGE 1 (CONCEPT.md §13). Nix declares selection and identity; YAML declares
# workflows (§7.4). Three keys and the repo's own primitives:
#
#   devman = {
#     enable  = true;
#     project = "pyjutsu";
#     groups  = [ "base" "python" ];
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
# `git+https` records `rev` and `narHash` in devenv.lock. `git+file` records
# neither and silently follows the branch head, so a local checkout is never
# pinned (B4). Use a fixed `path:` copy for local iteration.
#
# The module takes `pkgs` from the consuming repo's devenv, which pins
# `devenv-nixpkgs/rolling`. The NixOS module takes `pkgs` from the machine.
# Neither reads the plane's own `nixpkgs` input (§3.1, B1).
{ pkgs, lib, config, ... }:

let
  inherit (lib) mkEnableOption mkIf mkOption types;

  cfg = config.devman;

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
    # A group may ship no workflows at all. A triggers-only group is how a
    # repository opts into reactivity without also inheriting somebody's
    # workflows, which is what keeps §7.4's "an inherited workflow you never
    # trigger costs nothing" true — a *triggered* workflow costs plenty (§8).
      { }
    else
      lib.mapAttrs'
        (file: _: lib.nameValuePair
          (lib.removeSuffix ".yaml" file)
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
  #   <registry>/dags/<project>-<workflow>.yaml               -> the line above
  #
  # `dags/` is Dagu's flat view of `projects/`. A DAG is keyed by its file's
  # base name, so two projects both projecting `check.yaml` are reported as a
  # duplicate and both vanish from `dagu ls`, from the web UI and from the
  # scheduler. `<project>-<workflow>` is the machine-unique name. See
  # nix/nixos-module.nix, which points `dags_dir` at it.
  #
  # This script forks. It runs only when the rendered entry differs from the one
  # on disk, which the guard in `enterShell` decides without forking at all.
  linkLines = lib.concatStringsSep "\n  "
    (lib.mapAttrsToList
      (name: w: "devman_link ${lib.escapeShellArg name} ${w.file}")
      resolved);

  projectScript = pkgs.writeShellScript "devman-project-${cfg.project}" ''
    set -eu
    root="$1"
    reg="$2"
    rendered="$3"
    proj=${lib.escapeShellArg cfg.project}

    pdir="$reg/projects/$proj"
    dags="$reg/dags"
    mkdir -p "$pdir/workflows" "$dags"

    # §9.2's run-state layout, repo-side. Dagu creates `log_dir` itself before
    # the first step runs, so `logs/` would appear anyway; `artifacts/` and
    # `reports/` have no other owner, and a step that writes a report should not
    # have to create the tree first.
    #
    # A step addresses them through the two names §7.1 already makes global —
    # `$DEVMAN_PROJECT_DIR` and the `.devman/.runs/` path shape — so this adds
    # no fourth name to a closed list and no absolute path to any workflow
    # (criterion 10):
    #
    #     run: mytool --out "$DEVMAN_PROJECT_DIR/.devman/.runs/artifacts/x.json"
    #
    # The whole tree is git-ignored: registration writes `.devman/.runs/` to
    # `.git/info/exclude` below, and `.devman/` itself holds nothing else here,
    # so an adopted repository's tree stays clean.
    mkdir -p "$root/.devman/.runs/logs" "$root/.devman/.runs/artifacts" \
             "$root/.devman/.runs/reports"

    # The registry is derived (§9.3), so the projection is rebuilt rather than
    # patched. A `dags/` link is removed only when it still points at this
    # project's own file: `<project>-<workflow>` is ambiguous when one project
    # name is a prefix of another, and the link target is not.
    for old in "$pdir"/workflows/*.yaml; do
      [ -L "$old" ] || [ -e "$old" ] || continue
      stem=''${old##*/}; stem=''${stem%.yaml}
      link="$dags/$proj-$stem.yaml"
      if [ -L "$link" ] && [ "$(readlink "$link")" = "../projects/$proj/workflows/$stem.yaml" ]; then
        rm -f "$link"
      fi
      rm -f "$old"
    done

    devman_link() {
      ln -sfn "$2" "$pdir/workflows/$1.yaml"
      ln -sfn "../projects/$proj/workflows/$1.yaml" "$dags/$proj-$1.yaml"
    }

    ${linkLines}

    # §7.3's last layer. It shadows every group, and it is a symlink, so
    # editing the file changes what Dagu reads without any re-projection.
    for f in "$root"/.devman/workflows/*.yaml; do
      [ -e "$f" ] || continue
      stem=''${f##*/}; stem=''${stem%.yaml}
      devman_link "$stem" "$f"
    done

    # Last, so that a projection interrupted half way leaves an entry that does
    # not match and is therefore retried on the next shell entry.
    printf '%s\n' "$rendered" > "$pdir/metadata.json"
  '';

  # ---------------------------------------------------------------------------
  # The entry the guard compares (§5.2)
  #
  # Two placeholders, both filled by bash parameter expansion rather than by a
  # fork. `@PATH@` is where this checkout sits. `@LOCAL@` is the set of names in
  # `.devman/workflows/`, which is what makes the guard notice a repo adding or
  # removing an override. It does not need to notice an *edit*: the projection
  # is a symlink, so an edited file is already what Dagu reads.
  #
  # `plan` is the projection script's store path. It changes when the groups
  # change, when a group file changes, and when the plane's revision changes,
  # which is exactly when the projection must be rebuilt.
  #
  # ---------------------------------------------------------------------------
  # SCHEMA 2 adds `workflows`, and it exists for `doctor` (§10) rather than for
  # the projection, which never reads it. Schema 1 recorded the inputs to §7.3's
  # resolution — `groups` and `local` — and not its outcome, so nothing on disk
  # said which file won or what it displaced. Four of §10's six checks want the
  # outcome, and check 4 — "shadowed files and their drift" — cannot be computed
  # from schema 1 at all: to diff a repo's `.devman/workflows/check.yaml`
  # against the group version it shadows, something must record which group
  # version that was. §12.4's measurement asks the same question.
  #
  #   "workflows": {
  #     "check": {"group":"python","shadows":["base"],"source":"/nix/store/..."}
  #   }
  #
  # `local` stays, and the two are read together: a name in `local` is the
  # winner, and `workflows.<name>.source` is then what it shadows. Nix knows the
  # group half at evaluation time; which files are in a working tree is a
  # run-time fact, which is why `local` is still filled by the hook.
  # SCHEMA 3 adds `triggers`, for the same reason schema 2 added `workflows`:
  # the watcher and `doctor` need the OUTCOME of a resolution that only Nix can
  # perform. It is `null` for a repository that takes no group declaring any,
  # which is every repository until one opts in.
  entryTemplate = pkgs.writeText "devman-metadata-${cfg.project}.json" ''
    {
      "schema": 3,
      "project": ${builtins.toJSON cfg.project},
      "path": "@PATH@",
      "groups": ${builtins.toJSON cfg.groups},
      "plan": "${projectScript}",
      "local": [@LOCAL@],
      "workflows": ${builtins.toJSON (lib.mapAttrs
        (_: w: { inherit (w) group shadows; source = "${w.file}"; })
        resolved)},
      "triggers": ${builtins.toJSON triggers}
    }
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
      '';
    };

    groups = mkOption {
      type = types.listOf types.str;
      default = [ "base" ];
      example = [ "base" "python" ];
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
      devman_meta="$devman_reg/projects/${cfg.project}/metadata.json"

      # §15.2: `.devman/` may hold only `workflows/` and `.runs/`. A survey of
      # 77 checkouts found four shapes, so the test is a whitelist rather than a
      # check for a known-old marker (D6). One directory listing, no fork.
      devman_bad=""
      for devman_f in "$devman_root"/.devman/* "$devman_root"/.devman/.*; do
        [ -e "$devman_f" ] || continue
        devman_b="''${devman_f##*/}"
        case "$devman_b" in
          . | .. | workflows | .runs) ;;
          *) devman_bad="$devman_bad $devman_b" ;;
        esac
      done

      devman_disk=""
      [ -f "$devman_meta" ] && devman_disk=$(<"$devman_meta")

      devman_local=""
      devman_names="${lib.concatStringsSep " " (lib.attrNames resolved)}"
      for devman_f in "$devman_root"/.devman/workflows/*.yaml; do
        [ -e "$devman_f" ] || continue
        devman_b="''${devman_f##*/}"
        devman_local="$devman_local, \"''${devman_b%.yaml}\""
        devman_names="$devman_names ''${devman_b%.yaml}"
      done
      devman_local="''${devman_local#, }"

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
      devman_relink=""
      for devman_n in $devman_names; do
        [ -L "$devman_reg/dags/${cfg.project}-$devman_n.yaml" ] || devman_relink=1
      done

      devman_tmpl=$(<${entryTemplate})
      devman_rendered="''${devman_tmpl//@PATH@/$devman_root}"
      devman_rendered="''${devman_rendered/@LOCAL@/$devman_local}"

      # The recorded path, sliced out of the entry we wrote ourselves. One
      # `[ -d ]` on it is the whole of §9.1's test, and it forks nothing.
      devman_recorded=""
      case "$devman_disk" in
        *'"path": "'*)
          devman_recorded="''${devman_disk#*'"path": "'}"
          devman_recorded="''${devman_recorded%%'"'*}"
          ;;
      esac

      if [ -n "$devman_bad" ]; then
        echo "devman: refusing to register '${cfg.project}'" >&2
        echo "devman:   .devman/ holds entries devman does not recognise:$devman_bad" >&2
        echo "devman:   only workflows/ and .runs/ may be there" >&2
        echo "devman:   move them, or unset devman.enable in this repository" >&2

      elif [ -n "$devman_recorded" ] && [ "$devman_recorded" != "$devman_root" ] \
           && [ -d "$devman_recorded" ]; then
        # §9.1: refuse a duplicate, but only when the recorded path still
        # exists. A recorded path that is gone means the project moved, and the
        # entry is replaced — which is what keeps criterion 11 working (C5).
        echo "devman: refusing to register '${cfg.project}'" >&2
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
        if [ "$devman_disk" != "$devman_rendered" ] || [ ! -d "$devman_reg/dags" ] \
           || [ -n "$devman_relink" ]; then
          ${projectScript} "$devman_root" "$devman_reg" "$devman_rendered"
        fi
      fi

      unset devman_root devman_reg devman_meta devman_bad devman_b devman_f \
            devman_disk devman_local devman_names devman_n devman_relink \
            devman_tmpl devman_rendered \
            devman_recorded devman_ex devman_gd devman_cd devman_cur
    '';
  };
}
