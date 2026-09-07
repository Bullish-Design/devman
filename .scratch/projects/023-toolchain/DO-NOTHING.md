# What is already correct

Stated plainly, because most of this design does not need to change.

1. **The RepoMan shared toolchain venv is the right answer for CLIs.** One copy
   of `gitman` on the machine, one `repoman doctor` that verifies the whole
   venv is mutually consistent (measured: "33 package(s) mutually compatible"),
   one command to upgrade every repository at once. Its only defect is that it
   was asked to do a second job it cannot do.

2. **`gitman` reaching a devenv through `PATH` is correct and cheap.** The
   console script carries its own shebang, so it can never pick the wrong
   interpreter. Measured 1.07 s.

3. **Dagu's daemon environment is correctly minimal.** No leaked developer
   state, `UnsetEnvironment=SHELL`, an explicit `PATH`. Requiring
   `devenv shell --` in a step is the right contract; it is what makes a step
   run the same environment the developer's checkout defines.

4. **`env_passthrough_prefixes: [DEVMAN_]` is correct.** It forces workflow
   configuration through `params:`, which is inspectable, instead of through
   ambient shell state, which is not.

5. **`GPU_LLM_BASE_URL` / `GPU_LLM_MODEL` as DAG params is correct**, and the
   measurement shows it is also the only mechanism that works. Nothing about
   them belongs in Nix.

6. **`gitman/uv.lock` is the reproducibility model to copy.** It pins `pyjutsu`
   to an exact GitHub release URL with a sha256. The right pin already exists in
   this fleet; it just is not the one `repoman.lock` uses.

7. **`pyjutsu` shipping as a prebuilt `abi3` wheel is correct.** `cp313-abi3`
   works across 3.13.13 and 3.13.14, so every consumer takes zero Rust.
   `repoman.nativeBuild` correctly defaults to false and is opted into only in
   pyjutsu's own repository.

8. **The loud failure on an unset `${DEVMAN_PROJECT_DIR}`.** Measured: the run
   records `Failed` with the exact path in the message. Compare `/home/andrew/$h`
   for what the silent version of the same mistake leaves behind.

9. **Home Manager owning `python3`, `git`, `ruff`, `node`, `gh`.** Right layer,
   right rollback story.

10. **devman's decision to give `base:unit` an explicit nixpkgs pytest store
    path rather than a bare `pytest` on `PATH`.** That comment in `devenv.nix`
    describes exactly the failure this whole investigation found somewhere else.
    The reasoning was already correct; it had just not been applied to
    `python3` itself.

11. **The inferference router.** One router, declared in
    `machines/server.nix` from the pinned flake input, serving `gemma` at
    `127.0.0.1:8100`, with model placement deliberately kept out of Nix so a
    resident-set change is an edit plus a reconcile rather than a rebuild. The
    unit even forces its own `PATH`, for the same reason the Dagu unit does.
    Verified up and answering. Nothing to change here.
