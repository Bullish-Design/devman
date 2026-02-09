{ pkgs, config, ... }:

let
  root = config.git.root;
in
{
  packages = with pkgs; [
    asciinema
    git
    just
    jujutsu
    jq
    ripgrep
  ];

  languages.python = {
    enable = true;
    version = "3.13";
    directory = "../";
    venv.enable = true;
    uv.enable = true;
  };

  scripts.devman.exec = ''
    cd "${root}"
    just devman "$@"
  '';

  # devenv.nix defines the stable command interfaces; the Justfile is the
  # experimentation layer for test workflows and output tweaks.
  scripts.test.exec = ''
    cd "${root}"
    just test "$@"
  '';

  scripts.entrypoint.exec = ''
    set -euo pipefail
    cd "${root}"

    config="''${1:-sample-config.toml}"

    if [ ! -f "$config" ]; then
      echo "Error: config file not found: $config" >&2
      exit 1
    fi

    # ── Parse answers from the TOML config ──────────────────────────
    file_type="$(${pkgs.python3}/bin/python3 -c "
import tomllib, sys
with open(sys.argv[1], 'rb') as f:
    cfg = tomllib.load(f)
print(cfg['file_type_template']['file_type'])
" "$config")"

    description="$(${pkgs.python3}/bin/python3 -c "
import tomllib, sys
with open(sys.argv[1], 'rb') as f:
    cfg = tomllib.load(f)
print(cfg['file_type_template'].get('description', ''))
" "$config")"

    template_name="file-type"
    template_src="src/devman/seed_templates/$template_name"

    if [ ! -d "$template_src" ]; then
      echo "Error: seed template not found: $template_src" >&2
      exit 1
    fi

    # ── Build timestamped output directory ──────────────────────────
    timestamp="$(date +%y%m%d%H%M%S)"
    output_dir="output/$template_name/$timestamp"
    term_dir="$output_dir/.term"

    mkdir -p "$term_dir"

    echo "──────────────────────────────────────────────"
    echo " template  : $template_name"
    echo " file_type : $file_type"
    echo " output    : $output_dir"
    echo " recording : $term_dir/session.cast"
    echo "──────────────────────────────────────────────"

    # ── Generate the template instance inside an asciinema session ──
    asciinema rec "$term_dir/session.cast" --command "
      set -e
      echo 'Generating $template_name instance for file_type=$file_type ...'
      copier copy --defaults \
        --data file_type='$file_type' \
        --data description='$description' \
        '$template_src' '$output_dir'
      echo
      echo 'Generated files:'
      find '$output_dir' -not -path '*/.term/*' -not -path '*/.term' | sort
      echo
      echo 'Done.'
    "

    echo
    echo "Instance saved to: $output_dir"
    echo "Recording saved to: $term_dir/session.cast"
  '';

  enterShell = ''
    echo
    echo --------------------------------------------------------
    echo
    echo " Welcome to the Devman development environment! "
    # echo
    # echo " To get started, try running: devman launch"
    echo
    echo --------------------------------------------------------
    echo
    git --version
    # echo
    # echo IWD: "$(pwd)"
    echo
    cd "${root}"
    echo PWD: "$(pwd)"
    echo
  '';

}
