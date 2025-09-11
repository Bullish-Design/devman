{% if use_nix %}
# Example container definition (dockerTools). Adjust as needed.
{ pkgs, ... }:
pkgs.dockerTools.buildImage {
  name = "{{ project_slug }}-container";
  tag = "latest";
  contents = [ ];
  config = {
    Cmd = [ "bash" ];
    WorkingDir = "/app";
  };
}
{% endif %}
