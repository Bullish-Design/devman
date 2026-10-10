"""Assemble one devman registry from project inputs.

The Nix function in `nix/registry.nix` runs this script inside a build. For each
project it calls the existing renderer (`devman project render`) and writes the
bundle it returns into one output directory:

    generation.json
    projects/<project>/{metadata.json,projection.json,workflows/<name>.yaml}
    dags/<project>.<name>.yaml -> ../projects/<project>/workflows/<name>.yaml

This is the layout that `services.devman-dagu` reads. The script holds no
rendering rule. It writes bytes, links, and one `generation.json`, then runs
`dagu validate` on every workflow it wrote.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def fail(message: str) -> None:
    print(f"devman registry: {message}", file=sys.stderr)
    raise SystemExit(1)


def manifest_text(name: str, groups: list[str], policy: str) -> str:
    quoted = ", ".join(json.dumps(group) for group in groups)
    return (
        "schema = 1\n"
        f"project = {json.dumps(name)}\n"
        f"groups = [{quoted}]\n"
        f"policy = {json.dumps(policy)}\n"
    )


def project_root(scratch: Path, name: str, project: dict) -> Path:
    """Return a directory that holds this project's `.devman` files."""

    source = project.get("source")
    if source:
        root = Path(source)
        manifest = root / ".devman" / "project.toml"
        if not manifest.is_file():
            fail(f"project '{name}': {manifest} does not exist")
        declared = tomllib.loads(manifest.read_text()).get("project")
        if declared != name:
            fail(
                f"project '{name}': the manifest at {manifest} names "
                f"'{declared}'; the attribute name must match"
            )
        return root

    root = scratch / "roots" / name
    devman = root / ".devman"
    devman.mkdir(parents=True)
    (devman / "project.toml").write_text(
        manifest_text(name, project["groups"], project["policy"])
    )
    for local in ("triggers", "writes"):
        if project.get(local):
            (devman / f"{local}.toml").write_bytes(Path(project[local]).read_bytes())
    return root


def render(devman: str, root: Path, name: str, spec: dict, project: dict, bundle: Path):
    command = [
        devman,
        "project",
        "render",
        "--root",
        str(root),
        "--checkout",
        project["path"],
        "--policy-root",
        spec["policyRoot"],
        "--overlay-root",
        spec["overlayRoot"],
        "--generation",
        str(spec["generation"]),
        "--dagu-digest",
        spec["daguDigest"],
        "--output",
        str(bundle),
    ]
    if spec.get("toolchainDigest"):
        command += ["--toolchain-digest", spec["toolchainDigest"]]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        fail(f"cannot render project '{name}'\n{done.stderr.strip()}")
    return json.loads(bundle.read_text())


def write_bundle(out: Path, raw: dict) -> None:
    for relative, body in sorted(raw["files"].items()):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(body, validate=True))
    for relative, destination in sorted(raw["links"].items()):
        link = out / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(destination)


def validate(out: Path, dagu: str, scratch: Path) -> None:
    env = dict(os.environ, HOME=str(scratch), DAGU_HOME=str(scratch / "dagu"))
    (scratch / "dagu").mkdir(exist_ok=True)
    failed = []
    for workflow in sorted(out.glob("projects/*/workflows/*.yaml")):
        done = subprocess.run(
            [dagu, "validate", str(workflow)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if done.returncode != 0:
            failed.append(f"{workflow.relative_to(out)}\n{done.stderr or done.stdout}")
    if failed:
        fail("dagu refuses a rendered workflow\n" + "\n".join(failed))


def check_links(out: Path) -> None:
    for link in sorted((out / "dags").iterdir()):
        if not link.is_symlink() or not link.resolve().is_file():
            fail(f"dags/{link.name} does not resolve to a rendered workflow")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--devman", required=True)
    ap.add_argument("--dagu", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    spec["daguDigest"] = "sha256:" + hashlib.sha256(Path(args.dagu).read_bytes()).hexdigest()
    out = Path(args.out)
    (out / "projects").mkdir(parents=True)
    (out / "dags").mkdir()

    generations = []
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name, project in sorted(spec["projects"].items()):
            root = project_root(scratch, name, project)
            raw = render(
                args.devman, root, name, spec, project, scratch / f"{name}.bundle.json"
            )
            if raw["project"] != name:
                fail(f"project '{name}' rendered as '{raw['project']}'")
            generations.append(raw["generation"])
            write_bundle(out, raw)
        validate(out, args.dagu, scratch)

    if any(item != generations[0] for item in generations):
        fail("the projects rendered different generation identities")
    check_links(out)
    (out / "generation.json").write_text(
        json.dumps(generations[0], sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
