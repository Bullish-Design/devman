# The machine-owned link interface.
#
# This module has one job: expose the central `devman.link` declaration and
# reconcile it when a devenv shell starts. It does not know about workflows,
# the registry, Dagu, or project generation state. The machine installs the
# adapter at the stable path below, so a consuming repository does not build
# or pin a second copy of the link component.
{ config, lib, ... }:

let
  inherit (lib) mkOption types;

  # Older adopters still import modules/devenv.nix and therefore expose
  # devman.project. New adopters expose only this module; their identity is the
  # repository manifest. The fallback keeps the migration reversible without
  # making the compatibility option part of the new interface.
  projectName =
    if config.devman ? project then
      config.devman.project
    else
      let
        manifestPath = "${config.devenv.root}/.devman/project.toml";
        manifest =
          if builtins.pathExists manifestPath then
            builtins.fromTOML (builtins.readFile manifestPath)
          else
            throw ("devman-link: project manifest is missing at "
              + manifestPath + ". Create .devman/project.toml.");
      in
        if manifest ? project && builtins.isString manifest.project then
          manifest.project
        else
          throw ("devman-link: project manifest " + manifestPath
            + " must define a string project field.");

  identityGrammar = "[A-Za-z0-9][A-Za-z0-9._-]*";

  # Keep this fallback only for adopters that still set the old option. The
  # link-only interface has no overlay option: the machine contract is the
  # user's central configuration checkout.
  overlayDir =
    if config.devman ? overlayDir then
      config.devman.overlayDir
    else
      "$HOME/.config/devman";

in
{
  options.devman.link = mkOption {
    type = types.attrsOf (types.submodule {
      options = {
        canonical = mkOption {
          type = types.enum [ "central" "repo" "external" ];
          default = "central";
        };
        path = mkOption {
          type = types.str;
          default = "";
        };
        template = mkOption {
          type = types.nullOr types.str;
          default = null;
        };
      };
    });
    default = { };
    description = "Filesystem links reconciled at shell entry (§5).";
  };

  config = {
    assertions = [
      {
        assertion = builtins.match identityGrammar projectName != null;
        message = "devman-link: project identity must start with a letter or digit and contain only letters, digits, '.', '-' or '_'.";
      }
    ];

    # The adapter is a machine component. The package that provides this
    # module also installs this absolute command path in the system profile.
    enterShell = ''
      /run/current-system/sw/bin/devman-link reconcile \
        --root "$DEVENV_ROOT" \
        --overlay "${overlayDir}" \
        --project "${projectName}"
    '';
  };
}
