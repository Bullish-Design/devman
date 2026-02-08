from pathlib import Path
from types import SimpleNamespace

import pytest

from devman.domain.errors import WatchError
from devman.watcher.config import DevmanWatchConfig, PatternConfig
from devman.watcher.handlers import (
    handle_instantiation,
    handle_pattern_match,
    initialize_instance_repository,
    replace_source_with_symlink,
    resolve_target_instance_path,
    run_copier_instantiation,
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


def test_handle_instantiation_accepts_none_injected_functions(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    trigger = repo_root / "src" / "modules" / "auth"
    trigger.mkdir(parents=True)

    templates = tmp_path / "templates"
    (templates / "module-template").mkdir(parents=True)
    config = _config(tmp_path / "instances", templates)
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")

    instance_path = handle_instantiation(
        pattern=pattern,
        matched_path=trigger,
        change="added",
        repo_root=repo_root,
        config=config,
        resolve_instance_path_fn=None,
        run_copier_fn=None,
        init_repo_fn=None,
        replace_path_fn=None,
    )

    assert instance_path.exists()
    assert trigger.is_symlink()


def test_replace_source_with_symlink_file_source_happy_path(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("print('hello')")

    instance_path = tmp_path / "generated-instance"
    instance_path.mkdir()
    expected_target = instance_path / source.name
    expected_target.write_text("print('from instance')")

    replace_source_with_symlink(source, instance_path)

    assert source.is_symlink()
    assert source.resolve() == expected_target.resolve()


def test_replace_source_with_symlink_directory_source_happy_path(tmp_path: Path) -> None:
    source = tmp_path / "src-dir"
    source.mkdir()

    instance_path = tmp_path / "generated-instance"
    instance_path.mkdir()

    replace_source_with_symlink(source, instance_path)

    assert source.is_symlink()
    assert source.resolve() == instance_path.resolve()


def test_replace_source_with_symlink_refuses_unrelated_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.touch()
    current = tmp_path / "current-target"
    current.touch()
    source.unlink()
    source.symlink_to(current)

    with pytest.raises(WatchError):
        replace_source_with_symlink(source, tmp_path / "different-target")


def test_handle_instantiation_modified_file_skips_destructive_replace_by_default(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    trigger = repo_root / "src" / "modules" / "auth.py"
    trigger.parent.mkdir(parents=True)
    trigger.write_text("print('hello')", encoding="utf-8")

    templates = tmp_path / "templates"
    (templates / "module-template").mkdir(parents=True)
    config = _config(tmp_path / "instances", templates)
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")

    with pytest.raises(WatchError, match="Refusing destructive modified event"):
        handle_instantiation(
            pattern=pattern,
            matched_path=trigger,
            change="modified",
            repo_root=repo_root,
            config=config,
        )

    assert trigger.exists()
    assert not trigger.is_symlink()


def test_handle_instantiation_modified_directory_skips_destructive_replace_by_default(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    trigger = repo_root / "src" / "modules" / "auth"
    trigger.mkdir(parents=True)
    sentinel = trigger / "README.md"
    sentinel.write_text("keep me", encoding="utf-8")

    templates = tmp_path / "templates"
    (templates / "module-template").mkdir(parents=True)
    config = _config(tmp_path / "instances", templates)
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")

    with pytest.raises(WatchError, match="Refusing destructive modified event"):
        handle_instantiation(
            pattern=pattern,
            matched_path=trigger,
            change="modified",
            repo_root=repo_root,
            config=config,
        )

    assert trigger.exists()
    assert trigger.is_dir()
    assert not trigger.is_symlink()
    assert sentinel.exists()


def test_handle_pattern_match_swallows_watcherror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pattern = PatternConfig(pattern="src/modules/*", template="module-template")
    config = _config(tmp_path / "instances", tmp_path / "templates")

    def fail(*_: object, **__: object) -> None:
        raise WatchError("skip")

    monkeypatch.setattr("devman.watcher.handlers.handle_instantiation", fail)

    # no raise; errors should be handled as a skipped path
    handle_pattern_match(pattern, Path("src/modules/auth"), "added", tmp_path, config)


def test_run_copier_instantiation_invokes_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["text"] = text
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("devman.watcher.handlers.subprocess.run", fake_run)

    template_path = tmp_path / "templates" / "module-template"
    instance_path = tmp_path / "instances" / "generated"

    run_copier_instantiation(template_path, instance_path)

    assert captured["cmd"] == [
        "copier",
        "copy",
        "--defaults",
        str(template_path),
        str(instance_path),
    ]
    assert captured["capture_output"] is True
    assert captured["text"] is True



def test_run_copier_instantiation_existing_target_without_force_raises(
    tmp_path: Path,
) -> None:
    template_path = tmp_path / "templates" / "module-template"
    instance_path = tmp_path / "instances" / "generated"
    instance_path.mkdir(parents=True)

    with pytest.raises(WatchError, match="Refusing to overwrite existing target"):
        run_copier_instantiation(template_path, instance_path)


def test_run_copier_instantiation_existing_target_with_force_reinstantiates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["text"] = text
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("devman.watcher.handlers.subprocess.run", fake_run)

    template_path = tmp_path / "templates" / "module-template"
    instance_path = tmp_path / "instances" / "generated"
    instance_path.mkdir(parents=True)
    (instance_path / "stale.txt").write_text("stale", encoding="utf-8")

    run_copier_instantiation(template_path, instance_path, force=True)

    assert instance_path.exists() is False
    assert captured["cmd"] == [
        "copier",
        "copy",
        "--defaults",
        str(template_path),
        str(instance_path),
    ]

def test_initialize_instance_repository_uses_jj_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance_path = tmp_path / "instance"
    instance_path.mkdir()

    commands: list[list[str]] = []

    def fake_which(binary: str) -> str | None:
        return "/usr/bin/jj" if binary == "jj" else None

    def fake_run(cmd: list[str], cwd: Path, capture_output: bool, text: bool) -> SimpleNamespace:
        commands.append(cmd)
        assert cwd == instance_path
        assert capture_output is True
        assert text is True
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("devman.watcher.handlers.shutil.which", fake_which)
    monkeypatch.setattr("devman.watcher.handlers.subprocess.run", fake_run)

    initialize_instance_repository(instance_path)

    assert commands == [["jj", "git", "init"]]
