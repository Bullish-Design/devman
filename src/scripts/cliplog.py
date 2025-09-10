#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "pydantic>=2"
# ]
# ///
from __future__ import annotations

import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from pydantic import BaseModel, Field

app = typer.Typer(add_completion=False, no_args_is_help=True)


class ClipEntry(BaseModel):
    """Single clipboard capture."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    text: str
    backend: Optional[str] = None

    def to_log_block(self, timestamp_format: str) -> str:
        ts = self.timestamp.astimezone().strftime(timestamp_format)
        sep = f"\n\n####==== {ts} ====####\n\n"
        block = self.text
        if not block.endswith("\n"):
            block += "\n"
        return sep + block


class ClipLogConfig(BaseModel):
    output: Path
    poll_interval: float = 0.5
    include_initial: bool = True
    timestamp_format: str = "%Y-%m-%d %H:%M:%S%z"
    overwrite: bool = False


def _detect_backend() -> tuple[list[str], str]:
    """Return (command, name) for first available clipboard reader."""
    if shutil.which("wl-paste"):
        return (["wl-paste", "--no-newline"], "wl-paste")
    if shutil.which("xclip"):
        return (["xclip", "-selection", "clipboard", "-out"], "xclip")
    if shutil.which("xsel"):
        return (["xsel", "--clipboard", "--output"], "xsel")
    raise RuntimeError("No clipboard backend found. Install one of: wl-clipboard (wl-paste), xclip, or xsel.")


def _read_clipboard(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        return ""
    except Exception:
        return ""


def _setup_signals(stop_flag: dict):
    def _handler(signum, frame):
        stop_flag["stop"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handler)


@app.command()
def run(
    output: Optional[Path] = typer.Argument(
        None,
        help="Filepath to write the clipboard log. Defaults to ~/Downloads/clipboard_log_YYYYMMDD_HHMMSS.txt",
    ),
    poll_interval: float = typer.Option(0.5, help="Polling interval in seconds."),
    include_initial: bool = typer.Option(True, help="Capture the clipboard value present at start."),
    timestamp_format: str = typer.Option("%Y-%m-%d %H:%M:%S%z", help="Python strftime format for timestamps."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Start with a fresh file instead of appending."),
):
    """
    Watch the clipboard and append every new text copy to OUTPUT,
    separating entries with a timestamped marker.
    """
    # Resolve default output path if none was provided
    if output is None:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        fname = f"clipboard_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        output = downloads / fname

    cfg = ClipLogConfig(
        output=output,
        poll_interval=poll_interval,
        include_initial=include_initial,
        timestamp_format=timestamp_format,
        overwrite=overwrite,
    )

    cmd, backend = _detect_backend()

    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if cfg.overwrite else "a"

    stop = {"stop": False}
    _setup_signals(stop)

    last = None
    initial = _read_clipboard(cmd)
    if cfg.include_initial:
        last = None  # force write if something exists
    else:
        last = initial

    typer.echo(f"[cliplog] backend={backend} → {cfg.output}  (Ctrl+C to stop)")

    with cfg.output.open(mode, encoding="utf-8") as fh:
        try:
            while not stop["stop"]:
                cur = _read_clipboard(cmd)
                if cur and cur != last:
                    entry = ClipEntry(text=cur, backend=backend)
                    fh.write(entry.to_log_block(cfg.timestamp_format))
                    fh.flush()
                    last = cur
                time.sleep(cfg.poll_interval)
        finally:
            typer.echo("[cliplog] stopped.")


if __name__ == "__main__":
    app()
