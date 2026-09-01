{
  description = "devman - development automation plane";

  # The development environment is driven by `devenv.yaml` and entered with
  # `devenv shell`. It is not duplicated here: an earlier `devShells` output
  # re-declared a partial copy of devenv.yaml's inputs and had been broken for
  # some time in two independent ways, which is what an unused second path
  # looks like.
  #
  # What this flake carries is the Dagu package (`nix/dagu.nix`), the two module
  # interfaces, and the workflow groups:
  #
  #   nixosModules.default   one Dagu service, queues, state paths, ports
  #   modules/               the repo interface, imported via devenv.yaml
  #   groups/                workflow content, shadowed by name (§7.2, §7.3)
  #
  # Note what is NOT here: the NixOS module takes `pkgs` from the importing
  # machine and the devenv module takes `pkgs` from the consuming repo. Neither
  # reads this flake's own `nixpkgs` input. That input serves `packages` and
  # `checks` only, and §3.1's first rule is what keeps one flake able to serve
  # two nixpkgs without either constraining the other.

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # For a machine that already composes its own nixpkgs.
      overlays.default = final: _prev: {
        dagu = final.callPackage ./nix/dagu.nix { };
      };

      # The machine interface (§4). Evaluated under the importing machine's
      # nixpkgs, never this flake's.
      nixosModules.default = ./nix/nixos-module.nix;
      nixosModules.devman-dagu = ./nix/nixos-module.nix;

      packages = forAllSystems (pkgs:
        let dagu = pkgs.callPackage ./nix/dagu.nix { }; in
        {
          inherit dagu;

          # §3.1's table: `packages.default` is the devman CLI, and the NixOS
          # module is what puts it on a machine's PATH. It is not offered by the
          # devenv module — see the note at the top of nix/devman-cli.nix.
          devman = pkgs.callPackage ./nix/devman-cli.nix { inherit dagu; };
          default = pkgs.callPackage ./nix/devman-cli.nix { inherit dagu; };
        });

      checks = forAllSystems (pkgs:
        {
          # Every shipped workflow must load. Dagu rejects an unknown top-level
          # key outright and rejects a top-level `name:`, and neither failure is
          # visible until something tries to run the file (A5).
          groups-validate = pkgs.runCommand "devman-groups-validate"
            {
              nativeBuildInputs = [ (pkgs.callPackage ./nix/dagu.nix { }) ];
            } ''
            export HOME=$TMPDIR
            export DAGU_HOME=$TMPDIR/dagu
            mkdir -p "$DAGU_HOME"
            fail=0
            for f in ${./groups}/*/workflows/*.yaml; do
              echo "validating ''${f#${./groups}/}"
              dagu validate "$f" || fail=1
            done
            [ "$fail" = 0 ]
            touch $out
          '';

          # THE THIRD READER OF THE SHARED IDENTITY TABLE (009 P1-5).
          #
          # The grammar is stated twice — `src/devman/registry.py` for the CLI
          # and `modules/devenv.nix` for the repo interface — because §3.1 says
          # what the two interfaces share must be TEXT, and a Python function is
          # not text. `tests/fixtures/identity.json` is that text.
          #
          # This check reads the same file with `fromJSON` and asserts the
          # Nix-side pattern agrees with every case. The Python side asserts the
          # same table in `tests/unit/test_registry.py`, and the conformance
          # suite asserts the pinned Dagu accepts every name marked valid. That
          # is what makes duplicating a small grammar at both boundaries safe.
          identity-grammar =
            let
              table = builtins.fromJSON (builtins.readFile ./tests/fixtures/identity.json);
              # The devenv module's own pattern, spelled as it is spelled there.
              # `builtins.match` anchors, so the module carries no `^` or `$`.
              grammar = "[A-Za-z0-9][A-Za-z0-9._-]*";
              agrees = case: (builtins.match grammar case.name != null) == case.valid;
              disagreeing = builtins.filter (c: !(agrees c)) table.cases;
            in
            assert table.grammar == "^${grammar}$";
            assert disagreeing == [ ];
            pkgs.runCommand "devman-identity-grammar" { } "touch $out";

          # §3.8's case 12 — the hook's own refusal, run rather than read.
          #
          # The shell-entry guard compares the recorded path against
          # `$DEVENV_ROOT` WITHOUT FORKING (§5.2), and a forkless comparison
          # cannot undo the JSON encoding `src/devman/project.py` writes. Three
          # characters are therefore refused at registration, by name. That
          # refusal is bash inside a Nix string inside a devenv hook, which no
          # Python test can reach.
          #
          # THIS CUTS THE BLOCK OUT OF `modules/devenv.nix` AND RUNS IT. What is
          # tested is the bytes the hook uses, not a copy of them — a copy would
          # be the second implementation rule 5 warns about, and it would agree
          # with itself forever. The module carries the two sentinels and a
          # comment saying why its source text must stay runnable.
          hook-path-refusal = pkgs.runCommand "devman-hook-path-refusal" { } ''
            block=$(sed -n '/devman-hook: path-refusal begin/,/devman-hook: path-refusal end/p' \
              ${./modules/devenv.nix})
            if [ -z "$block" ]; then
              echo "the sentinels are gone from modules/devenv.nix" >&2
              exit 1
            fi
            echo "--- the block under test ---"
            printf '%s\n' "$block"

            check() {          # <path> <expected reason, or empty for accepted>
              devman_root="$1"
              eval "$block"
              if [ "$devman_badroot" != "$2" ]; then
                echo "FAIL: $(printf %q "$1") gave '''$devman_badroot''', wanted '''$2'''" >&2
                exit 1
              fi
            }

            # Refused, each by name. These are the three the guard cannot
            # compare once Python has encoded them.
            check 'has"quote'    'a double quote'
            check 'has\backslash' 'a backslash'
            check "$(printf 'has\tnewline')" 'a control character'
            check "$(printf 'has\ttab')"     'a control character'
            check "$(printf 'has\rreturn')"  'a control character'

            # ACCEPTED, and this half matters more: P2-1's complaint was that
            # the domain was narrower than the contract said, so everything
            # that is not one of the three above has to keep working.
            check /home/you/project            ""
            check '/home/you/with space'       ""
            check '/home/you/colon: space'     ""
            check '/home/you/hash#mark'        ""
            check '/home/you/café-日本'       ""
            check "/home/you/single'quote"     ""
            check '/home/you/{brace}$dollar'   ""
            check '/home/you/semi;colon|pipe'  ""

            touch $out
          '';

          # The Python test layer (`tests/README.md`, `STAGE_7_LOG.md` S-11).
          #
          # WHY A CHECK AND NOT ONLY A DEVENV TASK. `base:test` is `nix flake
          # check`, so anything that must run before a change lands has to be
          # here. `devenv tasks run base:unit` runs the same suite in about a
          # second for the developer; this one runs it hermetically, with the
          # pinned Dagu, on a machine that has never entered this shell.
          #
          # THE SUITE MUST NOT SEE THE INSTALLED PLANE, and the sandbox is what
          # guarantees it rather than a rule the tests are asked to keep:
          # `~/.local/share/devman` is not in the closure, and no Dagu service
          # is running. Every test builds its own registry under `tmp_path`.
          #
          # `dagu` on `nativeBuildInputs` is what makes the conformance layer
          # measure rather than skip — the same shape as `groups-validate`
          # above, and the same `HOME`/`DAGU_HOME` discipline, because `dagu`
          # seeds five example DAGs into an unset home on first use (S2).
          #
          # The source is copied out of the store because pytest writes
          # `__pycache__` and `.pytest_cache` beside the files it collects, and
          # a store path is read-only.
          python-tests =
            let
              python = pkgs.python313.withPackages (ps: [ ps.pytest ps.pyyaml ]);
              source = nixpkgs.lib.fileset.toSource {
                root = ./.;
                fileset = nixpkgs.lib.fileset.unions [ ./src ./tests ./pyproject.toml ];
              };
            in
            pkgs.runCommand "devman-python-tests"
              {
                nativeBuildInputs = [ python (pkgs.callPackage ./nix/dagu.nix { }) ];
              } ''
              export HOME=$TMPDIR
              export DAGU_HOME=$TMPDIR/dagu
              mkdir -p "$DAGU_HOME"
              cp -r ${source} ./suite
              chmod -R u+w ./suite
              cd ./suite
              pytest
              touch $out
            '';
        }
        // nixpkgs.lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          # The machine module's ASSERTIONS (009 P1-6, P3-1).
          #
          # `nix flake check` does not evaluate a NixOS configuration that
          # nobody builds, so an assertion with no test is unproved. This
          # evaluates the module six ways and reads `config.assertions` — which
          # is lazy, so nothing here builds a system.
          #
          # It asserts the MESSAGE as well as the failure. An assertion that
          # fires for the wrong reason is not a test.
          module-assertions =
            let
              lib = nixpkgs.lib;
              failures = args:
                let
                  system = (lib.nixosSystem {
                    modules = [
                      ./nix/nixos-module.nix
                      {
                        nixpkgs.hostPlatform = pkgs.stdenv.hostPlatform.system;
                        system.stateVersion = "25.05";
                        services.devman-dagu = { enable = true; } // args;
                      }
                    ];
                  }).config;
                in
                # Only this module's own. A bare `nixosSystem` also fails
                # NixOS's root-filesystem and boot-loader assertions, which say
                # nothing about the option under test.
                builtins.filter (m: lib.hasInfix "services.devman-dagu" m)
                  (map (a: a.message)
                    (builtins.filter (a: !a.assertion) system.assertions));

              evaluates = args: failures args == [ ];
              refusedBecause = args: text:
                let msgs = failures args;
                in msgs != [ ] && lib.any (m: lib.hasInfix text m) msgs;
            in
            assert evaluates { };                                    # the default
            assert evaluates { host = "127.0.0.1"; };                # IPv4 loopback
            assert evaluates { host = "127.0.0.53"; };               # 127.0.0.0/8
            assert evaluates { host = "::1"; };                      # IPv6 loopback
            assert evaluates { host = "localhost"; };
            assert refusedBecause { host = "0.0.0.0"; } "authentication";
            assert refusedBecause { host = "::"; } "authentication";
            assert refusedBecause { host = "192.168.1.10"; } "authentication";
            assert evaluates { queues = { light = 4; }; defaultQueue = "light"; };
            assert refusedBecause
              { queues = { light = 4; }; defaultQueue = "typo"; }
              "not a key in services.devman-dagu.queues";
            pkgs.runCommand "devman-module-assertions" { } "touch $out";

          # The machine module, run rather than evaluated (§9, rule 7). One VM,
          # one lingering user, one projection built by hand — because the
          # devenv half cannot run inside a NixOS test — and one real run.
          dagu-service = pkgs.testers.runNixOSTest (import ./nix/tests/dagu-service.nix {
            module = ./nix/nixos-module.nix;
            groups = ./groups;
            # P1-1's two source files, kept where the review wrote them. One
            # mentions DEVMAN_SELF_DIR in a comment and must still be given
            # DEVMAN_PROJECT_DIR; the other has an `env:` block naming neither
            # reserved name and must be refused (009 stage 8, §9.2).
            fixture = ./.scratch/projects/009-code-review/fixture-project;
            # The plan the devenv module would have written for that fixture,
            # in its shape (schema 4). Everything downstream of it in the test
            # is the real thing: the renderer, `dagu validate`, the published
            # bytes, the `dags/` link, the entry, and a run.
            plan = pkgs.writeText "devman-plan-fixture.json" (builtins.toJSON {
              schema = 4;
              project = "fixture";
              groups = [ ];
              workflows = { };
              triggers = null;
              renderer = "the devenv module records the renderer's store path here";
            });
          });
        });
    };
}
