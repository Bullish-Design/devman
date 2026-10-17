# The devman CLI, built with uv2nix from `pyproject.toml` and `uv.lock`.
# It installs the Python package, its required base template, and `dagu/`
# (config template and checkout guard).
#
# The Python interpreter comes from nixpkgs (python313). The dependencies come
# from `uv.lock`, as wheels. A stale lock fails `uv lock --check` in `base:check`.
{ lib
, stdenvNoCC
, callPackage
, python313
, makeWrapper
, bash
, dagu
, watchexec
, uv2nix
, pyproject-nix
, pyproject-build-systems
}:

let
  # Only the files uv2nix and the build read. `.scratch/` and `.git` stay out
  # of the closure.
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../uv.lock
      ../src
      ../dagu
    ];
  };

  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = src; };

  pythonSet =
    (callPackage pyproject-nix.build.packages { python = python313; }).overrideScope
      (lib.composeManyExtensions [
        pyproject-build-systems.overlays.default
        (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
      ]);

  # Runtime dependencies only (no dependency groups).
  venv = pythonSet.mkVirtualEnv "devman-env" workspace.deps.default;

  # Runtime dependencies plus the dev group, for `checks.python-tests`.
  testEnv = pythonSet.mkVirtualEnv "devman-test-env" workspace.deps.all;
in
(stdenvNoCC.mkDerivation {
  pname = "devman";
  version = (fromTOML (builtins.readFile ../pyproject.toml)).project.version;
  inherit src;

  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin $out/share/devman
    cp -r dagu $out/share/devman/
    # The guard is a template: its @bash@ token becomes this store path.
    substituteInPlace $out/share/devman/dagu/guard.sh --replace-fail @bash@ ${bash}/bin/bash
    makeWrapper ${venv}/bin/devman $out/bin/devman \
      --prefix PATH : ${lib.makeBinPath [ dagu watchexec ]}
    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    $out/bin/devman --version | grep -F "devman 0.9.1"
    ${venv}/bin/python -c 'from importlib.resources import files; assert files("devman").joinpath("base.yaml").is_file()'

    # The installed guard passes a checkout with a marker and fails one without.
    guard=$out/share/devman/dagu/guard.sh
    ! grep -F @bash@ $guard
    mkdir -p $TMPDIR/ok/.git $TMPDIR/gone
    DEVMAN_PROJECT_DIR=$TMPDIR/ok $guard -c true
    ! DEVMAN_PROJECT_DIR=$TMPDIR/gone $guard -c true 2> $TMPDIR/err
    grep -F "no .git, no .jj" $TMPDIR/err
  '';

  meta.mainProgram = "devman";
}).overrideAttrs (old: {
  passthru = (old.passthru or { }) // { inherit testEnv pythonSet; };
})
