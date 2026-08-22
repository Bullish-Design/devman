# Archive — the old `.devman/` layout

Two samples of the `.devman/` directory as devman v0 used it, kept from
`templates/` before that tree was deleted.

**This is a reference sample, not a design.** Nothing here is part of the
charter. It exists so investigation **D6** has something concrete to look at.

## What D6 needs from it

`CONCEPT.md` §15.2 says registration must detect a `.devman/` it does not
recognize and report it, never silently adopt it. D6 asks for the minimum test
that tells old from new. These files are what "old" looks like:

| Marker | Old (here) | New (charter) |
|---|---|---|
| `devman.toml` | present — the workspace descriptor | **absent**; the declaration is in `devenv.nix` |
| `workspace.tmuxp.yaml` | present | absent |
| `nvim/`, `sessions/` | present — editor state | absent |
| `interaction.md` | present | absent |
| `workflows/` | absent | **present** — Dagu YAML |
| `.runs/` | absent | present, ignored |

The cheapest discriminator is likely the presence of `devman.toml` or the
absence of `workflows/`. Confirm that against real repos rather than against
these two samples — a repo may carry a shape neither column describes.

## Provenance

```
templates/workspace-min/.devman/               → workspace-min-devman/
templates/workspace-nixos-collection/.devman/  → workspace-nixos-collection-devman/
```

Both are recoverable from git history at the commit that deleted `templates/`.
