# Dagu — the orchestrator the automation plane installs (CONCEPT.md §4).
#
# nixpkgs does not package Dagu at any version, so the plane must carry its own
# expression. One file, two consumers: `devenv.nix` calls it under the repo's
# nixpkgs, and the NixOS module will call it under the machine's. That is the
# §3.1 anti-drift rule applied to the one package both interfaces need.
#
# This installs the upstream release tarball rather than building from source.
# Two things block a source build today:
#
#   * v2.15.0 declares `go 1.27.0`; nixpkgs ships 1.26.4.
#   * The web UI is a pnpm/webpack build, and its output is not committed —
#     `internal/service/frontend/assets/` holds only a `.gitkeep` at the tag.
#
# Revisit when nixpkgs has Go 1.27. The pin is a tag either way.
{ lib
, stdenvNoCC
, fetchurl
}:

let
  version = "2.15.0";

  # sha256 sums copied verbatim from the release's own checksums.txt, so a
  # bump is a diff against one upstream file:
  #   curl -sSL https://github.com/dagucloud/dagu/releases/download/v<version>/checksums.txt
  releases = {
    x86_64-linux = {
      platform = "linux_amd64";
      sha256 = "7789fd5bf53101ff6442faf602ae404f3e64f438e982c86c57653277d93d1ad2";
    };
    aarch64-linux = {
      platform = "linux_arm64";
      sha256 = "a9426a580dbdaf4385d4528b717a83092d901e871ca455e9bf23a2a449b12fff";
    };
    x86_64-darwin = {
      platform = "darwin_amd64";
      sha256 = "9420fd6102ffde74158775ef5c0577ae358e4bfe6e08868d04acdaa51049afd5";
    };
    aarch64-darwin = {
      platform = "darwin_arm64";
      sha256 = "bebf2bb0e9f8342790edb61a67c1a37de6508d290f2b8f784609fd765aa2ff6b";
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
