import sys
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import json
import httpx
import asyncio
from backend.tools.agents.research_agent.agent import ResearchAgent, flow_fn, SectionState
import backend.tools.agents.research_agent.agent as agent_mod
from backend.tools.agents.research_agent.constants import (
    EVENT_INITIAL_SEARCHES_DONE, EVENT_REFLECTION_DONE, 
    EVENT_GAP_SEARCHES_DONE, EVENT_TRIAGE_DONE, 
    EVENT_WRITER_DONE, EVENT_SUMMARY_DONE,
    EVENT_SECTION_PREFIX, EVENT_SECTION_COMPLETE_SUFFIX
)

@pytest.fixture(autouse=True)
def search_limit():
    """The per-user search limit check (the test chats have no owner); allowed unless a test says otherwise."""
    with patch.object(agent_mod, 'check_search_limit', return_value=None) as check:
        yield check


@pytest.fixture
def mock_agent_context():
    agent = MagicMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = 123
    agent.model = "test-model"
    return agent

@pytest.fixture
def research_agent(mock_agent_context):
    with patch.object(agent_mod, 'config') as mock_config:
        mock_config.RESEARCH_MAX_GAPS_PER_SECTION = 3
        mock_config.RESEARCH_MAX_SECTION_STALLS = 2
        mock_config.RESEARCH_SEARCH_RETRIES = 1
        mock_config.RESEARCH_JSON_RETRIES = 2
        mock_config.RESEARCH_MAX_RETRIES = 2
        mock_config.RESEARCH_MAX_TOKENS_AUDIT = 1000
        mock_config.RESEARCH_THINKING_BUDGET_AUDIT_TOKENS = 100
        mock_config.RESEARCH_EXTRACT_MIN_RAW_CONTENT = 10
        mock_config.RESEARCH_SEARCH_TIMEOUT = 10
        
        return ResearchAgent(
            chat_id=mock_agent_context.chat_id,
            parent_message_id=mock_agent_context.parent_message_id,
            enable_thinking=True,
            model=mock_agent_context.model
        )

def test_research_agent_init(research_agent):
    assert research_agent.chat_id == "test_chat"
    assert research_agent.model == "test-model"

def test_parse_section_state_resumption(research_agent):
    state = SectionState(2)
    prefix = "[Section 2] "
    history = [
        {"role": "event", "content": f"{prefix}{EVENT_INITIAL_SEARCHES_DONE}"},
        {"role": "event", "content": f"{prefix}{EVENT_REFLECTION_DONE}"}
    ]
    research_agent._parse_section_state(history, state)
    assert state.has_initial_search is True
    assert state.has_reflection is True

def test_get_assistant_output_for_phase(research_agent):
    history = [
        {"role": "assistant", "content": "Actual Output"},
        {"role": "event", "content": "Phase Completed"}
    ]
    res = research_agent._get_assistant_output_for_phase(history, "Phase Completed")
    assert res["content"] == "Actual Output"

@pytest.mark.anyio
async def test_build_continuous_context_filtering(research_agent):
    plan = {"title": "Topic Title", "sections": [{"heading": "S1", "queries": []}]}
    sections = plan["sections"]
    
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_collections.return_value = []
        msgs = research_agent._build_continuous_context(
            current_idx=0,
            current_section=sections[0],
            plan=plan,
            sections=sections,
            accumulated_summaries_text="Prev Summary",
            section_history=[],
            target_phase="Reflection"
        )
        assert len(msgs) == 2
        assert "Research Executor Agent" in msgs[0]["content"]

