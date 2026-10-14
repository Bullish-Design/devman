# The registry function: project inputs in, one registry store path out.
#
# THE OUTPUT IS THE LAYOUT `services.devman-dagu` READS (CONCEPT.md §9.2):
#
#   generation.json
#   projects/<project>/{metadata.json,projection.json,workflows/<name>.yaml}
#   dags/<project>.<name>.yaml -> ../projects/<project>/workflows/<name>.yaml
#
# Point `services.devman-dagu.registryDir` at the result. The module reads a
# store path and never writes to it. A new registry is a new store path, so the
# NixOS generation is the atomic switch and the rollback.
#
# NO SECOND RENDERER. `nix/mk-registry.py` calls `devman project render` for
# each project, the same entry point the machine plane has always used, and
# writes the bundle it returns. It then runs `dagu validate` on every workflow.
#
# ARGUMENTS
#
#   projects      attrset, name -> project. Required and not empty.
#                 The name is the project identity (`.devman/project.toml`).
#     path        string, required. The absolute path of the checkout that the
#                 workflows run in. It is a run-time path, not a store path:
#                 a run writes `.devman/.runs/` there.
#     groups      list of group names. Required unless `source` is set.
#     policy      string, default "stable". The manifest `policy` field.
#     triggers    path or null. A `.devman/triggers.toml` for the project.
#     writes      path or null. A `.devman/writes.toml` for the project.
#     source      path or null. A directory that holds `.devman/project.toml`
#                 (and the optional `triggers.toml`, `writes.toml`), such as a
#                 flake input. Replaces `groups`, `policy`, `triggers`, `writes`.
#   policyRoot    path. A tree with `groups/`. The flake's own function sets
#                 this to its `groups/`. Override it to follow another policy.
#   overlayRoot   path or null. A central overlay with
#                 `projects/<project>/workflows/*.yaml`. Null means no overlay.
#   generation    integer, default 1. Recorded in `generation.json`.
#   toolchainDigest  "sha256:<64 hex>" or null. Recorded as is.
{ lib, runCommand, writeText, python3, dagu, devman }:

{ projects
, policyRoot
, overlayRoot ? null
, generation ? 1
, toolchainDigest ? null
, name ? "devman-registry"
}:

let
  allowed = [ "path" "groups" "policy" "triggers" "writes" "source" ];

  normalise = projectName: project:
    let
      unknown = lib.subtractLists allowed (builtins.attrNames project);
      fromSource = (project.source or null) != null;
    in
    assert lib.assertMsg (unknown == [ ])
      "devman mkRegistry: project '${projectName}' has unknown attribute(s): ${lib.concatStringsSep ", " unknown}";
    assert lib.assertMsg (builtins.isString (project.path or null) && lib.hasPrefix "/" project.path)
      "devman mkRegistry: project '${projectName}' needs `path`, an absolute string";
    assert lib.assertMsg (!(lib.hasPrefix "${builtins.storeDir}/" project.path))
      "devman mkRegistry: project '${projectName}' has a store path as `path`; a run writes there";
    assert lib.assertMsg (fromSource || builtins.isList (project.groups or null))
      "devman mkRegistry: project '${projectName}' needs `groups` or `source`";
    assert lib.assertMsg
      (!fromSource || (project.groups or null) == null && (project.triggers or null) == null && (project.writes or null) == null)
      "devman mkRegistry: project '${projectName}' sets `source` and also groups, triggers or writes";
    {
      inherit (project) path;
      source = project.source or null;
      groups = project.groups or [ ];
      policy = project.policy or "stable";
      triggers = project.triggers or null;
      writes = project.writes or null;
    };

  paths = lib.mapAttrsToList (_: p: p.path) projects;

  spec = writeText "devman-registry-spec.json" (builtins.toJSON {
    inherit generation toolchainDigest;
    projects = lib.mapAttrs normalise projects;
    policyRoot = "${policyRoot}";
    # `/var/empty` holds no `projects/` directory, so it means "no overlay".
    overlayRoot = if overlayRoot == null then "/var/empty" else "${overlayRoot}";
  });
in
assert lib.assertMsg (projects != { }) "devman mkRegistry: `projects` is empty";
assert lib.assertMsg (lib.length (lib.unique paths) == lib.length paths)
  "devman mkRegistry: two projects share one `path`";
runCommand name
{
  nativeBuildInputs = [ python3 ];
  meta.description = "A devman registry rendered from project inputs";
} ''
  python3 -I ${./mk-registry.py} \
    --spec ${spec} \
    --devman ${devman}/bin/devman \
    --dagu ${dagu}/bin/dagu \
    --out $out
''
