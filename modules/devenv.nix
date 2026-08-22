# The repo interface — a devenv module a project imports through devenv.yaml.
#
# INVESTIGATION B SCRATCH (CONCEPT.md §12.3). The smallest honest half of the
# pair: selection, identity, and one registry entry written at shell entry. It
# is not stage 1. It does not project workflows into Dagu (§9.2), it does not
# resolve groups (§7.3), and it does not detect a stale `.devman/` (§15.2).
#
#   inputs:
#     devman:
#       url: "git+file:///path/to/devman?ref=BRANCH&rev=REV"
#   imports:
#     - devman/modules
#
# The file MUST be named devenv.nix. devenv resolves `<input>/<subdir>` to
# `inputs.<input> + /<subdir>` and then looks for `devenv.nix` inside it; a
# `default.nix` is never consulted (B4).
#
# The module takes `pkgs` from the consuming repo's devenv, which pins
# `devenv-nixpkgs/rolling`. The NixOS module takes `pkgs` from the machine.
# Whether those two can disagree without cost is the whole of Investigation B.
{ pkgs, lib, config, ... }:

let
  inherit (lib) mkEnableOption mkIf mkOption types;

  cfg = config.devman;

  # Registration renders this, then compares it against disk before writing
  # (§5.2). The repo's path is a run-time fact, so it is filled in by the
  # hook rather than by Nix.
  entryTemplate = {
    schema = 1;
    project = cfg.project;
    groups = cfg.groups;
    path = "@PATH@";
  };

  entryFile = (pkgs.formats.json { }).generate "devman-entry.json" entryTemplate;
in
{
  options.devman = {
    enable = mkEnableOption "devman automation plane membership for this repository";

    project = mkOption {
      type = types.str;
      description = "Project identity, never a path (§9.1). Stated, never inferred from the directory name.";
    };

    groups = mkOption {
      type = types.listOf types.str;
      default = [ "base" ];
      example = [ "base" "python" ];
      description = "Workflow groups this repository inherits (§7.3).";
    };

    registryDir = mkOption {
      type = types.str;
      default = "$HOME/.local/share/devman";
      description = "Registry root (§9.2). An option so a test can point it somewhere disposable.";
    };

    installClient = mkOption {
      type = types.bool;
      default = true;
      description = "Put the Dagu client on PATH, so a trigger in this repo can run `dagu enqueue` (E2). Calls the same nix/dagu.nix the NixOS module calls, under this repo's nixpkgs.";
    };
  };

  config = mkIf cfg.enable {
    packages = lib.optional cfg.installClient (pkgs.callPackage ../nix/dagu.nix { });

    # §5.2: registration runs in enterShell, guarded by a content hash. The
    # module renders the entry, compares its hash against disk, and writes only
    # on a difference, so the common case costs nothing.
    enterShell = ''
      devman_registry="${cfg.registryDir}/projects"
      devman_entry="$devman_registry/${cfg.project}.json"
      devman_rendered="$(${lib.getExe pkgs.gnused} "s|@PATH@|$DEVENV_ROOT|" ${entryFile})"

      if [ ! -f "$devman_entry" ] || [ "$(cat "$devman_entry")" != "$devman_rendered" ]; then
        mkdir -p "$devman_registry"
        printf '%s\n' "$devman_rendered" > "$devman_entry"
        echo "devman: registered ${cfg.project}"
      fi
    '';
  };
}
