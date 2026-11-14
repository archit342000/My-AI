from backend.tools.agents.research_agent.constants import (
    EVENT_SCOUT_START, EVENT_SCOUT_FINALIZED,
    EVENT_PLAN_START, EVENT_PLAN_APPROVED,
    EVENT_ALL_SECTIONS_DONE,
    EVENT_SECTION_PREFIX, EVENT_SECTION_START_PREFIX, EVENT_SECTION_COMPLETE_SUFFIX,
    EVENT_INITIAL_SEARCHES_PREFIX, EVENT_INITIAL_SEARCHES_DONE,
    EVENT_REFLECTION_START, EVENT_REFLECTION_DONE,
    EVENT_GAP_SEARCHES_START, EVENT_GAP_SEARCHES_IN_PROGRESS, EVENT_GAP_SEARCHES_DONE,
    EVENT_TRIAGE_START, EVENT_TRIAGE_DONE,
    EVENT_WRITER_START, EVENT_WRITER_DONE,
    EVENT_SUMMARY_START, EVENT_SUMMARY_DONE,
    EVENT_SYNTHESIS_START, EVENT_SYNTHESIS_POST,
    EVENT_RESEARCH_COMPLETE,
    PLAN_APPROVAL_SIGNAL,
)


def test_all_event_constants_are_strings():
    """Every exported constant must be a non-empty string."""
    constants = [
        EVENT_SCOUT_START, EVENT_SCOUT_FINALIZED,
        EVENT_PLAN_START, EVENT_PLAN_APPROVED,
        EVENT_ALL_SECTIONS_DONE,
        EVENT_SECTION_PREFIX, EVENT_SECTION_START_PREFIX, EVENT_SECTION_COMPLETE_SUFFIX,
        EVENT_INITIAL_SEARCHES_PREFIX, EVENT_INITIAL_SEARCHES_DONE,
        EVENT_REFLECTION_START, EVENT_REFLECTION_DONE,
        EVENT_GAP_SEARCHES_START, EVENT_GAP_SEARCHES_IN_PROGRESS, EVENT_GAP_SEARCHES_DONE,
        EVENT_TRIAGE_START, EVENT_TRIAGE_DONE,
        EVENT_WRITER_START, EVENT_WRITER_DONE,
        EVENT_SUMMARY_START, EVENT_SUMMARY_DONE,
        EVENT_SYNTHESIS_START, EVENT_SYNTHESIS_POST,
        EVENT_RESEARCH_COMPLETE,
        PLAN_APPROVAL_SIGNAL,
    ]
    for const in constants:
        assert isinstance(const, str), f"Expected str, got {type(const)}: {const!r}"
        assert len(const.strip()) > 0, f"Constant is empty: {const!r}"


def test_section_prefix_format():
    """Section prefix must allow numeric index concatenation like 'Section 0'."""
    assert EVENT_SECTION_PREFIX.endswith(" ") or EVENT_SECTION_PREFIX[-1].isdigit() is False
    # Should form a valid section marker when combined with an index
    marker = f"{EVENT_SECTION_PREFIX}0{EVENT_SECTION_COMPLETE_SUFFIX}"
    assert "0" in marker
    assert marker.startswith(EVENT_SECTION_PREFIX)


def test_plan_approval_signal_is_user_friendly():
    """The approval signal must be human-readable for the MCQ UI."""
    assert PLAN_APPROVAL_SIGNAL
    # Should be a phrase, not a code token
    assert " " in PLAN_APPROVAL_SIGNAL


def test_event_phase_pairs_complete():
    """Every phase that has a START event should also have a DONE event."""
    assert EVENT_REFLECTION_START and EVENT_REFLECTION_DONE
    assert EVENT_GAP_SEARCHES_START and EVENT_GAP_SEARCHES_DONE
    assert EVENT_TRIAGE_START and EVENT_TRIAGE_DONE
    assert EVENT_WRITER_START and EVENT_WRITER_DONE
    assert EVENT_SUMMARY_START and EVENT_SUMMARY_DONE


def test_progress_markers_and_phases():
    from backend.tools.agents.research_agent.constants import SECTION_TAG_FORMAT, EVENT_FAILURE_MARKER, PROGRESS_PHASES
    assert SECTION_TAG_FORMAT.format(2) == "[Section 2] "
    assert EVENT_FAILURE_MARKER == "\u274c"
    assert PROGRESS_PHASES == ("scouting", "planning", "awaiting_approval", "executing", "synthesizing", "done", "failed")
