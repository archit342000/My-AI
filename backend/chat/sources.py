"""
Numbered sources for a chat's answers.

Web pages and file reads that tools return are numbered per chat (`[[1]]`, `[[2]]`, ...). The model is shown the numbers with
the tool result and cites them as `[[n]]`; the sources an answer cited are stored with it and sent to the client.
"""
import re
from typing import Any, Dict, List, Optional

MARKER_RE = re.compile(r"\[\[(\d+)\]\]")  # one number per marker: [[1]][[2]], not [[1, 2]]
SOURCE_REGISTRY_ANCHOR = "chat:{}"  # parent_message_id of the stored registry: never a message id, so it is not served on a message
KINDS = ("web", "file")
MAX_TITLE_CHARS = 200
_WHITESPACE_RE = re.compile(r"[\s\x00-\x1f\x7f]+")


def clean_title(title: Optional[str], fallback: str) -> str:
    """A one-line title: control characters and runs of whitespace collapse to one space (a title cannot forge
    extra `[[n]]` lines in the block shown to the model) and long titles are cut."""
    text = _WHITESPACE_RE.sub(" ", str(title or "")).strip()
    return (text or fallback)[:MAX_TITLE_CHARS]


class SourceRegistry:
    """The numbered sources of one chat. Numbers start at 1, never change and continue across turns."""

    def __init__(self, sources: Optional[List[Dict[str, Any]]] = None):
        self._sources: List[Dict[str, Any]] = []
        self._by_key: Dict[tuple, int] = {}
        for s in sources or []:
            self._load(s)

    def _load(self, s: Any) -> None:
        if (not isinstance(s, dict) or not isinstance(s.get("n"), int) or isinstance(s.get("n"), bool) or s["n"] < 1
                or s.get("kind") not in KINDS or not isinstance(s.get("locator"), str)):
            return  # a malformed stored entry is dropped rather than breaking the turn
        entry = {"n": s["n"], "kind": s["kind"], "title": clean_title(s.get("title"), s["locator"]),
                 "locator": s["locator"], "detail": s.get("detail") if isinstance(s.get("detail"), str) else None}
        self._sources.append(entry)
        self._by_key[(entry["kind"], entry["locator"], entry["detail"])] = entry["n"]

    @classmethod
    def from_list(cls, items: Any) -> "SourceRegistry":
        return cls(items if isinstance(items, list) else [])

    def to_list(self) -> List[Dict[str, Any]]:
        return [dict(s) for s in self._sources]

    def add(self, kind: str, title: Optional[str], locator: str, detail: Optional[str] = None) -> int:
        """The number of the source, adding it when it is new (the same kind, address or path and lines keeps its number)."""
        if kind not in KINDS:
            raise ValueError(f"unknown source kind: {kind!r}")
        key = (kind, locator, detail)
        if key in self._by_key:
            return self._by_key[key]
        n = max((s["n"] for s in self._sources), default=0) + 1
        self._load({"n": n, "kind": kind, "title": title, "locator": locator, "detail": detail})
        return n

    def get(self, n: int) -> Optional[Dict[str, Any]]:
        return next((dict(s) for s in self._sources if s["n"] == n), None)

    def cited(self, text: str) -> List[Dict[str, Any]]:
        """The sources whose `[[n]]` marker appears in `text`, in number order; markers for unknown numbers are ignored."""
        numbers = {int(m) for m in MARKER_RE.findall(text or "")}
        return [dict(s) for s in sorted(self._sources, key=lambda s: s["n"]) if s["n"] in numbers]

    def __len__(self) -> int:
        return len(self._sources)


def format_sources_block(entries: List[Dict[str, Any]]) -> str:
    """The text appended to a tool result so the model sees the numbers: `Sources:` then one `[[n]] title - locator` line each."""
    lines = []
    for e in entries:
        where = e["locator"] + (f" ({e['detail']})" if e.get("detail") else "")
        title = e.get("title") or e["locator"]
        lines.append(f"[[{e['n']}]] {title} - {where}" if title != e["locator"] else f"[[{e['n']}]] {where}")
    return "Sources:\n" + "\n".join(lines)
