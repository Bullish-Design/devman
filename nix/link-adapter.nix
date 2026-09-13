# The independent link adapter (038 Stage 16, B) — `devman-link`.
#
# WHAT THIS DERIVATION IS FOR, AND WHY IT IS SEPARATE.
#
# Before B, the link adapter shipped inside `nix/renderer.nix`. That derivation
# carries Dagu, because the projection validates every file it publishes. A
# repository that wanted its links reconciled therefore took the workflow
# renderer, its Dagu, and the compatibility registry the old command read. None
# of those is needed to make a symlink.
#
# The closure here is python3 and this source. No Dagu, no watchexec, no
# renderer, no `pyyaml`. The component reads the central Nix file through
# `nix-instantiate`, which every caller already has.
#
# THE BUILD IS THE INDEPENDENCE CHECK.
#
# The fileset holds `src/devman_link`, `src/devman_contract` and the adapter's
# own `pyproject.toml`, and nothing else. `src/devman` is absent, so an
# `import devman.registry` inside the component fails the install check below
# rather than reaching a machine. `tests/unit/test_link_adapter.py` says the
# same thing in the fast loop; this is the one that cannot be skipped.
#
# The source is assembled with `runCommand` rather than taken straight from a
# fileset, because hatchling needs `pyproject.toml` at the root of the tree it
# builds and this one lives under `packaging/`.
#
# THE INSTALL CHECK RUNS THE COMMAND, NOT ONLY `--help`.
#
# `--help` proves the entry point resolves and every module imports. It does
# not prove the claim B exists to make. So the check also runs a real `status`
# against a temporary repository and overlay that no registry has heard of, and
# asserts exit 1 with the five-state output. A component that quietly re-grew a
# registry dependency fails here.
{ lib
, python3Packages
, nix
}:

let
  source = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../src/devman_link
      ../src/devman_contract
      ../packaging/devman-link/pyproject.toml
    ];
  };
in
python3Packages.buildPythonApplication {
  pname = "devman-link";
  version = "0.6.0";
  pyproject = true;

  src = builtins.path {
    name = "devman-link-source";
    path = source;
  };

  postPatch = ''
    cp packaging/devman-link/pyproject.toml ./pyproject.toml
    rm -rf packaging
  '';

  build-system = [ python3Packages.hatchling ];
  dependencies = [ ];

  doInstallCheck = true;
  nativeInstallCheckInputs = [ nix ];
  installCheckPhase = ''
    runHook preInstallCheck

    $out/bin/devman-link --help > /dev/null
    $out/bin/devman-link status --help > /dev/null

    # THE NO-REGISTRY FIXTURE. A repository the compatibility registry has
    # never heard of, with its identity in the manifest and its links in the
    # central Nix file — which is exactly the shape that refused before Stage
    # 15, and exactly what B has to keep working without a registry.
    export HOME=$TMPDIR
    fixture=$TMPDIR/fixture
    mkdir -p "$fixture/repo/.devman" "$fixture/overlay/projects/fixture-demo"

    cat > "$fixture/repo/.devman/project.toml" <<'MANIFEST'
    schema = 1
    project = "fixture-demo"
    groups = ["base"]
    policy = "stable"
    MANIFEST

    cat > "$fixture/overlay/projects/fixture-demo/devenv.local.nix" <<'CENTRAL'
    { config, ... }:

    {
      devman.link = {
        ".envrc" = { canonical = "central"; path = "common/envrc"; };
        ".agents" = {
          canonical = "central";
          path = "projects/''${config.devman.project}/agents";
        };
      };
    }
    CENTRAL

    set +e
    out=$($out/bin/devman-link status \
      --root "$fixture/repo" \
      --overlay "$fixture/overlay" 2>&1)
    code=$?
    set -e

    echo "$out"
    # Exit 1 is the drift answer: nothing is linked yet. Exit 2 would mean the
    # component could not run at all, which is the failure this check is for.
    [ "$code" = 1 ] || { echo "expected exit 1, got $code" >&2; exit 1; }
    case "$out" in
      *"central config $fixture/overlay/projects/fixture-demo/devenv.local.nix"*) ;;
      *) echo "status did not report the central configuration path" >&2; exit 1 ;;
    esac
    case "$out" in
      *"fixture-demo:.agents"*) ;;
      *) echo "status did not resolve the project-expanded declaration" >&2; exit 1 ;;
    esac

    runHook postInstallCheck
  '';

  meta = {
    description = "The devman link adapter, independent of the workflow plane";
    homepage = "https://github.com/Bullish-Design/devman";
    mainProgram = "devman-link";
  };
}
