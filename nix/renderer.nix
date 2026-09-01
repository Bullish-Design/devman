# The projection renderer (CONCEPT.md §9.2) — `devman-project apply`.
#
# WHY THIS EXISTS AS A SECOND DERIVATION, AND WHAT IT AMENDS.
#
# §3.1's second rule says what the two interfaces share must be TEXT, and a
# Python program is not text. `nix/dagu.nix` was the single measured exception,
# and this is the second — with the same cost, two store paths holding one
# identical program, and a reason §3.1's own text did not anticipate.
#
# THE DECIDING ARGUMENT IS THE GUARD, NOT THE CHARTER.
#
# The alternative was for the devenv module to call `devman` from PATH, which
# works: a devenv shell inherits the machine profile's PATH (nix/devman-cli.nix).
# It fails for one reason. A PATH lookup is a RUN-TIME fact, so the devenv module
# cannot know the renderer's identity at evaluation time, so it cannot put it
# into `planFile`, so the shell-entry guard cannot observe it. Upgrade the
# machine's `devman` and the rendering rules change while every repository keeps
# a projection produced by the old renderer: the entry still matches, nothing
# re-projects, and Dagu keeps reading stale bytes. That is `STAGE_7_LOG.md` S-5a
# exactly — the projection stopped being what the source implies, silently, a
# whole stage before anything noticed.
#
# It also invents a version-skew axis the plane does not have. The devenv module
# comes from the repository's pinned rev; the CLI comes from the machine's.
# Today they share only `metadata.json` — a text schema with a version number
# and soft degradation. Moving rendering SEMANTICS across that boundary turns a
# soft-degrading schema into a hard shell-entry dependency between two
# independently-pinned components.
#
# Built here, the renderer is a store path known at evaluation time. It goes
# into `planFile`, `plan` equality covers it, and a renderer change re-projects
# every repository at its next shell entry.
#
# §3.1's second rule exists to stop silent drift between the two interfaces.
# Sharing the renderer as a machine-side binary CREATES that drift, in the one
# form the guard cannot see. Building it under each consumer's nixpkgs makes the
# renderer's identity observable to the guard. The exception applies §3.1's own
# reasoning to a case its text did not anticipate.
#
# COST CONTROL.
#
#   * the SAME source tree as `nix/devman-cli.nix`, with a narrower entry point
#     and no watchexec wrapper. One source, two derivations, no second
#     implementation.
#   * `dagu` is wrapped on, because the projection validates every file before
#     it publishes it (§3.5 of the 009 guide, P2-2). That is `nix/dagu.nix` —
#     the exception that already exists — so this adds no new dependency.
#   * the closure is python3 plus pyyaml, cached across every repository on the
#     same nixpkgs. The first-entry cost is measured in `STAGE_9_LOG.md` S-3.
{ lib
, python3Packages
, dagu
, makeWrapper
}:

python3Packages.buildPythonApplication {
  pname = "devman-project";
  version = "0.3.0";
  pyproject = true;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [ ../src ../pyproject.toml ];
  };

  build-system = [ python3Packages.hatchling ];
  dependencies = [ python3Packages.pyyaml ];

  nativeBuildInputs = [ makeWrapper ];

  # The renderer runs `dagu validate` on every file it is about to publish, so
  # it states its Dagu rather than inheriting one. A repository's shell has the
  # machine's `dagu` on PATH only when `installClient` is on, and the projection
  # must not depend on that option.
  postFixup = ''
    wrapProgram $out/bin/devman-project \
      --prefix PATH : ${lib.makeBinPath [ dagu ]}
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    $out/bin/devman-project --help > /dev/null
    $out/bin/devman-project apply --help > /dev/null
    runHook postInstallCheck
  '';

  meta = {
    description = "The devman projection renderer, called at devenv shell entry";
    homepage = "https://github.com/Bullish-Design/devman";
    mainProgram = "devman-project";
  };
}
