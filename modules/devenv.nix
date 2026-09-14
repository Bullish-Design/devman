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

  # The canonical machine-plane resolver reads these sources at shell entry.
  # Nix keeps only a content identity for the selected policy and the workflow
  # names needed by the forkless repair guard below. It does not select winners,
  # merge triggers, or merge writes.
  policyRoot = ../.;
  groupsRoot = ../groups;

  groupPolicy = group:
    let
      dir = groupsRoot + "/${group}";
      workflowsDir = dir + "/workflows";
      workflowFiles =
        if builtins.pathExists workflowsDir then
          lib.filterAttrs
            (file: kind: kind == "regular" && lib.hasSuffix ".yaml" file)
            (builtins.readDir workflowsDir)
        else
          { };
    in
    if !builtins.pathExists dir then
      throw "devman: group '${group}' does not exist. There is no ${toString dir}."
    else {
      inherit group;
      workflows = lib.mapAttrs
        (file: _: builtins.readFile (workflowsDir + "/${file}"))
        workflowFiles;
      triggers =
        if builtins.pathExists (dir + "/triggers.toml") then
          builtins.readFile (dir + "/triggers.toml")
        else
          null;
      writes =
        if builtins.pathExists (dir + "/writes.toml") then
          builtins.readFile (dir + "/writes.toml")
        else
          null;
    };

  groupPolicies = map groupPolicy cfg.groups;
  policyDigest = builtins.hashString "sha256" (builtins.toJSON {
    groups = cfg.groups;
    sources = groupPolicies;
  });
  workflowNames = lib.sort builtins.lessThan (lib.unique (lib.concatLists
    (map
      (policy: map (lib.removeSuffix ".yaml") (lib.attrNames policy.workflows))
      groupPolicies)));

  rendererSource = lib.concatMapStrings
    (package:
      lib.concatMapStrings
        (file: builtins.readFile (../src + "/${package}/${file}"))
        (builtins.attrNames
          (lib.filterAttrs
            (file: kind: kind == "regular" && lib.hasSuffix ".py" file)
            (builtins.readDir (../src + "/${package}")))))
    [ "devman" "devman_contract" ];

  renderer = (pkgs.callPackage ../nix/renderer.nix {
    dagu = pkgs.callPackage ../nix/dagu.nix { };
  }).overrideAttrs (_: {
    devmanSourceHash = builtins.hashString "sha256" rendererSource;
  });

  # This path is an identity for the selected policy and renderer. The
  # compatibility publisher records it in metadata so the guard re-runs when
  # either changes.
  planFile = pkgs.writeText "devman-plan-${projectName}.json" (builtins.toJSON {
    schema = 5;
    project = projectName;
    groups = cfg.groups;
    policy = policyDigest;
    renderer = "${renderer}";
  });

  projectScript = pkgs.writeShellScript "devman-project-${projectName}" ''
    exec ${renderer}/bin/devman \
      --registry "$2" \
      --state "$3" \
      project apply \
      --plan ${planFile} \
      --policy-root ${policyRoot} \
      --overlay-root "${cfg.overlayDir}" \
      --root "$1"
  '';

  # The link module owns the bootstrap link and all link declarations. Workflow
  # projection no longer copies those declarations into a second plan.


