"""Action handlers for watcher match dispatch and side effects."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from devman.domain.errors import WatchError
from devman.watcher.config import DevmanWatchConfig, PatternConfig

logger = logging.getLogger(__name__)

WatcherHandler = Callable[
    [PatternConfig, Path, str, Path, DevmanWatchConfig],
    None,
]


def handle_pattern_match(
    pattern: PatternConfig,
    matched_path: Path,
    change: str,
    repo_root: Path,
    config: DevmanWatchConfig,
) -> None:
    """Default watcher handler that instantiates templates for matched paths."""
    try:
        handle_instantiation(
            pattern=pattern,
            matched_path=matched_path,
            change=change,
            repo_root=repo_root,
            config=config,
        )
    except WatchError as exc:
        logger.warning(
            "watcher handler skipped path: %s",
            exc,
            extra={
                "event": "watcher.handler.skipped",
                "change": change,
                "path": str(matched_path),
                "pattern": pattern.pattern,
                "template": pattern.template,
            },
        )


def handle_instantiation(
    pattern: PatternConfig,
    matched_path: Path,
    change: str,
    repo_root: Path,
    config: DevmanWatchConfig,
    *,
    resolve_instance_path_fn: Callable[[Path, PatternConfig, Path, DevmanWatchConfig], Path] | None = None,
    run_copier_fn: Callable[[Path, Path], None] | None = None,
    init_repo_fn: Callable[[Path], None] | None = None,
    replace_path_fn: Callable[[Path, Path], None] | None = None,
) -> Path:
    """Orchestrate template instantiation side-effects for a matched event."""
    resolve_instance_path_fn = resolve_instance_path_fn or resolve_target_instance_path
    run_copier_fn = run_copier_fn or run_copier_instantiation
    init_repo_fn = init_repo_fn or initialize_instance_repository
    replace_path_fn = replace_path_fn or replace_source_with_symlink

    source_path = _resolve_source_path(matched_path, repo_root)
    instance_path = resolve_instance_path_fn(source_path, pattern, repo_root, config)
    template_path = resolve_template_path(pattern.template, config)

    if source_path.is_symlink() and source_path.resolve() == instance_path.resolve():
        logger.info("watcher path already linked to instance", extra={"path": str(source_path)})
        return instance_path

    if instance_path.exists() and not source_path.exists():
        logger.info(
            "watcher instance already exists for missing source path; no-op",
            extra={"instance_path": str(instance_path), "path": str(source_path)},
        )
        return instance_path

    if not instance_path.exists():
        run_copier_fn(template_path, instance_path)
        init_repo_fn(instance_path)

    replace_path_fn(source_path, instance_path)
    logger.info(
        "watcher instantiation complete",
        extra={
            "event": "watcher.handler.instantiated",
            "change": change,
            "path": str(source_path),
            "instance_path": str(instance_path),
            "pattern": pattern.pattern,
            "template": pattern.template,
        },
    )
    return instance_path


def resolve_target_instance_path(
    source_path: Path,
    pattern: PatternConfig,
    repo_root: Path,
    config: DevmanWatchConfig,
) -> Path:
    """Resolve instance destination path from source, pattern, and config context."""
    repo_root = repo_root.resolve()
    try:
        relative_source = source_path.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise WatchError(f"Matched path is outside repository root: {source_path}") from exc

    instance_store = Path(config.settings.instance_store).expanduser().resolve()
    slug = _path_to_slug(relative_source)
    instance_name = f"{repo_root.name}-{pattern.template}-{slug}" if slug else f"{repo_root.name}-{pattern.template}"
    return instance_store / instance_name


def resolve_template_path(template_name: str, config: DevmanWatchConfig) -> Path:
    """Resolve and validate template path from watcher settings."""
    template_store = Path(config.settings.template_store).expanduser().resolve()
    template_path = template_store / template_name
    if not template_path.exists() or not template_path.is_dir():
        raise WatchError(f"Template not found: {template_path}")
    return template_path


def run_copier_instantiation(
    template_path: Path,
    instance_path: Path,
    force: bool = False,
) -> None:
    """Execute copier to instantiate a selected template into an instance path."""
    if instance_path.exists():
        if not force:
            raise WatchError(
                f"Refusing to overwrite existing target: {instance_path}. "
                "Re-run with force=True to replace it."
            )

        if instance_path.is_dir() and not instance_path.is_symlink():
            shutil.rmtree(instance_path)
        else:
            instance_path.unlink()

    instance_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["copier", "copy", "--defaults", str(template_path), str(instance_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise WatchError(proc.stderr.strip() or "copier instantiation failed")


def initialize_instance_repository(instance_path: Path) -> None:
    """Initialize version control metadata for a generated instance."""
    if not instance_path.exists() or not instance_path.is_dir():
        raise WatchError(f"Instance path is missing after instantiation: {instance_path}")

    if (instance_path / ".git").exists() or (instance_path / ".jj").exists():
        return

    repo_cmd = ["jj", "git", "init"] if shutil.which("jj") else ["git", "init"]
    proc = subprocess.run(repo_cmd, cwd=instance_path, capture_output=True, text=True)
    if proc.returncode != 0:
        raise WatchError(proc.stderr.strip() or "repository initialization failed")


def replace_source_with_symlink(source_path: Path, instance_path: Path) -> None:
    """Replace the matched source path with a symlink to the generated instance."""
    source_was_directory = source_path.is_dir() and not source_path.is_symlink()

    if source_path.is_symlink():
        current_target = source_path.resolve()
        file_target = _resolve_file_link_target(source_path, instance_path)
        if current_target in {instance_path.resolve(), file_target.resolve()}:
            return
        raise WatchError(f"Refusing to replace unrelated symlink: {source_path}")

    if not source_path.exists():
        raise WatchError(f"Matched source path no longer exists: {source_path}")

    if source_was_directory:
        shutil.rmtree(source_path)
        source_path.symlink_to(instance_path, target_is_directory=True)
    else:
        source_path.unlink()
        source_path.symlink_to(_resolve_file_link_target(source_path, instance_path), target_is_directory=False)


def _resolve_file_link_target(source_path: Path, instance_path: Path) -> Path:
    """Resolve symlink target for file sources.

    A file-oriented instance strategy may return a concrete file path. Otherwise,
    default to linking into the generated instance directory with the source file name.
    """
    if instance_path.exists() and instance_path.is_file():
        return instance_path
    if instance_path.suffix and not instance_path.exists():
        return instance_path
    return instance_path / source_path.name


def _resolve_source_path(matched_path: Path, repo_root: Path) -> Path:
    if matched_path.is_absolute():
        return matched_path
    return (repo_root / matched_path).resolve()


def _path_to_slug(path: Path) -> str:
    return "-".join(part for part in path.parts if part not in {".", ""})


DEFAULT_HANDLERS: tuple[WatcherHandler, ...] = (handle_pattern_match,)
