{ pkgs, ... }:
{
  imports = [ ./gen/devman.nix ];
  packages = [ pkgs.jq ];
}
