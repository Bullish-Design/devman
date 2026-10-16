# Dagu 2.20.1, the orchestrator the plane installs (CONCEPT.md §10).
#
# nixpkgs does not package Dagu at any version, so the plane carries its own
# expression. The flake, `devenv.nix` and the Home Manager module all call this
# one file.
#
# This installs the upstream release tarball and does not build from source.
# The web UI is a pnpm/webpack build, and its output is not committed:
# `internal/service/frontend/assets/` holds only a `.gitkeep` at the tag. A
# source build would also need the Go version that the tag declares. The Go
# reason of the 2.15.0 pin is not re-measured for 2.20.1. The UI reason holds.
#
# The pin is a tag either way.
{ lib
, stdenvNoCC
, fetchurl
}:

let
  version = "2.20.1";

  # sha256 sums copied verbatim from the release's own checksums.txt, so a
  # bump is a diff against one upstream file:
  #   curl -sSL https://github.com/dagucloud/dagu/releases/download/v<version>/checksums.txt
  releases = {
    x86_64-linux = {
      platform = "linux_amd64";
      sha256 = "0d5c1612cd842931fe6d4e598fc2e43fb912a94122e571c62a8f73691ea49837";
    };
    aarch64-linux = {
      platform = "linux_arm64";
      sha256 = "eab7377c1b1993f8eb4c272f9383174effdf4caee0bf7e00def7f2e644fe3186";
    };
    x86_64-darwin = {
      platform = "darwin_amd64";
      sha256 = "51d003cb637c80af8f30142abd9e89de916ac56ab65f0740959b2f5530060ba6";
    };
    aarch64-darwin = {
      platform = "darwin_arm64";
      sha256 = "f511a6d45d1a350ef3020695fad2fcea1237b39f4b24eccdc0100362dd230c29";
    };
  };

  inherit (stdenvNoCC.hostPlatform) system;

  release = releases.${system} or (throw "dagu: no release binary for ${system}");
in
stdenvNoCC.mkDerivation {
  pname = "dagu";
  inherit version;

  src = fetchurl {
    url = "https://github.com/dagucloud/dagu/releases/download/v${version}/dagu_${version}_${release.platform}.tar.gz";
    inherit (release) sha256;
  };

  # The tarball holds its files at the top level, with no wrapping directory.
  sourceRoot = ".";

  installPhase = ''
    runHook preInstall
    install -Dm755 dagu $out/bin/dagu
    runHook postInstall
  '';

  # The release binary is statically linked, so it needs no patchelf. The check
  # below runs it, which is what proves that on each version bump.
  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    $out/bin/dagu version
    runHook postInstallCheck
  '';

  meta = {
    description = "Workflow engine that runs DAGs defined in YAML";
    homepage = "https://github.com/dagu-org/dagu";
    license = lib.licenses.gpl3Plus;
    mainProgram = "dagu";
    platforms = lib.attrNames releases;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
}