in
{
  imports = [ ./link.nix ];

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
      description = "Workflow groups this repository inherits, in precedence order (§7.3). `[ ]` is legal: the repository then has only its central per-project `.devman/workflows/` overlay.";
    };

    registryDir = mkOption {
      type = types.str;
      default = "$HOME/.local/share/devman";
      description = ''
        The registry root (§9.2) — `dags/` and the `workflows/` projection.
        `$HOME` is expanded by the shell hook, not by Nix. It must match
        `services.devman-dagu.registryDir` on the machine.

        **Not moved to `~/.config/devman` yet, though `overlayDir` already
        defaults there** (§11 Stage 3's charter said it should). `reconcile.py`
        reads a local workflow override's authored source from
        `overlay/projects/<p>/workflows/<name>.yaml`, the same relative path
        the compatibility publisher writes as a rendered projection under
        `registry/projects/<p>/workflows/`. Moving this option would make the
        two the same file
        until §6.2a's render-to-link change lands, and every shell entry would
        overwrite a tracked, hand-authored workflow with its own generated
        output. §6.2a is deferred: it needs a design for how a scheduled
        (cron-fired) run still gets its project directory without a
        per-project rendered file (see CONCEPT.md §11 Stage 4).
      '';
    };

    stateDir = mkOption {
      type = types.str;
      default = "$HOME/.local/state/devman";
      description = "The state root (§11 Stage 3) — `metadata.json` and the kept copies of `.devman/triggers.toml` and `.devman/writes.toml`, regenerated on every shell entry. `$HOME` is expanded by the shell hook, not by Nix. It must match `services.devman-dagu.stateDir` on the machine.";
    };

    overlayDir = mkOption {
      type = types.str;
      default = "$HOME/.config/devman";
      description = "The config repository root. `$HOME` is expanded by the shell hook, not by Nix.";
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
      devman_state="${cfg.stateDir}"
      devman_meta="$devman_state/projects/${projectName}/metadata.json"

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
      devman_names="${lib.concatStringsSep " " workflowNames}"
      devman_stale=""
      for devman_f in "$devman_root"/.devman/workflows/*.yaml; do
        [ -e "$devman_f" ] || continue
        devman_b="''${devman_f##*/}"
        devman_local="$devman_local, \"''${devman_b%.yaml}\""
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
      devman_trig_kept="$devman_state/projects/${projectName}/triggers.toml"
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

      # AND THE SAME FOR `.devman/writes.toml`, THE LOCAL OUTPUT-OWNERSHIP LAYER
      # (015). It is read at run time by the renderer for the same reason the
      # trigger layer is, so `plan` equality cannot cover it either.
      #
      # 015 shipped the layer WITHOUT this block, and the failure is the exact
      # shape S-5a exists to prevent: the renderer read the file correctly and
      # the guard never asked it to, so editing `writes.toml` changed the
      # registry entry not at all. It was caught end-to-end rather than by a
      # unit test, because both halves were individually right.
      devman_wr="$devman_root/.devman/writes.toml"
      devman_wr_kept="$devman_state/projects/${projectName}/writes.toml"
      if [ -f "$devman_wr" ]; then
        if [ ! -f "$devman_wr_kept" ]; then
          devman_stale=1
        else
          devman_wr_now=$(<"$devman_wr")
          devman_wr_was=$(<"$devman_wr_kept")
          [ "$devman_wr_now" = "$devman_wr_was" ] || devman_stale=1
        fi
      elif [ -f "$devman_wr_kept" ]; then
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
      #     disk "plan"   == ${planFile}      selected policy and renderer unchanged
      #     disk "local"  == $devman_local    the override set has not changed
      #
      # `plan` covers the selected policy sources and renderer. The two
      # run-time facts are the other two. The canonical resolver reads the
      # sources again at publication time, so Nix never selects a workflow.
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
        # The guard. `[ -d ]` on the Dagu view as well as the entry, so that
        # deleting the registry and re-entering restores it exactly
        # (criterion 17).
        if [ "$devman_recorded" != "$devman_root" ] \
           || [ "$devman_plan" != "${planFile}" ] \
           || [ "$devman_locals" != "$devman_local" ] \
           || [ ! -d "$devman_reg/dags" ] \
           || [ -n "$devman_relink" ] || [ -n "$devman_stale" ]; then
          ${projectScript} "$devman_root" "$devman_reg" "$devman_state"
        fi
      fi

      unset devman_root devman_reg devman_state devman_meta devman_b devman_f \
            devman_disk devman_local devman_names devman_n \
            devman_relink devman_stale devman_proj devman_body devman_have \
            devman_recorded devman_plan devman_locals devman_badroot \
            devman_trig devman_trig_kept devman_trig_now devman_trig_was \
            devman_wr devman_wr_kept devman_wr_now devman_wr_was
    '';
  };
}
