import pytest

from backend.tools.agents.research_agent.constants import (
    EVENT_FAILURE_MARKER, EVENT_SECTION_COMPLETE_SUFFIX, EVENT_SECTION_PREFIX, EVENT_SECTION_START_PREFIX, SECTION_TAG_FORMAT,
)
from backend.tools.agents.research_agent.progress import build_progress

PLAN = {"title": "Plan", "sections": [{"heading": "One"}, {"heading": "Two"}, {"heading": "Three"}]}


def start(i, ts):
    return {"role": "event", "content": f"{SECTION_TAG_FORMAT.format(i)}{EVENT_SECTION_START_PREFIX}{i}", "timestamp": ts}


def complete(i, ts):
    return {"role": "event", "content": f"{EVENT_SECTION_PREFIX}{i}{EVENT_SECTION_COMPLETE_SUFFIX}", "timestamp": ts}


def states(snapshot):
    return [s["state"] for s in snapshot["steps"]]


def test_the_markers_match_the_texts_the_agent_stores():
    assert SECTION_TAG_FORMAT.format(3) == "[Section 3] "
    assert EVENT_FAILURE_MARKER == "❌"


def test_no_plan_has_no_steps():
    snap = build_progress(None, [], None, "scouting")
    assert snap == {"title": "", "phase": "scouting", "steps": [], "steps_done": 0, "steps_total": 0, "pages_read": 0}
    assert build_progress({"sections": "bad"}, [], [], "planning")["steps"] == []


def test_a_plan_awaiting_approval_has_pending_steps():
    snap = build_progress(PLAN, [], [], "awaiting_approval")
    assert snap["title"] == "Plan" and states(snap) == ["pending"] * 3 and snap["steps_total"] == 3 and snap["steps_done"] == 0
    assert [s["heading"] for s in snap["steps"]] == ["One", "Two", "Three"]
    assert all(s["duration_ms"] is None for s in snap["steps"])


def test_a_started_step_is_running():
    snap = build_progress(PLAN, [start(0, 10.0)], [], "executing")
    assert states(snap) == ["running", "pending", "pending"]


def test_finished_steps_have_durations_from_the_event_timestamps():
    history = [start(0, 100.0), complete(0, 100.1), start(1, 101.0), complete(1, 139.0), start(2, 140.0)]
    snap = build_progress(PLAN, history, ["a", "b", "c", "d"], "executing")
    assert states(snap) == ["done", "done", "running"]
    assert [s["duration_ms"] for s in snap["steps"]] == [100, 38000, None]
    assert snap["steps_done"] == 2 and snap["pages_read"] == 4


@pytest.mark.parametrize("failure", [
    "[Section 1] ❌ FileSystem update failed for section 1: boom",
    "❌ Section 1 failed: boom. Research halted.",
    "❌ Section 1 failed repeatedly. Research halted to prevent incomplete report.",
])
def test_a_failure_event_marks_an_unfinished_step_failed(failure):
    history = [start(0, 1.0), complete(0, 2.0), start(1, 3.0), {"role": "event", "content": failure, "timestamp": 4.0}]
    snap = build_progress(PLAN, history, [], "failed")
    assert states(snap) == ["done", "failed", "pending"] and snap["steps"][1]["duration_ms"] is None


def test_a_step_that_completed_after_a_failure_is_done():
    history = [start(0, 1.0), {"role": "event", "content": "[Section 0] ❌ x", "timestamp": 2.0}, complete(0, 3.0)]
    assert states(build_progress(PLAN, history, [], "executing"))[0] == "done"


def test_all_done():
    history = [e for i in range(3) for e in (start(i, i * 10.0), complete(i, i * 10.0 + 5))]
    snap = build_progress(PLAN, history, [], "done")
    assert states(snap) == ["done"] * 3 and snap["steps_done"] == 3 and snap["phase"] == "done"


def test_events_outside_the_plan_and_non_events_are_ignored():
    history = [start(7, 1.0), complete(7, 2.0), {"role": "assistant", "content": "Section 0 complete.", "timestamp": 3.0}, start(0, 4.0)]
    assert states(build_progress(PLAN, history, [], "executing")) == ["running", "pending", "pending"]


def test_the_last_start_is_used_so_a_restarted_or_retried_attempt_counts_only_itself():
    history = [start(0, 10.0), start(0, 50.0), complete(0, 60.0)]
    assert build_progress(PLAN, history, [], "executing")["steps"][0]["duration_ms"] == 10000


def test_a_step_started_again_after_a_failure_is_running_not_failed():
    failure = {"role": "event", "content": "[Section 0] ❌ x", "timestamp": 2.0}
    assert states(build_progress(PLAN, [start(0, 1.0), failure, start(0, 3.0)], [], "executing"))[0] == "running"
    snap = build_progress(PLAN, [start(0, 1.0), failure, start(0, 3.0), complete(0, 4.5)], [], "executing")
    assert snap["steps"][0]["state"] == "done" and snap["steps"][0]["duration_ms"] == 1500


def test_an_infinite_timestamp_gives_no_duration():
    snap = build_progress(PLAN, [start(0, 1.0), complete(0, float("inf"))], [], "executing")
    assert snap["steps"][0]["state"] == "done" and snap["steps"][0]["duration_ms"] is None


def test_a_bad_timestamp_gives_no_duration_and_pages_must_be_a_list():
    history = [start(0, "x"), complete(0, 5.0)]
    snap = build_progress(PLAN, history, "not a list", "executing")
    assert snap["steps"][0]["state"] == "done" and snap["steps"][0]["duration_ms"] is None and snap["pages_read"] == 0


def test_an_unknown_phase_is_refused():
    with pytest.raises(ValueError):
        build_progress(PLAN, [], [], "sleeping")
