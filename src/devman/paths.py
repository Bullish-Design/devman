"""Every path and setting devman reads from the environment (PLAN §A.6)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    overlay: Path
    state: Path
    library: Path
    base_src: Path  # packaged base.yaml template
    base_out: Path  # <state>/base.yaml, the template with its tokens filled
    dags: Path
    runs: Path
    tmp: Path
    events: Path
    compile_json: Path
    lock: Path
    dagu_config: Path | None  # DEVMAN_DAGU_CONFIG, None when unset
    dagu_version: str | None
    bash: str | None  # fill the base.yaml tokens; `guard` is the header shell
    guard: str | None
    bin: str | None

    @property
    def projects_toml(self) -> Path:
        return self.overlay / "projects.toml"

    @property
    def workflows(self) -> Path:
        return self.overlay / "workflows"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Paths:
        env = os.environ if env is None else env
        overlay = Path(env.get("DEVMAN_OVERLAY") or "~/.config/devman").expanduser()
        state = Path(env.get("DEVMAN_STATE") or "~/.local/state/devman").expanduser()
        library = Path(env.get("DEVMAN_LIBRARY") or overlay / "library").expanduser()
        config = env.get("DEVMAN_DAGU_CONFIG")
        return cls(
            overlay=overlay,
            state=state,
            library=library,
            base_src=Path(__file__).with_name("base.yaml"),
            base_out=state / "base.yaml",
            dags=state / "dags",
            runs=state / "runs",
            tmp=state / "tmp",
            events=state / "events.jsonl",
            compile_json=state / "compile.json",
            lock=state / "compile.lock",
            dagu_config=Path(config) if config else None,
            dagu_version=env.get("DEVMAN_DAGU_VERSION") or None,
            bash=env.get("DEVMAN_BASH") or None,
            guard=env.get("DEVMAN_GUARD") or None,
            bin=env.get("DEVMAN_BIN") or None,
        )
