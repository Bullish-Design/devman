# The devman CLI. It installs the mechanism only: the Python package and
# `dagu/` (config template, checkout guard). The library is overlay content
# (PLAN.md, decision Q7), so this package ships none.
{ lib
, python313Packages
, makeWrapper
, dagu
, watchexec
}:

python313Packages.buildPythonApplication {
  pname = "devman";
  version = "0.9.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../src
      ../dagu
    ];
  };

  build-system = [ python313Packages.hatchling ];
  dependencies = [ python313Packages.pyyaml ];
  nativeBuildInputs = [ makeWrapper ];

  postInstall = ''
    mkdir -p $out/share/devman
    cp -r dagu $out/share/devman/
  '';

  postFixup = ''
    wrapProgram $out/bin/devman \
      --prefix PATH : ${lib.makeBinPath [ dagu watchexec ]}
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    $out/bin/devman --version | grep -F "devman 0.9.0"
  '';

  meta.mainProgram = "devman";
}
