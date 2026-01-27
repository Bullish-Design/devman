#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12.0", "pydantic>=2.7.0"]
# ///
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

import typer
from pydantic import BaseModel, Field, ValidationError, field_validator

app = typer.Typer(no_args_is_help=True)


# --- NEW: whitelist/blacklist policy -----------------------------------------
class HeaderPolicy(BaseModel):
    """
    Controls whether a '# <text>' header is considered a valid relative path.

    - `blacklist` rules reject known-non-path headers (shebangs, uv headers, key=value, lists, spaces, etc.).
    - `whitelist` rules enforce a conservative 'POSIX-like relative path' shape.
    """

    whitelist: list[str] = Field(
        default_factory=lambda: [
            # segments of [A-Za-z0-9._-], slash-separated, no surrounding slashes
            r"(?:[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)"
        ]
    )
    blacklist: list[str] = Field(
        default_factory=lambda: [
            r"^!",  # shebang after '#'
            r"^/{1,2}",  # absolute or protocol-like
            r"^[A-Za-z]:[\\/]",  # Windows drive
            r"^///",  # uv-style '/// script' block
            r"\s",  # any whitespace in the candidate
            r"[=\[\]]",  # key=value or list syntax
        ]
    )

    def allowed(self, text: str) -> bool:
        t = text.strip()
        for pat in self.blacklist:
            if re.search(pat, t):
                return False
        return any(re.fullmatch(pat, t) for pat in self.whitelist)


# Provide a sane default policy. You can later expose this via CLI if desired.
DEFAULT_POLICY = HeaderPolicy()
# -----------------------------------------------------------------------------


# (kept) matches the first comment line and captures the candidate body
PATH_LINE = re.compile(r"^\s*#\s*(?P<rel>.+?)\s*$")


def first_line_path(file: Path, policy: HeaderPolicy = DEFAULT_POLICY) -> Optional[Path]:
    """
    Return a normalized, safe relative Path parsed from the first '# ...' line,
    honoring the provided whitelist/blacklist policy.
    """
    try:
        with file.open("r", encoding="utf-8-sig", errors="ignore") as fh:
            line = fh.readline()
    except Exception:
        return None

    m = PATH_LINE.match(line)
    if not m:
        return None

    candidate = m.group("rel").strip().replace("\\", "/")

    # NEW: apply whitelist/blacklist policy to the captured text
    if not policy.allowed(candidate):
        return None

    # Normalize and validate path safety
    rel = Path(candidate)
    if rel.is_absolute():
        return None

    parts = [p for p in rel.parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None

    return Path(*parts)


class CLIArgs(BaseModel):
    src_dir: Path = Field(description="Directory containing input files")
    out_root: Path = Field(description="Root directory where files are written")
    yes: bool = Field(default=False, description="Overwrite without prompting")
    dry_run: bool = Field(default=False, description="Show actions without writing")

    @field_validator("src_dir")
    @classmethod
    def _src_exists(cls, v: Path) -> Path:
        if not v.exists() or not v.is_dir():
            raise ValueError(f"Source directory not found: {v}")
        return v

    @field_validator("out_root")
    @classmethod
    def _normalize_out(cls, v: Path) -> Path:
        return v


class Mapping(BaseModel):
    source: Path
    dest_rel: Path
    dest_abs: Path
    will_overwrite: bool = False
    reason: Optional[str] = None


def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def first_line_path(file: Path) -> Optional[Path]:
    try:
        with file.open("r", encoding="utf-8-sig", errors="ignore") as fh:
            line = fh.readline()
    except Exception:
        return None
    m = PATH_LINE.match(line)
    if not m:
        return None
    rel = Path(m.group("rel").strip().replace("\\", "/"))
    if rel.is_absolute():
        return None
    # Normalize to remove any leading "./"
    return Path(*rel.parts)


def safe_join(out_root: Path, rel: Path) -> Optional[Path]:
    dest = (out_root / rel).resolve()
    try:
        dest.relative_to(out_root.resolve())
        return dest
    except ValueError:
        return None


def build_mapping(args: CLIArgs, src_file: Path) -> Optional[Mapping]:
    rel = first_line_path(src_file)
    if rel is None:
        return None
    dest_abs = safe_join(args.out_root, rel)
    if dest_abs is None:
        return Mapping(source=src_file, dest_rel=rel, dest_abs=args.out_root, reason="Unsafe path")
    will_overwrite = dest_abs.exists()
    return Mapping(source=src_file, dest_rel=rel, dest_abs=dest_abs, will_overwrite=will_overwrite)


def contents_equal(a: Path, b: Path) -> bool:
    try:
        return a.read_bytes() == b.read_bytes()
    except Exception:
        return False


@app.command()
def sync(
    src_dir: Path = typer.Argument(..., help="Folder of files to read"),
    out_root: Path = typer.Argument(..., help='Root output directory (prefix for "# path")'),
    yes: bool = typer.Option(False, "--yes", "-y", help="Overwrite without confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes"),
):
    """
    Read each file in SRC_DIR. If the first line looks like "# some/relative/path",
    write the file to OUT_ROOT/some/relative/path. Prompt before overwriting.
    """
    try:
        args = CLIArgs(src_dir=src_dir, out_root=out_root, yes=yes, dry_run=dry_run)
    except ValidationError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=2)

    mappings: list[Mapping] = []
    for f in iter_files(args.src_dir):
        m = build_mapping(args, f)
        if m is None:
            typer.secho(f"[skip] {f} (no '# path' on first line)", fg=typer.colors.YELLOW)
            continue
        if m.reason:
            typer.secho(f"[warn] {f} -> {m.dest_rel} ({m.reason})", fg=typer.colors.RED)
            continue
        mappings.append(m)

    if not mappings:
        typer.secho("No valid files to process.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    for m in mappings:
        dest = m.dest_abs
        dest.parent.mkdir(parents=True, exist_ok=True)
        action = "create"
        if dest.exists():
            if contents_equal(m.source, dest):
                typer.secho(f"[same] {m.source} -> {m.dest_rel} (no change)", fg=typer.colors.BLUE)
                continue
            action = "overwrite"
            if not args.yes:
                typer.secho(f"[conflict] {dest} exists.", fg=typer.colors.RED)
                if not typer.confirm("  Overwrite?", default=False):
                    typer.secho(f"[skip] {m.source}", fg=typer.colors.YELLOW)
                    continue

        if args.dry_run:
            typer.secho(f"[dry-run] {action}: {m.source} -> {m.dest_rel}", fg=typer.colors.CYAN)
            continue

        try:
            dest.write_bytes(m.source.read_bytes())
            fg = typer.colors.GREEN if action == "create" else typer.colors.MAGENTA
            typer.secho(f"[{action}] {m.source} -> {m.dest_rel}", fg=fg)
        except Exception as ex:
            typer.secho(f"[error] {m.source}: {ex}", fg=typer.colors.RED)

    typer.secho("Done.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