@pytest.mark.anyio
async def test_run_json_inference_retry_logic(research_agent):
    """Tests that _run_json_inference retries on failure and succeeds on the second attempt.
    The method now calls _extract_json_from_text as a module-level function (not a method)."""
    agent = MagicMock()

    # Simulate two inference runs: first yields empty, second yields valid JSON
    call_count = 0
    async def mock_gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        yield "chunk"

    agent.run_inference_step.side_effect = mock_gen

    with patch.object(agent_mod, 'config') as mock_config, \
         patch.object(agent_mod, 'db') as mock_db, \
         patch.object(agent_mod, '_extract_json_from_text') as mock_extract:
        mock_config.RESEARCH_MAX_RETRIES = 2
        
        # First attempt: extract returns None (invalid), second: returns valid JSON
        mock_extract.side_effect = [None, {"valid": "json"}]
        mock_db.get_messages.return_value = [{"role": "assistant", "content": "some output"}]
        
        # Patch _emit_event to be a no-op async generator
        async def noop_emit(*args, **kwargs):
            return
            yield  # make it an async generator
        research_agent._emit_event = noop_emit
        
        gen = research_agent._run_json_inference(
            agent=agent,
            messages=[],
            phase_name="test",
            schema={},
            max_tokens=1000,
            thinking_budget=100
        )
        results = []
        async for item in gen:
            results.append(item)
        
        assert agent.run_inference_step.call_count == 2
        # The last result should be the parsed JSON
        assert any(isinstance(r, dict) and r.get("type") == "test_result" for r in results)

@pytest.mark.anyio
async def test_run_executor_sequential_logic(research_agent):
    """Tests that _run_executor skips completed sections and runs pending ones."""
    sections = [{"heading": "S1"}, {"heading": "S2"}]
    plan = {"title": "Test Plan", "sections": sections}
    
    with patch.object(agent_mod, 'db') as mock_db:
        # Section 0 is already complete (event marker present)
        mock_db.get_messages.return_value = [
            {"role": "event", "content": f"{EVENT_SECTION_PREFIX}0{EVENT_SECTION_COMPLETE_SUFFIX}"}
        ]
        mock_db.get_collections.return_value = [{"collection_type": "report_file_system_id", "items": '"fs_123"'}]
        
        # Make _run_single_section an async generator
        async def mock_section(*args, **kwargs):
            return
            yield  # async generator
        research_agent._run_single_section = mock_section
        
        # After one iteration, mark section 1 as complete too to break the loop
        call_idx = [0]
        def get_messages_side_effect(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] >= 2:
                return [
                    {"role": "event", "content": f"{EVENT_SECTION_PREFIX}0{EVENT_SECTION_COMPLETE_SUFFIX}"},
                    {"role": "event", "content": f"{EVENT_SECTION_PREFIX}1{EVENT_SECTION_COMPLETE_SUFFIX}"},
                ]
            return [
                {"role": "event", "content": f"{EVENT_SECTION_PREFIX}0{EVENT_SECTION_COMPLETE_SUFFIX}"}
            ]
        mock_db.get_messages.side_effect = get_messages_side_effect
        mock_db.get_collections.return_value = [
            {"collection_type": "report_file_system_id", "items": '"fs_123"'}
        ]

        # Patch _emit_event
        async def noop_emit(*args, **kwargs):
            yield "event"
        research_agent._emit_event = noop_emit
        
        gen = research_agent._run_executor(plan, MagicMock())
        async for _ in gen: pass

@pytest.mark.anyio
async def test_run_executor_stall_detection(research_agent):
    """Tests that _run_executor detects stalled sections and raises RuntimeError."""
    plan = {"title": "Test Plan", "sections": [{"heading": "S1"}]}
    with patch.object(agent_mod, 'db') as mock_db, \
         patch.object(agent_mod, 'config') as mock_config:
        mock_config.RESEARCH_MAX_SECTION_STALLS = 2
        
        # Section 0 never completes (always pending)
        mock_db.get_messages.return_value = []
        mock_db.get_collections.return_value = [
            {"collection_type": "report_file_system_id", "items": '"fs_123"'}
        ]

        # _run_single_section does nothing (doesn't complete the section)
        async def mock_section(*args, **kwargs):
            return
            yield  # async generator
        research_agent._run_single_section = mock_section
        
        # Patch _emit_event
        async def noop_emit(*args, **kwargs):
            yield "event"
        research_agent._emit_event = noop_emit
        
        with pytest.raises(RuntimeError, match="stalled repeatedly"):
            gen = research_agent._run_executor(plan, MagicMock())
            async for _ in gen: pass

