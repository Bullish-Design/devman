# The devman CLI (CONCEPT.md §10) — `run`, `show`, `doctor`, and the watcher.
#
# WHERE IT SHIPS FROM, AND WHY ONLY THERE.
#
# `nixosModules.default` puts this on the machine's PATH. The devenv module does
# not, and that is §3.1's second rule: what the two interfaces share must be
# TEXT — queue names, the four variable names, the `.devman/.runs/` path shape,
# the registry schema. `nix/dagu.nix` is the single measured exception, and it
# costs two store paths holding one identical binary.
#
# A Python program is not text. Shipping it from both interfaces would build it
# twice, under two nixpkgs that differ in hundreds of attributes, and put two
# `devman` binaries on one PATH resolved by profile order — which is exactly the
# hazard §3.3 records against `devman 0.2.0`. A devenv shell inherits the
# machine profile's PATH, so one machine-side install reaches every repository
# shell on that machine.
#
# ONE PART OF THIS SOURCE TREE IS AN EXCEPTION, AND IT AMENDS §3.1.
#
# `nix/renderer.nix` builds the same `src/` with a narrower entry point,
# `devman-project`, and the devenv module builds it under the CONSUMING
# repository's nixpkgs. It is not offered here and it is not on any PATH.
#
# The reason is the shell-entry guard rather than the charter: a `devman` found
# on PATH is a run-time fact, so its identity cannot enter `planFile`, so the
# guard cannot observe it — and a machine-side upgrade would then change the
# rendering rules while every repository kept a projection produced by the old
# renderer, with nothing re-projecting. CONCEPT.md §3.1 carries the amendment;
# `nix/renderer.nix` carries the whole argument (009 stage 3).
#
# WHAT IS WRAPPED ONTO ITS PATH, AND WHY.
#
#   dagu       `devman run` triggers with a local `dagu enqueue`, and only a
#              local process resolves `log_dir` into the project that triggered
#              the run (E2). Wrapping the plane's own Dagu is what stops the CLI
#              and the service drifting to two versions.
#   watchexec  the watcher execs it (§8, D7). One process per machine.
#
# The CLI never inherits `DAGU_HOME`: an unset one makes `dagu` build a fresh
# home and seed five example DAGs (S2). The NixOS module wraps this with
# `--dagu-home` and `--registry` when the machine moves either directory.
{ lib
, python3Packages
, dagu
, watchexec
, makeWrapper
}:

python3Packages.buildPythonApplication {
  pname = "devman";
  version = "0.3.0";
  pyproject = true;

  # Only the CLI's own files. The repository also holds `.scratch/` (a quarter
  # of a megabyte of design notes), `.devenv/` state and the group files, none
  # of which belong in this closure.
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [ ../src ../pyproject.toml ];
  };

  build-system = [ python3Packages.hatchling ];
  dependencies = [ python3Packages.pyyaml ];

  nativeBuildInputs = [ makeWrapper ];

  postFixup = ''
    wrapProgram $out/bin/devman \
      --prefix PATH : ${lib.makeBinPath [ dagu watchexec ]}
  '';

  # `--help` proves the entry point resolves and every module imports. The
  # measurements that matter are in `STAGE_3_LOG.md` and run against the real
  # registry: a module that evaluates but was never entered has not been tested.
  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck
    $out/bin/devman --help > /dev/null
    $out/bin/devman doctor --help > /dev/null
    runHook postInstallCheck
  '';

  meta = {
    description = "The devman automation plane's CLI";
    homepage = "https://github.com/Bullish-Design/devman";
    mainProgram = "devman";
  };
}
