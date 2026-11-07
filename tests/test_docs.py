"""Documentation guardrails: size budgets, agent-guide stubs, and dead references."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"venv", "node_modules", ".git", "scratch", "reports", "secrets", "__pycache__"}

AGENTS_MAX_LINES = 80
DOCS_MAX_LINES = 200
README_MAX_LINES = 100

_TABLE_REF = re.compile(r"^\|\s*`([^`|]+)`\s*\|")
_BACKTICK_PATH = re.compile(r"`((?:docs/|scripts/|backend/|tests/)[\w./-]+|(?:AGENTS|CLAUDE|GEMINI|README)\.md)`")


def _readmes():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if "README.md" in filenames:
            yield Path(dirpath) / "README.md"


def _lines(path):
    return len(path.read_text(encoding="utf-8").splitlines())


def _looks_like_path(ref):
    return " " not in ref and not any(c in ref for c in "*<>{}()") and (ref.endswith("/") or "." in Path(ref).name)


def test_agents_md_within_budget():
    assert _lines(ROOT / "AGENTS.md") <= AGENTS_MAX_LINES


def test_docs_files_within_budget():
    for path in (ROOT / "docs").rglob("*.md"):
        if "archive" in path.parts:
            continue
        assert _lines(path) <= DOCS_MAX_LINES, f"{path.relative_to(ROOT)} is over {DOCS_MAX_LINES} lines"


def test_component_readmes_within_budget():
    for path in _readmes():
        assert _lines(path) <= README_MAX_LINES, f"{path.relative_to(ROOT)} is over {README_MAX_LINES} lines"


def test_tool_specific_guides_point_to_agents_md():
    for name in ("CLAUDE.md", "GEMINI.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "AGENTS.md" in text, f"{name} must point to AGENTS.md"
        assert _lines(ROOT / name) <= 20, f"{name} must stay a short stub"


def test_references_in_agent_guides_and_docs_resolve():
    files = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "GEMINI.md"]
    files += [p for p in (ROOT / "docs").rglob("*.md") if "archive" not in p.parts]
    for path in files:
        for ref in _BACKTICK_PATH.findall(path.read_text(encoding="utf-8")):
            if not _looks_like_path(ref):
                continue
            assert (ROOT / ref).exists() or (path.parent / ref).exists(), f"{path.relative_to(ROOT)} references missing {ref}"


def test_readme_table_file_references_exist():
    for path in _readmes():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _TABLE_REF.match(line)
            if not match:
                continue
            ref = match.group(1)
            if not _looks_like_path(ref):
                continue
            assert (path.parent / ref).exists() or (ROOT / ref).exists(), f"{path.relative_to(ROOT)} lists missing {ref}"
