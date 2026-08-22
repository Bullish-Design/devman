# B3 — a module that disagrees with the tree it is evaluated under.
#
# Two references, one in each direction, chosen from the real 465-attribute
# difference between the machine's nixpkgs (26.11, rev d407951, 2026-07-05) and
# nixos-unstable (rev ffb3c9b, 2026-08-19):
#
#   cronet-go   exists in unstable, absent on the machine  (added upstream)
#   rust_1_95   exists on the machine, absent in unstable  (removed upstream)
#
# The names are arbitrary. What is being measured is the failure: which
# evaluation produces it, what it says, and how late it arrives.
{ direction }:
{ pkgs, lib, ... }:
{
  systemd.user.services.dagu-collide = {
    description = "B3 collision probe";
    serviceConfig.ExecStart =
      if direction == "newer-than-machine"
      then "${pkgs.cronet-go}/bin/probe"
      else "${pkgs.rust_1_95.rustc}/bin/probe";
  };
}
