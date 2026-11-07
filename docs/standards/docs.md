# Documentation standards

## Where things live

| What | Where |
|------|-------|
| How to run the project | root `README.md` |
| Rules every agent must follow | `AGENTS.md` (short) |
| System overview and boundaries | `docs/architecture.md` |
| Cross-cutting rules | `docs/standards/*.md` |
| Known traps | `docs/pitfalls.md` |
| What a component does and its local constraints | that component's `README.md` |
| What each function does | docstrings in the code |
| Release history | generated changelog (see below); old history in `docs/archive/` |

Do not repeat information. If a fact belongs in a standards file, link to it from the README instead of copying it.

## Component README template

Keep it to roughly 20-40 lines.

```markdown
# <directory>
**Role:** One sentence on what this directory is responsible for.

## Layout
Only list entries that are not obvious from their names.

## Context
- **Depends on:** key internal/external dependencies.
- **Flow:** how data or control moves through it.

## Conventions
Local patterns and constraints. Test commands are in `docs/standards/testing.md`.
```

Do not maintain tables of files and symbols by hand. They go stale. Put that information in docstrings.

## Keeping docs accurate

- Update the README when a component's role, dependencies, or constraints change. Adding or renaming a file rarely needs a README edit.
- If code and a README disagree, trust the code and fix the README in the same change.
- If a change would contradict a documented rule, ask the owner before proceeding.

## Changelog

New entries are generated from commit messages with `scripts/changelog.py`
(conventional prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`).
Release history through v4.10.0 is archived in `docs/archive/changelog-through-v4.10.0.md`.

## Size budget

`AGENTS.md` stays under 80 lines, each file in `docs/` under 200 lines, and each component README under 60 lines.
`backend/tests/test_docs.py` enforces this.
