# Python syntax, trivia, and ownership support matrix

Date: 2026-08-20

Status: deterministic corpus passed; edit/render mutation corpus remains open

## Decision vocabulary

- **Preserve**: retain exact source bytes as source-authored material; do not
  claim semantic ownership.
- **Own**: a typed declaration record may own meaning, while its accepted
  rendering still must reproduce the full-file canonical bytes.
- **Collate**: assemble a separately owned section without reordering or
  deduplicating unless equivalence is proved.
- **Reject**: stop the attempted ownership/promotion operation before mutation,
  preserve the source, and name the source owner and reason.

## Matrix

| Area | Decision | Owner | Boundary |
| --- | --- | --- | --- |
| Shebang, cookie, module docstring, future import, `__all__` | preserve | module preamble | Exact bytes, including missing final newline |
| Blank lines, mixed newlines, trailing whitespace | preserve | source layout | Ruff canonicalization is a separate explicit transition |
| Comments and tool directives | preserve | adjacent/source trivia | Declaration AST spans do not assign safe semantic ownership |
| Functions, methods, signatures, decorators, generics | own | declaration record | Full syntax validation and exact-file convergence required |
| Classes, protocols, dataclasses, enums, descriptors | own | class/declaration records | Nested ownership must remain hierarchical |
| Lambdas and comprehensions | preserve | enclosing statement | Independent durable identity is ambiguous |
| Conditional/repeated definitions | preserve | conditional block | Automatic identity continuity is unsafe |
| Structured imports | collate | module import section | Preserve spelling and order |
| Optional, star, dynamic, side-effect, semicolon imports | reject | source statement/block | Binding and execution order may change semantics |
| Modern expressions and statements | own/preserve | containing record | Parser-version gate applies |
| Invalid edited buffer | reject | edited source buffer | Any `ERROR` or missing node stops extraction |

## Span finding

Tree-sitter and pydantree offsets are UTF-8 byte offsets. Byte slicing is safe
only against the original encoded buffer; applying those offsets to Python
character indexes corrupts non-ASCII input. The executable corpus walks every
node, validates bounds, decodes each byte slice, and includes non-ASCII source.

AST plus declaration byte spans is sufficient to locate declarations and to
preserve an entire untouched input as opaque bytes. It is not sufficient to
assign comments, blank lines, directives, mixed newline policy, or
semicolon/import collation to semantic records. The implementation needs the
tree-sitter concrete tree plus tokens or explicit trivia/gap records for those
claims. Until that representation exists, those regions remain source-owned.

The passing evidence is
`artifacts/20260820T192930Z-python-corpus-final/results.json`: 16 cases, 69
categories, zero byte-identity, parse-classification, or span failures. The
probe reconstructs every supported file from top-level concrete-node byte spans
and explicit opaque gaps. It does not yet prove edits inside those segments or
semantic regeneration across this full corpus.
