"""
Structured progress of a research run, for the chat's research plan card.

`build_progress` is pure: it turns the plan, the agent's stored events and the visited URLs into one JSON-ready snapshot.
Step state and time come from the section start and complete events the agent already stores (with their timestamps).
"""
import math
from typing import Any, Dict, List, Optional

from .constants import (
    EVENT_FAILURE_MARKER,
    EVENT_SECTION_COMPLETE_SUFFIX,
    EVENT_SECTION_PREFIX,
    EVENT_SECTION_START_PREFIX,
    PROGRESS_PHASES,
    SECTION_TAG_FORMAT,
)


def _section_markers(history: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
    """
    A section's state and attempt time, read from its events in order: a start event means running (clearing an earlier
    failure, so a retried step shows running again), a failure event means failed, a complete event means done for good.
    The duration is from the last start before the complete event, so a step retried after a failure or a restart counts
    only the attempt that finished.
    """
    tag = SECTION_TAG_FORMAT.format(index)
    start_text = f"{tag}{EVENT_SECTION_START_PREFIX}{index}"
    complete_text = f"{EVENT_SECTION_PREFIX}{index}{EVENT_SECTION_COMPLETE_SUFFIX}"
    failed_prefixes = (f"{tag}{EVENT_FAILURE_MARKER}", f"{EVENT_FAILURE_MARKER} {EVENT_SECTION_PREFIX}{index} ")
    state, started, completed = "pending", None, None
    for m in history:
        if m.get("role") != "event" or state == "done":
            continue
        content = m.get("content") or ""
        if content == start_text:
            state, started = "running", m.get("timestamp")
        elif content == complete_text:
            state, completed = "done", m.get("timestamp")
        elif content.startswith(failed_prefixes):
            state = "failed"
    return {"state": state, "started": started, "completed": completed}


def _duration_ms(started: Optional[float], completed: Optional[float]) -> Optional[int]:
    if started is None or completed is None:
        return None
    try:
        seconds = float(completed) - float(started)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds):
        return None
    return max(0, int(round(seconds * 1000)))


def build_progress(
    plan: Optional[Dict[str, Any]],
    history: List[Dict[str, Any]],
    visited_urls: Optional[List[Any]],
    phase: str,
) -> Dict[str, Any]:
    """
    The snapshot: `{"title", "phase", "steps": [{"index", "heading", "state", "duration_ms"}], "steps_done", "steps_total",
    "pages_read"}`. A step is `done` once its complete event exists (with a duration from the last start to the complete event), `failed` when the
    latest event about it is a failure, `running` when it started (again) after that, else `pending`. A missing or malformed plan
    gives no steps; events for sections outside the plan are ignored.
    """
    if phase not in PROGRESS_PHASES:
        raise ValueError(f"unknown research phase: {phase!r}")
    sections = plan.get("sections") if isinstance(plan, dict) else None
    sections = sections if isinstance(sections, list) else []
    steps = []
    for index, section in enumerate(sections):
        markers = _section_markers(history, index)
        state = markers["state"]
        heading = section.get("heading") if isinstance(section, dict) else None
        steps.append({
            "index": index,
            "heading": heading if isinstance(heading, str) else "",
            "state": state,
            "duration_ms": _duration_ms(markers["started"], markers["completed"]) if state == "done" else None,
        })
    return {
        "title": plan.get("title", "") if isinstance(plan, dict) and isinstance(plan.get("title"), str) else "",
        "phase": phase,
        "steps": steps,
        "steps_done": sum(1 for s in steps if s["state"] == "done"),
        "steps_total": len(steps),
        "pages_read": len(visited_urls) if isinstance(visited_urls, list) else 0,
    }
