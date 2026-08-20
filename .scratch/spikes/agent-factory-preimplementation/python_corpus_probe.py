"""Probe Python syntax, trivia, ownership, and UTF-8 byte preservation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tree_sitter_python
from pydantree_sitter import Language

Decision = Literal["preserve", "own", "collate", "reject"]

PYTHON = Language.load(tree_sitter_python.language())


@dataclass(frozen=True)
class CorpusCase:
    name: str
    categories: tuple[str, ...]
    source: str
    decision: Decision
    owner: str
    parse_clean: bool = True
    reason: str = ""


def corpus() -> list[CorpusCase]:
    """Return the frozen categorized corpus."""

    return [
        CorpusCase(
            "module-preamble-and-missing-final-newline",
            (
                "shebang",
                "encoding-cookie",
                "module-docstring",
                "future-import",
                "__all__",
                "missing-final-newline",
            ),
            '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"""módulo"""\nfrom __future__ import annotations\n\n__all__ = ["café"]\ncafé = 1',
            "preserve",
            "source-authored module preamble",
        ),
        CorpusCase(
            "mixed-newlines-and-trailing-space",
            ("blank-lines", "mixed-newlines", "trailing-whitespace"),
            "x = 1  \r\n\r\ny = 2\n",
            "preserve",
            "source-authored layout",
        ),
        CorpusCase(
            "comments-and-directives",
            (
                "comments-before-between-inside-after",
                "type-comment",
                "noqa",
                "formatter",
                "coverage",
                "type-checker",
            ),
            "# before\n# fmt: off\nx = []  # type: list[int]\n# fmt: on\n\n# between\ndef f() -> int:  # noqa: D103\n    # inside\n    return 1  # pragma: no cover\n# after\n# type: ignore\n",
            "preserve",
            "source-authored trivia",
        ),
        CorpusCase(
            "decorators-and-signatures",
            (
                "decorators",
                "stacked-decorators",
                "multiline-signature",
                "positional-only",
                "keyword-only",
                "annotations",
                "defaults",
            ),
            '@outer\n@inner(flag=True)\ndef f(\n    left: int,\n    /,\n    right: str = "x",\n    *,\n    enabled: bool = True,\n) -> tuple[int, str]:\n    return left, right\n',
            "own",
            "function declaration record",
        ),
        CorpusCase(
            "overloads-and-generics",
            ("overloads", "generics", "newest-syntax"),
            "from typing import overload\n\ntype Pair[T] = tuple[T, T]\n\n@overload\ndef duplicate(value: int) -> Pair[int]: ...\n\n@overload\ndef duplicate(value: str) -> Pair[str]: ...\n\ndef duplicate[T](value: T) -> Pair[T]:\n    return value, value\n",
            "own",
            "declaration records plus collated typing import",
        ),
        CorpusCase(
            "function-kinds",
            ("sync", "async", "generator", "async-generator", "nested", "closure"),
            "def outer(seed: int):\n    def closure(delta: int) -> int:\n        return seed + delta\n    return closure\n\ndef gen():\n    yield 1\n\nasync def coro():\n    return 1\n\nasync def agen():\n    yield 1\n",
            "own",
            "nested declaration hierarchy",
        ),
        CorpusCase(
            "ambiguous-expressions",
            ("lambdas", "comprehensions", "walrus"),
            "transform = lambda value: value + 1\nvalues = [item for item in range(4) if (keep := item % 2)]\n",
            "preserve",
            "enclosing source-owned statement",
            reason="expression ownership is not independently promoted",
        ),
        CorpusCase(
            "class-kinds",
            (
                "classes",
                "nested-classes",
                "dataclasses",
                "enums",
                "protocols",
                "properties",
                "setters",
                "static-method",
                "class-method",
            ),
            'from dataclasses import dataclass\nfrom enum import Enum\nfrom typing import Protocol\n\nclass P(Protocol):\n    def run(self) -> int: ...\n\nclass E(Enum):\n    ONE = 1\n\n@dataclass\nclass Box:\n    value: int\n\n    class Meta:\n        label = "box"\n\n    @property\n    def doubled(self) -> int:\n        return self.value * 2\n\n    @doubled.setter\n    def doubled(self, value: int) -> None:\n        self.value = value // 2\n\n    @staticmethod\n    def empty() -> "Box":\n        return Box(0)\n\n    @classmethod\n    def one(cls) -> "Box":\n        return cls(1)\n',
            "own",
            "class and method declaration records",
        ),
        CorpusCase(
            "advanced-classes",
            ("metaclass", "descriptor", "decorated-definition"),
            "class Meta(type):\n    pass\n\nclass Descriptor:\n    def __get__(self, instance, owner):\n        return 1\n\ndef decorate(cls):\n    return cls\n\n@decorate\nclass Subject(metaclass=Meta):\n    field = Descriptor()\n",
            "own",
            "class declaration records",
        ),
        CorpusCase(
            "conditional-definitions",
            (
                "conditional-definition",
                "platform-guard",
                "version-guard",
                "TYPE_CHECKING",
                "repeated-symbol",
            ),
            'import sys\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from pkg import Hint\n\nif sys.version_info >= (3, 13):\n    def selected():\n        return "new"\nelse:\n    def selected():\n        return "old"\n',
            "preserve",
            "source-authored conditional block",
            reason="repeated conditional names are ambiguous durable identities",
        ),
        CorpusCase(
            "try-import",
            ("try-import", "optional-import", "import-side-effect"),
            "try:\n    import fast_backend as backend\nexcept ImportError:\n    import slow_backend as backend\n",
            "reject",
            "source-authored try statement",
            reason="import choice and order are executable semantics",
        ),
        CorpusCase(
            "structured-imports",
            ("aliases", "relative-levels", "parenthesized-imports"),
            "from ..pkg import (\n    first as one,\n    second,\n)\n",
            "collate",
            "module import section",
            reason="preserve ordering and spelling; no automatic deduplication",
        ),
        CorpusCase(
            "unsafe-import-forms",
            (
                "star-import",
                "semicolon-statements",
                "dynamic-import",
                "import-side-effect",
            ),
            "from plugin import *\nimport alpha; import beta\nmodule = __import__(name)\nimport registers_handlers\n",
            "reject",
            "source-authored module statements",
            reason="binding and order effects cannot be safely normalized",
        ),
        CorpusCase(
            "modern-expressions",
            ("pattern-matching", "exception-groups", "f-strings", "walrus"),
            'def describe(value):\n    match value:\n        case {"name": name} if (size := len(name)):\n            return f"{name=}:{size}"\n        case _:\n            return "none"\n\ntry:\n    raise ExceptionGroup("many", [ValueError()])\nexcept* ValueError as group:\n    handled = group\n',
            "own",
            "function record and source-authored executable statement",
        ),
        CorpusCase(
            "non-ascii-byte-spans",
            (
                "utf8-byte-offset",
                "non-ascii-identifier",
                "non-ascii-comment",
                "non-ascii-string",
            ),
            '# π before\ndef café(naïve: str = "☕") -> str:\n    return f"olá {naïve}"\n',
            "own",
            "function declaration record plus opaque trivia",
        ),
        CorpusCase(
            "invalid-edited-buffer",
            ("syntactically-invalid", "actively-edited-buffer"),
            "def unfinished(\n    value: int,\n",
            "reject",
            "edited source buffer",
            parse_clean=False,
            reason="ERROR or missing nodes must stop extraction before mutation",
        ),
    ]


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _reassemble_with_gaps(source: bytes, root) -> tuple[bytes, int]:
    """Reassemble top-level concrete nodes plus every opaque byte gap."""

    chunks: list[bytes] = []
    cursor = 0
    for child in root.children:
        if child.start_byte < cursor:
            raise ValueError(f"overlapping top-level span at {child.type}")
        chunks.append(source[cursor : child.start_byte])
        chunks.append(source[child.start_byte : child.end_byte])
        cursor = child.end_byte
    chunks.append(source[cursor:])
    return b"".join(chunks), len(chunks)


def evaluate(case: CorpusCase) -> dict[str, object]:
    before = case.source.encode("utf-8")
    tree = PYTHON.parse(case.source)
    nodes = list(_walk(tree.root_node))
    errors = [
        {
            "type": node.type,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        }
        for node in nodes
        if node.type == "ERROR" or node.is_missing
    ]
    clean = not errors

    span_failures: list[str] = []
    non_ascii_span_count = 0
    for node in nodes:
        if not (0 <= node.start_byte <= node.end_byte <= len(before)):
            span_failures.append(f"{node.type}:out-of-bounds")
            continue
        fragment = before[node.start_byte : node.end_byte]
        try:
            text = fragment.decode("utf-8")
        except UnicodeDecodeError:
            span_failures.append(f"{node.type}:split-utf8")
            continue
        if any(ord(character) > 127 for character in text):
            non_ascii_span_count += 1

    assembly_attempted = clean and case.decision != "reject"
    if assembly_attempted:
        after, segment_count = _reassemble_with_gaps(before, tree.root_node)
    else:
        after, segment_count = before, 0
    accepted = clean == case.parse_clean and not span_failures
    if not case.parse_clean:
        accepted = accepted and bool(errors) and not assembly_attempted

    return {
        "name": case.name,
        "categories": case.categories,
        "decision": case.decision,
        "owner": case.owner,
        "reason": case.reason,
        "expected_parse_clean": case.parse_clean,
        "actual_parse_clean": clean,
        "parse_errors": errors,
        "span_failures": span_failures,
        "non_ascii_span_count": non_ascii_span_count,
        "input_bytes": len(before),
        "input_hash": _hash(before),
        "output_hash": _hash(after),
        "bytes_preserved": before == after,
        "assembly_attempted": assembly_attempted,
        "segment_count": segment_count,
        "mutation_attempted": False,
        "passed": accepted and before == after,
    }


def run_suite(artifacts: Path | None = None) -> dict[str, object]:
    rows = [evaluate(case) for case in corpus()]
    decisions = {
        decision: sum(row["decision"] == decision for row in rows)
        for decision in ("preserve", "own", "collate", "reject")
    }
    categories = sorted({category for case in corpus() for category in case.categories})
    results: dict[str, object] = {
        "cases": rows,
        "metrics": {
            "case_count": len(rows),
            "category_count": len(categories),
            "decisions": decisions,
            "byte_identity_failures": sum(not row["bytes_preserved"] for row in rows),
            "parse_classification_failures": sum(
                row["expected_parse_clean"] != row["actual_parse_clean"] for row in rows
            ),
            "span_failures": sum(bool(row["span_failures"]) for row in rows),
            "pre_mutation_rejections": sum(
                row["decision"] == "reject" and not row["mutation_attempted"]
                for row in rows
            ),
        },
        "categories": categories,
        "suite_passed": all(row["passed"] for row in rows),
    }
    if artifacts is not None:
        if artifacts.exists() and any(artifacts.iterdir()):
            raise ValueError(f"artifact directory is not fresh: {artifacts}")
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "results.json").write_text(
            json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (artifacts / "environment.json").write_text(
            json.dumps(
                {
                    "command": " ".join(sys.argv),
                    "python": platform.python_version(),
                    "parser": "tree-sitter-python through pydantree Language",
                    "encoding": "UTF-8 bytes",
                    "network": "not used",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    try:
        results = run_suite(args.artifacts)
    except Exception as error:
        args.artifacts.mkdir(parents=True, exist_ok=True)
        (args.artifacts / "failure.txt").write_text(
            f"status=failed\nerror_type={type(error).__name__}\nerror={error}\n",
            encoding="utf-8",
        )
        raise
    print(json.dumps(results["metrics"], indent=2, sort_keys=True))
    return 0 if results["suite_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
