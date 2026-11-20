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
        
        assert len(chunks) == 1
        assert "Research agent failed" in chunks[0]
        assert mock_agent_context.result == "Research agent failed. Try again."
        
        # Verify event logged to DB
        mock_db.add_message.assert_any_call(
            chat_id="test_chat",
            role='event',
            content='Research Agent failed. Try again.',
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



# ---- fixed failure texts ---------------------------------------------------------------------------------------

SECRET = "/secret/place db locked"
STOPPED = "Research stopped; you can start it again."


def _events_of(agent):
    """Replace `_emit_event` by one that records the text it was given and streams it."""
    texts = []

    async def emit(content, parent_type=None):
        texts.append(content)
        yield content
    agent._emit_event = emit
    return texts


def _run_state(history=(), plan=None):
    colls = [{"collection_type": "research_plan", "items": json.dumps(plan)}] if plan else []
    return list(history), colls


@pytest.mark.anyio
@pytest.mark.parametrize("phase,patched,history,expected_event", [
    ("scout", "_run_scout", [], f"❌ Scout phase failed. {STOPPED}"),
    ("planner", "_run_planner", [{"role": "event", "content": "Scouting finalized. Context gathered."}], f"❌ Planner phase failed. {STOPPED}"),
    ("executor", "_run_executor", [{"role": "event", "content": "Scouting finalized. Context gathered."},
                                   {"role": "event", "content": "Research plan approved. Proceeding to execution."}], f"❌ Execution phase failed. {STOPPED}"),
    ("synthesis", "_run_synthesis", [{"role": "event", "content": "Scouting finalized. Context gathered."},
                                     {"role": "event", "content": "Research plan approved. Proceeding to execution."}], f"❌ Synthesis phase failed. {STOPPED}"),
])
async def test_a_failing_research_phase_sends_a_fixed_text_marks_the_chat_failed_and_logs_the_detail(research_agent, phase, patched, history, expected_event):
    plan = {"title": "T", "sections": [{"heading": "A", "queries": [], "description": "d"}]}
    hist, colls = _run_state(history, plan)

    async def boom(*a, **k):
        raise RuntimeError(SECRET)
        yield

    async def nothing(*a, **k):
        return
        yield

    texts = _events_of(research_agent)
    with patch.object(agent_mod, 'db') as mock_db, patch.object(agent_mod, 'log_event') as events, \
         patch.object(research_agent, '_validate_plan', return_value=(True, "Valid")), \
         patch.object(research_agent, '_run_executor', side_effect=nothing), patch.object(research_agent, '_run_synthesis', side_effect=nothing), \
         patch.object(research_agent, '_run_scout', side_effect=nothing), patch.object(research_agent, '_run_planner', side_effect=nothing):
        mock_db.get_messages.return_value = hist
        mock_db.get_collections.return_value = colls
        setattr(research_agent, patched, MagicMock(side_effect=boom))
        [c async for c in research_agent.run("topic", MagicMock())]
    assert expected_event in texts and all("secret" not in t for t in texts)
    mock_db.update_chat.assert_any_call("test_chat", research_state='failed')
    assert any(c.args[0] == f"research_{phase}_error" and "db locked" in c.args[1]["error"] for c in events.call_args_list)


@pytest.mark.anyio
async def test_a_section_that_fails_stops_research_with_a_fixed_text_and_a_search_limit_says_so(research_agent):
    from backend.auth.rate_limit import SearchLimitReached
    plan = {"title": "T", "sections": [{"heading": "A"}]}
    texts = _events_of(research_agent)
    for error, expected in ((RuntimeError(SECRET), f"❌ Section 0 failed. {STOPPED}"),
                            (SearchLimitReached("Error: Daily web search limit reached."), "❌ Section 0 stopped: the daily web search limit is reached. Try again tomorrow.")):
        async def boom(*a, **k):
            raise error
            yield
        texts.clear()
        with patch.object(agent_mod, 'db') as mock_db, patch.object(research_agent, '_run_single_section', side_effect=boom):
            mock_db.get_messages.return_value = []
            mock_db.get_collections.return_value = [{"collection_type": "report_file_system_id", "items": '"fs_1"'}]
            with pytest.raises(type(error)):
                [c async for c in research_agent._run_executor(plan, MagicMock())]
        assert expected in texts and all("secret" not in t for t in texts)


@pytest.mark.anyio
async def test_the_report_update_failure_text_says_research_stopped(research_agent):
    import inspect
    source = inspect.getsource(agent_mod.ResearchAgent._run_single_section)
    assert "Research stopped; you can start it again." in source and "Research continues" not in source


@pytest.mark.anyio
async def test_an_invalid_plan_notice_is_fixed_wording_with_the_reason_only_in_the_log():
    import inspect
    source = inspect.getsource(agent_mod.ResearchAgent._run_planner)
    assert "The generated plan was not valid. Trying a new plan…" in source and "({reason})" not in source
