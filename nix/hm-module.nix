# The Home Manager module (CONCEPT.md §10). It installs the devman CLI, Dagu,
# the Dagu user service and the watcher user service. It generates
# `config.yaml` only. `base.yaml` is overlay content (R13): `devman compile`
# fills its tokens and writes `<stateDir>/base.yaml`.
#
# Linger is not here. Home Manager cannot set it; the machine layer does.
{ self }:
{ config, lib, pkgs, ... }:

let
  cfg = config.services.devman;
  inherit (lib) mkEnableOption mkOption mkIf types;

  home = config.home.homeDirectory;

  isLoopback = host:
    builtins.match "127\\.[0-9]+\\.[0-9]+\\.[0-9]+|::1|localhost" host != null;

  # True when path `a` is `b` or sits inside `b`.
  inside = a: b: a == b || lib.hasPrefix (b + "/") a;

  queueList = lib.mapAttrsToList
    (name: max_concurrency: { inherit name max_concurrency; })
    cfg.queues;

  bash = "${pkgs.bash}/bin/bash";

  # Dagu reads this file at start. It has no @token@ left after the fill.
  configFile = pkgs.replaceVars ../dagu/config.yaml {
    host = cfg.host;
    port = toString cfg.port;
    coordinatorPort = toString cfg.coordinatorPort;
    inherit bash;
    stateDir = cfg.stateDir;
    baseConfig = "${cfg.stateDir}/base.yaml";
    queues = builtins.toJSON queueList;
  };

  # The CLI with the machine facts that `compile`, `watch` and `doctor` read.
  # `guard.sh` arrives in Stage 7, inside the package under share/devman/dagu.
  wrappedDevman = pkgs.symlinkJoin {
    name = "devman-wrapped-${cfg.package.version}";
    paths = [ cfg.package ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram $out/bin/devman \
        --set DEVMAN_OVERLAY ${lib.escapeShellArg cfg.overlayDir} \
        --set DEVMAN_STATE ${lib.escapeShellArg cfg.stateDir} \
        --set DAGU_HOME ${lib.escapeShellArg cfg.daguHome} \
        --set DEVMAN_DAGU_CONFIG ${configFile} \
        --set DEVMAN_DAGU_VERSION ${cfg.dagu.package.version} \
        --set DEVMAN_BASH ${bash} \
        --set DEVMAN_GUARD ${cfg.package}/share/devman/dagu/guard.sh \
        --set DEVMAN_BIN $out/bin/devman
    '';
  };

  servicePath = lib.concatStringsSep ":"
    ((map (root: "${root}/bin") cfg.servicePath) ++ [ "${wrappedDevman}/bin" "${cfg.dagu.package}/bin" ]);
in
{
  options.services.devman = {
    enable = mkEnableOption "devman, the Dagu workflow plane";

    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.devman;
      defaultText = lib.literalMD "this flake's `devman` package";
      description = "The devman CLI package.";
    };

    dagu.package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.dagu;
      defaultText = lib.literalMD "this flake's `dagu` package";
      description = "The Dagu package.";
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = ''
        Dagu bind address. It must be loopback, because `auth.mode` is `none`.
      '';
    };

    port = mkOption {
      type = types.port;
      default = 8080;
      description = "Dagu HTTP port.";
    };

    coordinatorPort = mkOption {
      type = types.port;
      default = 50055;
      description = "Dagu coordinator port.";
    };

    queues = mkOption {
      type = types.attrsOf types.ints.positive;
      default = {
        light = 4;
        normal = 2;
        heavy = 1;
        gpu = 1;
        exclusive = 1;
        llm = 2;
      };
      description = "Queue names and their max concurrency.";
    };

    defaultQueue = mkOption {
      type = types.str;
      default = "light";
      description = "The queue that library/base.yaml names. Must be a key of `queues`.";
    };

    overlayDir = mkOption {
      type = types.str;
      default = "${home}/.config/devman";
      defaultText = lib.literalExpression ''"''${config.home.homeDirectory}/.config/devman"'';
      description = "Central overlay: projects, library and local content.";
    };

    stateDir = mkOption {
      type = types.str;
      default = "${home}/.local/state/devman";
      defaultText = lib.literalExpression ''"''${config.home.homeDirectory}/.local/state/devman"'';
      description = "Compiled output, run logs, events and watcher state.";
    };

    daguHome = mkOption {
      type = types.str;
      default = "${home}/.local/share/dagu";
      defaultText = lib.literalExpression ''"''${config.home.homeDirectory}/.local/share/dagu"'';
      description = "DAGU_HOME for the Dagu service and the wrapped CLI.";
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
        Profile roots for the PATH of both services, as systemd specifiers.
        The module appends `/bin` to each root.
      '';
    };

    watch = {
      enable = mkOption {
        type = types.bool;
        default = true;
        description = "Run the watcher user service.";
      };

      debounce = mkOption {
        type = types.str;
        default = "300ms";
        description = "Watcher debounce interval.";
      };
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.queues ? ${cfg.defaultQueue};
        message = "services.devman.defaultQueue \"${cfg.defaultQueue}\" is not a key of services.devman.queues.";
      }
      {
        assertion = isLoopback cfg.host;
        message = "services.devman.host \"${cfg.host}\" is not loopback. Dagu runs with auth.mode none, so a non-loopback host exposes an unauthenticated command runner.";
      }
      {
        assertion = !(inside cfg.overlayDir cfg.stateDir || inside cfg.stateDir cfg.overlayDir);
        message = "services.devman.overlayDir and services.devman.stateDir must differ, and neither may contain the other.";
      }
    ];

    home.packages = [ wrappedDevman cfg.dagu.package ];

    systemd.user.services.devman-dagu = {
      Unit = {
        Description = "devman: Dagu server and scheduler";
        X-Restart-Triggers = [ "${configFile}" ];
      };
      Service = {
        ExecStart = "${cfg.dagu.package}/bin/dagu start-all --config ${configFile}";
        Environment = [
          "DAGU_HOME=${cfg.daguHome}"
          "PATH=${servicePath}"
        ];
        UnsetEnvironment = [ "SHELL" ];
        Restart = "on-failure";
      };
      Install.WantedBy = [ "default.target" ];
    };

    systemd.user.services.devman-watch = mkIf cfg.watch.enable {
      Unit = {
        Description = "devman: watcher";
        After = [ "devman-dagu.service" ];
        X-Restart-Triggers = [ "${wrappedDevman}" ];
      };
      Service = {
        ExecStart = "${wrappedDevman}/bin/devman watch --debounce ${cfg.watch.debounce}";
        Environment = [ "PATH=${servicePath}" ];
        Restart = "on-failure";
      };
      Install.WantedBy = [ "default.target" ];
    };
  };
}
