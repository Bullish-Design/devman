from pathlib import Path

import pytest

from devman.domain.errors import WatchError
from devman.watcher.config import DevmanWatchConfig, PatternConfig
from devman.watcher.handlers import (
    handle_instantiation,
    replace_source_with_symlink,
    resolve_target_instance_path,
)


def _config(instance_store: Path, template_store: Path) -> DevmanWatchConfig:
    return DevmanWatchConfig.model_validate(
        {
            "pattern": [{"pattern": "src/modules/*", "template": "module-template"}],
            "settings": {
                "instance_store": str(instance_store),
                "template_store": str(template_store),
            },
        }
    )


def test_resolve_target_instance_path_is_under_instance_store(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source = repo_root / "src" / "modules" / "auth"
    source.mkdir(parents=True)

    config = _config(tmp_path / "instances", tmp_path / "templates")
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")

    resolved = resolve_target_instance_path(source, pattern, repo_root, config)

    assert resolved.parent == (tmp_path / "instances")
    assert "repo-module-template-src-modules-auth" in resolved.name


def test_handle_instantiation_executes_steps_with_injected_functions(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    trigger = repo_root / "src" / "modules" / "auth"
    trigger.mkdir(parents=True)

    templates = tmp_path / "templates"
    (templates / "module-template").mkdir(parents=True)
    config = _config(tmp_path / "instances", templates)
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")

    calls: list[str] = []

    def fake_copier(template_path: Path, instance_path: Path) -> None:
        calls.append("copier")
        assert template_path == templates / "module-template"
        instance_path.mkdir(parents=True)

    def fake_init(instance_path: Path) -> None:
        calls.append("init")
        (instance_path / ".git").mkdir()

    def fake_replace(source_path: Path, instance_path: Path) -> None:
        calls.append("replace")
        if source_path.exists():
            import shutil

            shutil.rmtree(source_path)
        source_path.symlink_to(instance_path, target_is_directory=True)

    instance_path = handle_instantiation(
        pattern=pattern,
        matched_path=trigger,
        change="added",
        repo_root=repo_root,
        config=config,
        run_copier_fn=fake_copier,
        init_repo_fn=fake_init,
        replace_path_fn=fake_replace,
    )

    assert calls == ["copier", "init", "replace"]
    assert instance_path.exists()
    assert trigger.is_symlink()


def test_replace_source_with_symlink_refuses_unrelated_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.touch()
    current = tmp_path / "current-target"
    current.touch()
    source.unlink()
    source.symlink_to(current)

    with pytest.raises(WatchError):
        replace_source_with_symlink(source, tmp_path / "different-target")
