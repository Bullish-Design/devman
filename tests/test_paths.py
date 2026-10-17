from pathlib import Path

from devman.paths import Paths


def test_defaults_come_from_the_home_directory() -> None:
    paths = Paths.from_env({})
    assert paths.overlay == Path("~/.config/devman").expanduser()
    assert paths.state == Path("~/.local/state/devman").expanduser()
    assert paths.library == paths.overlay / "library"
    assert paths.dagu_config is None
    assert paths.bash is None


def test_environment_sets_every_path() -> None:
    paths = Paths.from_env(
        {
            "DEVMAN_OVERLAY": "/o",
            "DEVMAN_STATE": "/s",
            "DEVMAN_LIBRARY": "/lib",
            "DEVMAN_DAGU_CONFIG": "/c.yaml",
            "DEVMAN_DAGU_VERSION": "2.20.1",
            "DEVMAN_BASH": "/bin/bash",
            "DEVMAN_GUARD": "/g.sh",
            "DEVMAN_BIN": "/bin/devman",
        }
    )
    assert paths.base_src.name == "base.yaml"
    assert paths.base_src.parent.name == "devman"
    assert paths.library == Path("/lib")
    assert paths.base_out == Path("/s/base.yaml")
    assert paths.dags == Path("/s/dags")
    assert paths.runs == Path("/s/runs")
    assert paths.events == Path("/s/events.jsonl")
    assert paths.compile_json == Path("/s/compile.json")
    assert paths.lock == Path("/s/compile.lock")
    assert paths.projects_toml == Path("/o/projects.toml")
    assert paths.workflows == Path("/o/workflows")
    assert paths.dagu_config == Path("/c.yaml")
    assert paths.dagu_version == "2.20.1"
    assert (paths.bash, paths.guard, paths.bin) == ("/bin/bash", "/g.sh", "/bin/devman")
