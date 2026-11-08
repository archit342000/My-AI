# backend/tools/catalog
**Role:** Declares every tool the model can call as a `ToolSpec` (name, JSON-schema parameters, implementation path, scopes), grouped by domain.

## Layout
`__init__.py` concatenates each module's `SPECS` into `ALL_TOOL_SPECS`, the list `ToolRegistry` loads.
One module per domain: `time`, `preferences`, `web`, `filesystem`, `document`, `git`, `code`, `research`, `interaction`, `browser_tools`, `clipboard`.

## Context
- **Depends on:** `backend/tools/spec.py` for `ToolSpec`, `ToolType` and `ToolScope`; implementations are referenced by dotted path and imported lazily.
- **Flow:** `ToolRegistry` reads `ALL_TOOL_SPECS`, filters by scope and mode, and sends `to_openai_schema()` to the model.

## Conventions
- Adding a tool: see `docs/tools.md`. A new module must be added to `ALL_TOOL_SPECS`.
- Specs are frozen data; no logic here. Usage text lives in `backend/prompts/templates/directives/`.
- `tests/test_catalog.py` validates spec completeness. Test commands are in `docs/standards/testing.md`.
