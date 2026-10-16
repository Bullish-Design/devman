# `checks.<system>.hm-module`: evaluate the Home Manager module with a test
# configuration, then prove what it generates. No service starts here.
{ self, pkgs, home-manager, dagu }:

let
  inherit (pkgs) lib;

  mkHome = devman: home-manager.lib.homeManagerConfiguration {
    inherit pkgs;
    modules = [
      self.homeManagerModules.default
      {
        home = {
          username = "tester";
          homeDirectory = "/home/tester";
          stateVersion = "25.05";
        };
        services.devman = { enable = true; } // devman;
      }
    ];
  };

  good = mkHome { };
  files = good.config.home-files;

  # The assertions that fail, as text. Home Manager throws on a failed
  # assertion and hides the text from Nix, so a bare module evaluation with stub
  # options reads `config.assertions` instead.
  failures = devman:
    let
      stub = { options, ... }: {
        options = {
          assertions = lib.mkOption { type = lib.types.listOf lib.types.raw; default = [ ]; };
          home.homeDirectory = lib.mkOption { type = lib.types.str; default = "/home/tester"; };
          home.packages = lib.mkOption { type = lib.types.listOf lib.types.raw; default = [ ]; };
          systemd.user.services = lib.mkOption { type = lib.types.attrsOf lib.types.raw; default = { }; };
        };
        config._module.args.pkgs = pkgs;
      };
      evaluated = lib.evalModules {
        modules = [
          stub
          self.homeManagerModules.default
          { services.devman = { enable = true; } // devman; }
        ];
      };
    in
    map (a: a.message) (lib.filter (a: !a.assertion) evaluated.config.assertions);

  expect = what: devman: needle:
    let msgs = failures devman;
    in
    if lib.any (m: lib.hasInfix needle m) msgs
    then true
    else throw "hm-module: ${what} did not fail with \"${needle}\". Got: ${builtins.toJSON msgs}";

  negatives = [
    (expect "host 0.0.0.0" { host = "0.0.0.0"; } "is not loopback")
    (expect "defaultQueue typo" { defaultQueue = "typo"; } "is not a key of services.devman.queues")
    (expect "equal dirs" { stateDir = "/home/tester/.config/devman"; } "must differ")
    (expect "nested dirs" { stateDir = "/home/tester/.config/devman/state"; } "must differ")
  ];

  positives = assert (failures { }) == [ ]; true;
in
assert positives;
assert lib.all (x: x) negatives;
pkgs.runCommand "devman-hm-module-check"
  { nativeBuildInputs = [ dagu pkgs.gnugrep pkgs.gnused ]; }
  ''
    units=${files}/.config/systemd/user
    for u in devman-dagu.service devman-watch.service; do
      test -e "$units/$u" || { echo "missing unit $u"; exit 1; }
    done
    cat "$units/devman-dagu.service" "$units/devman-watch.service"

    grep -q "ExecStart=.*dagu start-all --config " "$units/devman-dagu.service"
    grep -q "^UnsetEnvironment=SHELL" "$units/devman-dagu.service"
    grep -q "^Restart=on-failure" "$units/devman-dagu.service"
    grep -q "^X-Restart-Triggers=" "$units/devman-dagu.service"
    grep -q "^After=devman-dagu.service" "$units/devman-watch.service"
    grep -q "devman watch --debounce 300ms" "$units/devman-watch.service"

    config=$(sed -n 's/^ExecStart=.* --config //p' "$units/devman-dagu.service")
    echo "config: $config"
    cat "$config"
    if grep -q '@' "$config"; then echo "config.yaml has an @ token left"; exit 1; fi
    grep -q '^port: 8080$' "$config"
    grep -q 'dags_dir: "/home/tester/.local/state/devman/dags"' "$config"
    grep -q 'base_config: "/home/tester/.local/state/devman/base.yaml"' "$config"
    grep -q '"name":"light","max_concurrency":4' "$config" \
      || grep -q '"max_concurrency":4,"name":"light"' "$config"

    # The seed base.yaml with its tokens filled, and an empty DAG.
    export HOME=$TMPDIR/home DAGU_HOME=$TMPDIR/dagu
    mkdir -p "$HOME" "$DAGU_HOME" $TMPDIR/state/dags/p
    sed 's|@bash@|${pkgs.bash}/bin/bash|' ${../tests/fixtures/library/base.yaml} \
      > $TMPDIR/base.yaml
    sed -e "s|/home/tester/.local/state/devman/base.yaml|$TMPDIR/base.yaml|" \
        -e "s|/home/tester/.local/state/devman/dags|$TMPDIR/state/dags|" \
        "$config" > $TMPDIR/config.yaml
    cat > $TMPDIR/state/dags/p/p.empty.yaml <<'EOF'
    steps:
      - name: noop
        run: "true"
    EOF
    dagu validate --config $TMPDIR/config.yaml $TMPDIR/state/dags/p/p.empty.yaml
    touch $out
  ''