@pytest.mark.anyio
async def test_execute_internal_searches_all_fail(research_agent):
    """Tests that _execute_internal_searches raises RuntimeError when ALL queries fail
    and no content was gathered."""
    with patch.object(agent_mod, '_execute_mcp_tool') as mock_tool, \
         patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_collections.return_value = []
        
        # All searches fail
        mock_tool.side_effect = Exception("Fail")
        
        # Patch the tavily_client connect
        with patch('backend.mcp_client.tavily_client', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.connect = AsyncMock()
            
            with pytest.raises(RuntimeError, match="All searches failed"):
                await research_agent._execute_internal_searches([{"query": "q1"}])

@pytest.mark.anyio
async def test_execute_internal_searches_partial_success(research_agent):
    """Tests that _execute_internal_searches succeeds when at least one query returns data,
    even if others fail."""
    with patch.object(agent_mod, '_execute_mcp_tool') as mock_tool, \
         patch.object(agent_mod, 'db') as mock_db, \
         patch.object(agent_mod, 'config') as mock_config:
        mock_config.RESEARCH_SELECT_TOP_URLS_COUNT = 5
        mock_config.RESEARCH_EXTRACT_MIN_RAW_CONTENT = 10
        mock_config.RESEARCH_TAVILY_MAX_RESULTS_INITIAL = 5
        mock_config.RESEARCH_CONTENT_CHUNK_LIMIT = 5000
        mock_config.TIMEOUT_TAVILY_SEARCH_ASYNC = 60
        mock_db.get_collections.return_value = []

        mock_res = MagicMock()
        mock_res.content = [MagicMock(text=json.dumps({
            "results": [{"url": "https://example.com", "raw_content": "A" * 100}]
        }))]
        
        # First query fails, second succeeds
        mock_tool.side_effect = [Exception("Fail"), mock_res]

        with patch('backend.mcp_client.tavily_client', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.connect = AsyncMock()

            result = await research_agent._execute_internal_searches(
                [{"query": "q1"}, {"query": "q2"}]
            )
            assert "example.com" in result

@pytest.mark.anyio
async def test_flow_fn_success(mock_agent_context):
    async def mock_run(*args, **kwargs):
        yield "chunk1"
        yield "chunk2"
        
    with patch.object(ResearchAgent, 'run', side_effect=mock_run) as mock_agent_run:
        chunks = [c async for c in flow_fn(mock_agent_context, "research", "topic")]
        assert chunks == ["chunk1", "chunk2"]
        mock_agent_run.assert_called_once_with("topic", mock_agent_context)

@pytest.mark.anyio
async def test_flow_fn_exception_handling(mock_agent_context):
    with patch.object(ResearchAgent, 'run', side_effect=Exception("Initialization error")) as mock_agent_run, \
         patch.object(agent_mod, 'db') as mock_db:
        
        chunks = [c async for c in flow_fn(mock_agent_context, "research", "topic")]
        
        assert len(chunks) == 2
        progress = json.loads(chunks[0][len("data: "):])
        assert progress["research_progress"]["phase"] == "failed"  # the card shows the failure
        assert "Research agent failed" in chunks[1]
        assert mock_agent_context.result == "Research agent failed: Initialization error"
        
        # Verify event logged to DB
        mock_db.add_message.assert_any_call(
            chat_id="test_chat",
            role='event',
            content='Research Agent failed: Initialization error',
            parent_id=123,
            parent_type='research'
        )
        
        # Verify chat state updated to failed
        mock_db.update_chat.assert_any_call("test_chat", research_state='failed')


LIMIT = "Error: Daily web search limit reached."


@pytest.mark.anyio
async def test_internal_searches_check_the_limit_before_each_query_and_do_not_swallow_it(research_agent, search_limit):
    search_limit.side_effect = [None, LIMIT]
    ok = MagicMock()
    ok.content = [MagicMock(text=json.dumps({"results": [{"url": "https://a.example", "raw_content": "A" * 100}]}))]
    with patch.object(agent_mod, '_execute_mcp_tool', new_callable=AsyncMock) as mock_tool, \
         patch.object(agent_mod, 'db') as mock_db, \
         patch.object(agent_mod, 'config') as mock_config, \
         patch('backend.mcp_client.tavily_client', new_callable=AsyncMock):
        mock_config.RESEARCH_SELECT_TOP_URLS_COUNT = 5
        mock_config.RESEARCH_EXTRACT_MIN_RAW_CONTENT = 10
        mock_config.RESEARCH_TAVILY_MAX_RESULTS_INITIAL = 5
        mock_config.RESEARCH_CONTENT_CHUNK_LIMIT = 5000
        mock_config.TIMEOUT_TAVILY_SEARCH_ASYNC = 60
        mock_db.get_collections.return_value = []
        mock_tool.return_value = ok
        with pytest.raises(agent_mod.SearchLimitReached, match="Daily web search limit"):
            await research_agent._execute_internal_searches([{"query": "q1"}, {"query": "q2"}])
    assert mock_tool.await_count == 1  # the second query never reached Tavily
    assert [c.args for c in search_limit.call_args_list] == [("test_chat",), ("test_chat",)]


class _StopLoop(Exception):
    """Ends the section state machine in tests once the state under test has finished."""


def _section_env(research_agent, events):
    async def emit(msg, *a, **k):
        events.append(msg)
        yield msg
    research_agent._emit_event = emit


@pytest.mark.anyio
async def test_the_initial_search_limit_halts_the_section_without_retrying(research_agent):
    events = []
    _section_env(research_agent, events)
    research_agent._execute_internal_searches = AsyncMock(side_effect=agent_mod.SearchLimitReached(LIMIT))
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.return_value = []
        with pytest.raises(agent_mod.SearchLimitReached):
            async for _ in research_agent._run_single_section(0, {"queries": [{"query": "q"}]}, {}, [{}], "", MagicMock()):
                pass
    assert research_agent._execute_internal_searches.await_count == 1  # RESEARCH_SEARCH_RETRIES is 1: no second attempt
    assert not any("No usable search results" in e for e in events)


@pytest.mark.anyio
async def test_a_limit_during_gap_searches_keeps_the_section_going_and_enters_the_state_once(research_agent):
    prefix = "[Section 0] "
    events = []
    _section_env(research_agent, events)
    history = [
        {"role": "event", "content": f"{prefix}{EVENT_INITIAL_SEARCHES_DONE}"},
        {"role": "event", "content": f"{prefix}{EVENT_REFLECTION_DONE}"},
    ]
    research_agent._get_assistant_output_for_phase = MagicMock(return_value={"content": json.dumps({"gaps": [{"query": "g1"}]})})
    research_agent._execute_internal_searches = AsyncMock(side_effect=agent_mod.SearchLimitReached(LIMIT))
    calls = {"n": 0}

    def get_messages(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise _StopLoop()  # the loop came back round after the gap-search state: stop here
        return history

    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.side_effect = get_messages
        with pytest.raises(_StopLoop):
            async for _ in research_agent._run_single_section(0, {}, {}, [{}], "", MagicMock()):
                pass
        added = [c.kwargs for c in mock_db.add_collection.call_args_list]
    assert research_agent._execute_internal_searches.await_count == 1
    assert sum(EVENT_GAP_SEARCHES_DONE in e for e in events) == 1
    assert added and added[0]["collection_type"] == "section_0_followup_searches"
    assert added[0]["items"].strip() == "## FOLLOW-UP SEARCH RESULTS"  # earlier results kept, no new ones




# ---- research_progress ---------------------------------------------------------------------------------------

def _progress_chunks(chunks):
    return [json.loads(c[len("data: "):])["research_progress"] for c in chunks if isinstance(c, str) and '"research_progress"' in c]


@pytest.mark.anyio
async def test_publish_progress_stores_the_snapshot_and_streams_one_data_chunk(research_agent):
    plan = {"title": "T", "sections": [{"heading": "A"}, {"heading": "B"}]}
    history = [
        {"role": "event", "content": "[Section 0] Starting Execution: Section 0", "timestamp": 100.0},
        {"role": "event", "content": "Section 0 complete.", "timestamp": 138.0},
    ]
    colls = [{"collection_type": "visited_urls", "items": json.dumps(["u1", "u2", "u3"])}]
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.return_value = history
        mock_db.get_collections.return_value = colls
        chunks = [c async for c in research_agent._publish_progress("executing", plan)]
    assert len(chunks) == 1 and chunks[0].startswith("data: ") and chunks[0].endswith("\n\n")
    payload = json.loads(chunks[0][len("data: "):])
    assert payload["parent_type"] == "research"
    snap = payload["research_progress"]
    assert snap["phase"] == "executing" and snap["steps_done"] == 1 and snap["steps_total"] == 2 and snap["pages_read"] == 3
    assert snap["steps"][0] == {"index": 0, "heading": "A", "state": "done", "duration_ms": 38000}
    stored = mock_db.add_collection.call_args.kwargs
    assert stored["collection_type"] == "research_progress" and stored["items"] == snap and stored["overwrite"] is True
    assert stored["parent_message_id"] == 123 and stored["parent_type"] == "research"


@pytest.mark.anyio
async def test_publish_progress_reads_the_stored_plan_when_none_is_passed(research_agent):
    colls = [{"collection_type": "research_plan", "items": json.dumps({"title": "Stored", "sections": [{"heading": "A"}]})}]
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.return_value = []
        mock_db.get_collections.return_value = colls
        chunks = [c async for c in research_agent._publish_progress("awaiting_approval")]
    snap = _progress_chunks(chunks)[0]
    assert snap["title"] == "Stored" and snap["steps"][0]["state"] == "pending"


@pytest.mark.anyio
async def test_a_failure_while_publishing_progress_is_logged_and_never_raised(research_agent):
    with patch.object(agent_mod, 'db') as mock_db, patch.object(agent_mod, 'log_event') as events:
        mock_db.get_messages.side_effect = RuntimeError("db down")
        chunks = [c async for c in research_agent._publish_progress("executing", None)]
    assert chunks == []
    assert any(c.args[0] == "research_progress_error" for c in events.call_args_list)


@pytest.mark.anyio
async def test_run_executor_publishes_progress_around_each_section_and_the_stored_one_matches_the_last_chunk(research_agent):
    plan = {"title": "T", "sections": [{"heading": "A"}, {"heading": "B"}]}
    state = {"events": [], "stored": None}

    async def single_section(idx, *a, **k):
        state["events"].append({"role": "event", "content": f"[Section {idx}] Starting Execution: Section {idx}", "timestamp": 10.0 + idx})
        yield f"section-{idx}"
        state["events"].append({"role": "event", "content": f"Section {idx} complete.", "timestamp": 20.0 + idx})

    def add_collection(**kw):
        if kw["collection_type"] == "research_progress":
            state["stored"] = kw["items"]

    with patch.object(agent_mod, 'db') as mock_db, patch.object(research_agent, '_run_single_section', side_effect=single_section):
        mock_db.get_messages.side_effect = lambda *a, **k: list(state["events"])
        mock_db.get_collections.return_value = [{"collection_type": "report_file_system_id", "items": json.dumps("fs1")}]
        mock_db.add_collection.side_effect = add_collection
        chunks = [c async for c in research_agent._run_executor(plan, MagicMock())]
    snaps = _progress_chunks(chunks)
    assert [s["steps_done"] for s in snaps] == [0, 1, 2]  # before the first section, then after each
    assert all(s["phase"] == "executing" for s in snaps)
    assert snaps[-1]["steps"][1] == {"index": 1, "heading": "B", "state": "done", "duration_ms": 10000}
    assert state["stored"] == snaps[-1]


@pytest.mark.anyio
async def test_run_publishes_failed_progress_when_the_executor_crashes(research_agent):
    plan = {"title": "T", "sections": [{"heading": "A", "queries": [], "description": "d"}]}
    history = [{"role": "event", "content": "Research plan approved. Proceeding to execution."},
               {"role": "event", "content": "Scouting finalized. Context gathered."}]
    colls = [{"collection_type": "research_plan", "items": json.dumps(plan)}]

    async def boom(*a, **k):
        raise RuntimeError("executor down")
        yield

    with patch.object(agent_mod, 'db') as mock_db, patch.object(research_agent, '_run_executor', side_effect=boom), \
         patch.object(research_agent, '_validate_plan', return_value=(True, "Valid")):
        mock_db.get_messages.return_value = history
        mock_db.get_collections.return_value = colls
        chunks = [c async for c in research_agent.run("topic", MagicMock())]
    assert _progress_chunks(chunks)[-1]["phase"] == "failed"
    mock_db.update_chat.assert_any_call("test_chat", research_state='failed')


def _approved_history(*extra):
    return [{"role": "event", "content": "Research plan approved. Proceeding to execution."},
            {"role": "event", "content": "Scouting finalized. Context gathered."}, *extra]


async def _run_to_the_end(agent, history, **patches):
    plan = {"title": "T", "sections": [{"heading": "A", "queries": [], "description": "d"}]}
    colls = [{"collection_type": "research_plan", "items": json.dumps(plan)}]

    async def nothing(*a, **k):
        return
        yield

    with patch.object(agent_mod, 'db') as mock_db, patch.object(agent, '_run_executor', side_effect=nothing), \
         patch.object(agent, '_run_synthesis', side_effect=nothing), patch.object(agent, '_validate_plan', return_value=(True, "Valid")):
        mock_db.get_messages.return_value = history
        mock_db.get_collections.return_value = colls
        return [c async for c in agent.run("topic", MagicMock())]


@pytest.mark.anyio
async def test_run_publishes_synthesizing_then_done_when_the_completion_event_is_stored(research_agent):
    chunks = await _run_to_the_end(research_agent, _approved_history(
        {"role": "event", "content": "Research complete! The full report has been audited and finalized in the FileSystem."}))
    assert [s["phase"] for s in _progress_chunks(chunks)] == ["synthesizing", "done"]


@pytest.mark.anyio
async def test_a_synthesis_that_paused_publishes_no_done(research_agent):
    chunks = await _run_to_the_end(research_agent, _approved_history())
    assert [s["phase"] for s in _progress_chunks(chunks)] == ["synthesizing"]


@pytest.mark.anyio
async def test_a_synthesis_that_halted_on_a_failure_event_publishes_failed(research_agent):
    chunks = await _run_to_the_end(research_agent, _approved_history(
        {"role": "event", "content": "❌ Report file_system is missing. Cannot finalize."}))
    assert [s["phase"] for s in _progress_chunks(chunks)] == ["synthesizing", "failed"]


@pytest.mark.anyio
async def test_run_publishes_planning_before_the_planner_and_failed_for_an_invalid_plan(research_agent):
    async def nothing(*a, **k):
        return
        yield

    with patch.object(agent_mod, 'db') as mock_db, patch.object(research_agent, '_run_planner', side_effect=nothing):
        mock_db.get_messages.return_value = [{"role": "event", "content": "Scouting finalized. Context gathered."}]
        mock_db.get_collections.return_value = []
        chunks = [c async for c in research_agent.run("topic", MagicMock())]
    assert [s["phase"] for s in _progress_chunks(chunks)] == ["planning", "awaiting_approval"]
    plan_coll = [{"collection_type": "research_plan", "items": json.dumps({"title": "T", "sections": []})}]
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.return_value = _approved_history()
        mock_db.get_collections.return_value = plan_coll
        chunks = [c async for c in research_agent.run("topic", MagicMock())]
    assert _progress_chunks(chunks)[-1]["phase"] == "failed"  # validation failure (no sections)
    with patch.object(agent_mod, 'db') as mock_db:
        mock_db.get_messages.return_value = _approved_history()
        mock_db.get_collections.return_value = []
        chunks = [c async for c in research_agent.run("topic", MagicMock())]
    assert _progress_chunks(chunks)[-1]["phase"] == "failed"  # plan missing
