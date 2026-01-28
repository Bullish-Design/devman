{ pkgs, ... }:

{
  packages = [ (pkgs.python312.withPackages (ps: [ ps.typer ])) ];

  scripts.hello.exec = ''
    python ${../hello.py} "$@"
  '';
}
