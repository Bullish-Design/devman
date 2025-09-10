from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping, Dict, List
import tempfile
import os

from copier import run_copy

DEFAULT_ANSWERS_FILE = ".devman/devman_config.yml"


def _run_copy_kwargs(
    template_path: str | Path,
    dst_path: str | Path,
    data: Mapping[str, Any] | None,
    *,
    overwrite: bool,  # <-- use overwrite, not force
    pretend: bool,
    quiet: bool,
    vcs_ref: str | None,
    subdirectory: str | None,
) -> dict:
    kwargs: dict[str, Any] = dict(
        src_path=str(template_path),
        dst_path=str(dst_path),
        data=dict(data or {}),
        answers_file=DEFAULT_ANSWERS_FILE,
        overwrite=overwrite,  # <-- pass overwrite through
        pretend=pretend,
        quiet=quiet,
        # NOTE: do not set skip_if_exists unless providing a tuple of patterns
    )
    if vcs_ref:
        kwargs["vcs_ref"] = vcs_ref
    if subdirectory:
        kwargs["subdirectory"] = subdirectory
    return kwargs


def generate_from_template(
    template_path: str | Path,
    dst_path: str | Path,
    data: Mapping[str, Any] | None = None,
    *,
    force: bool = False,  # CLI flag
    pretend: bool = False,
    quiet: bool = True,
    vcs_ref: str | None = None,
    subdirectory: str | None = None,
) -> None:
    kwargs = _run_copy_kwargs(
        template_path,
        dst_path,
        data,
        overwrite=bool(force),  # <-- map force -> overwrite
        pretend=pretend,
        quiet=quiet,
        vcs_ref=vcs_ref,
        subdirectory=subdirectory,
    )
    run_copy(**kwargs)


def _read_file_safe(p: Path) -> dict:
    try:
        t = p.read_text(encoding="utf-8")
        return {"type": "text", "text": t, "size": p.stat().st_size}
    except UnicodeDecodeError:
        raw = p.read_bytes()
        import base64 as _b

        return {
            "type": "binary",
            "b64": _b.b64encode(raw).decode("ascii"),
            "size": len(raw),
        }


def snapshot_render_to_memory(
    template_path: str | Path,
    data: Mapping[str, Any] | None = None,
    *,
    vcs_ref: str | None = None,
    subdirectory: str | None = None,
) -> Dict[str, dict]:
    """Render the template into a temporary directory and return an in-memory snapshot."""
    with tempfile.TemporaryDirectory(prefix="devman-demo-") as tmp:
        tmp_path = Path(tmp)
        kwargs = _run_copy_kwargs(
            template_path,
            tmp_path,
            data,
            overwrite=True,  # <-- ensure full materialization in sandbox
            pretend=False,
            quiet=True,
            vcs_ref=vcs_ref,
            subdirectory=subdirectory,
        )
        run_copy(**kwargs)

        snapshot: Dict[str, dict] = {}
        for p in tmp_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(tmp_path).as_posix()
                snapshot[rel] = _read_file_safe(p)

        # NEW (includes dotfiles):
        for root, _dirs, files in os.walk(tmp_path):
            root_path = Path(root)
            for fname in files:
                p = root_path / fname
                rel = p.relative_to(tmp_path).as_posix()
                snapshot[rel] = _read_file_safe(p)
        return snapshot


def plan_against_destination(
    snapshot: Dict[str, dict],
    dest: Path,
    *,
    force: bool = False,
) -> List[dict]:
    plan: List[dict] = []
    for rel, meta in snapshot.items():
        target = dest / rel
        size = meta.get("size", 0)
        if not target.exists():
            plan.append({"path": rel, "status": "create", "size": size, "note": ""})
        else:
            try:
                existing = target.read_text(encoding="utf-8")
                same = meta.get("type") == "text" and existing == meta.get("text")
            except UnicodeDecodeError:
                same = target.stat().st_size == size
            if same:
                if force:
                    plan.append(
                        {
                            "path": rel,
                            "status": "overwrite",
                            "size": size,
                            "note": "identical content",
                        }
                    )
                else:
                    plan.append(
                        {
                            "path": rel,
                            "status": "skip-identical",
                            "size": size,
                            "note": "",
                        }
                    )
            else:
                if force:
                    plan.append(
                        {"path": rel, "status": "overwrite", "size": size, "note": ""}
                    )
                else:
                    plan.append(
                        {
                            "path": rel,
                            "status": "skip-exists",
                            "size": size,
                            "note": "use --force to overwrite",
                        }
                    )
    return sorted(plan, key=lambda x: x["path"])
