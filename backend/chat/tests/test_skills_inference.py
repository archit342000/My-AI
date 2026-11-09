import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from backend.chat.handler import ChatHandler


@pytest.fixture
def mock_db():
    with patch("backend.chat.handler.db") as mock:
        mock.flush_sse_chunks.return_value = True
        mock.get_last_assistant_message.return_value = None
        yield mock


@pytest.fixture
def mock_task_manager():
    with patch("backend.chat.handler.task_manager") as mock:
        yield mock


@pytest.fixture
def mock_response_cache():
    with patch("backend.chat.handler.response_cache") as mock:
        yield mock


@pytest.mark.anyio
async def test_skills_system_prompt_injection(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    # 1. Mock DB returns
    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git commands.",
        }
    ]
    mock_db.get_chat.return_value = {"user_id": "user-a"}
    mock_db.get_messages.return_value = [{"role": "user", "content": "hello"}]
    mock_task_manager.is_interrupted.return_value = False

    # 2. Mock engine.stream
    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    # 3. Trigger orchestrated stream
    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    # 4. Verify stream arguments
    assert handler.engine.stream.call_count == 1
    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # First message is the system prompt
    assert messages[0]["role"] == "system"
    assert "Available Skills" in messages[0]["content"]
    assert "/git-helper: Git commands assist" in messages[0]["content"]
    mock_db.get_all_skills.assert_called_with("user-a")  # the chat owner's skills

    # Second message is the unchanged user message
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "hello"


@pytest.mark.anyio
async def test_latest_user_invocation_replacement(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git status.",
        }
    ]
    mock_db.get_chat.return_value = {}
    # User message starts with the skill command
    mock_db.get_messages.return_value = [
        {"role": "user", "content": "/git-helper check status"}
    ]
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # The user message should be replaced by the instructions + the remaining text
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "[SKILL: git-helper]\nUse git status.\n[/SKILL]\n\ncheck status"


@pytest.mark.anyio
async def test_multiple_user_invocations_only_latest_replaced(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git status.",
        }
    ]
    mock_db.get_chat.return_value = {}
    mock_db.get_messages.return_value = [
        {"role": "user", "content": "/git-helper first turn"},
        {"role": "assistant", "content": "Understood."},
        {"role": "user", "content": "/git-helper second turn"},
    ]
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # First user message (older) should remain as original string to prevent bloat
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "/git-helper first turn"

    # Second user message (latest) should be replaced with instructions
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "[SKILL: git-helper]\nUse git status.\n[/SKILL]\n\nsecond turn"


@pytest.mark.anyio
async def test_ai_invocation_synthetic_message_injection(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git status.",
        }
    ]
    mock_db.get_chat.return_value = {}

    tool_call = {
        "id": "call_abc",
        "type": "function",
        "function": {
            "name": "get_skill_details",
            "arguments": json.dumps({"skill_name": "git-helper"}),
        },
    }

    mock_db.get_messages.return_value = [
        {"role": "user", "content": "How do I do git?"},
        {
            "role": "assistant",
            "content": "Let me load the skill.",
            "tool_calls": [tool_call],
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc",
            "content": "Successfully loaded skill details for 'git-helper'.",
        },
    ]
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # We expect system, user, assistant, tool, AND injected synthetic user message!
    assert len(messages) == 5

    # Check the injected synthetic user message (messages[4])
    assert messages[4]["role"] == "user"
    assert messages[4]["content"] == "[SKILL: git-helper]\nUse git status.\n[/SKILL]"


@pytest.mark.anyio
async def test_multiple_ai_invocations_only_latest_gets_full_instructions(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git status.",
        }
    ]
    mock_db.get_chat.return_value = {}

    mock_db.get_messages.return_value = [
        {"role": "user", "content": "How do I do git?"},
        # First tool call
        {
            "role": "assistant",
            "content": "Let me load the skill.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_skill_details",
                        "arguments": '{"skill_name": "git-helper"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "Successfully loaded skill details for 'git-helper'.",
        },
        # Second tool call
        {
            "role": "assistant",
            "content": "Let me load the skill again.",
            "tool_calls": [
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_skill_details",
                        "arguments": '{"skill_name": "git-helper"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_2",
            "content": "Successfully loaded skill details for 'git-helper'.",
        },
    ]
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # We should have system prompt (1) + user (1) + assistant1 + tool1 + synthetic1 + assistant2 + tool2 + synthetic2
    # In total 8 messages. Let's verify their roles and contents.
    assert len(messages) == 8

    # First AI invocation (older) should get f"/{skill_name}" content
    assert messages[4]["role"] == "user"
    assert messages[4]["content"] == "/git-helper"

    # Second AI invocation (latest) should get the full instructions
    assert messages[7]["role"] == "user"
    assert messages[7]["content"] == "[SKILL: git-helper]\nUse git status.\n[/SKILL]"


@pytest.mark.anyio
async def test_multimodal_user_invocation_replacement(
    mock_db, mock_task_manager, mock_response_cache
):
    chat_id = "test_chat_skills"
    handler = ChatHandler(chat_id)

    mock_db.get_all_skills.return_value = [
        {
            "id": "s1",
            "name": "git-helper",
            "description": "Git commands assist",
            "instructions": "Use git status.",
        }
    ]
    mock_db.get_chat.return_value = {}
    
    # User message contains multimodal list content with an image and a skill invocation
    multimodal_content = [
        {"type": "text", "text": "/git-helper check status\n\n[System Note: some notes]"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,image_data"}}
    ]
    
    mock_db.get_messages.return_value = [
        {"role": "user", "content": multimodal_content}
    ]
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)

    gen = handler._run_orchestrated_stream(
        user_message=None, model_name="test-model"
    )
    async for _ in gen:
        pass

    called_kwargs = handler.engine.stream.call_args[1]
    messages = called_kwargs["messages"]

    # The user message should have its text block updated
    assert messages[1]["role"] == "user"
    content = messages[1]["content"]
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "[SKILL: git-helper]\nUse git status.\n[/SKILL]\n\ncheck status\n\n[System Note: some notes]"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"] == "data:image/png;base64,image_data"


@pytest.mark.anyio
async def test_prompt_for_user_b_contains_none_of_user_as_skills_or_preferences(
    mock_db, mock_task_manager, mock_response_cache
):
    skills = {"user-a": [{"id": "sa", "name": "a-secret-skill", "description": "A only", "instructions": "x"}],
              "user-b": [{"id": "sb", "name": "b-skill", "description": "B only", "instructions": "y"}]}
    prefs = {"user-a": [{"id": "pa", "tag": "t", "content": "A's private preference"}],
             "user-b": [{"id": "pb", "tag": "t", "content": "B's preference"}]}
    mock_db.get_all_skills.side_effect = lambda owner: skills[owner]
    mock_db.get_all_preferences.side_effect = lambda owner: prefs[owner]
    mock_db.get_chat.return_value = {"user_id": "user-b", "user_preferences": 1}
    mock_db.get_messages.return_value = [{"role": "user", "content": "hello"}]
    mock_task_manager.is_interrupted.return_value = False

    handler = ChatHandler("chat_of_b")

    async def mock_stream_gen(*args, **kwargs):
        yield "data: chunk1"

    handler.engine.stream = MagicMock(side_effect=mock_stream_gen)
    async for _ in handler._run_orchestrated_stream(user_message=None, model_name="test-model"):
        pass
    system_prompt = handler.engine.stream.call_args[1]["messages"][0]["content"]
    assert "b-skill" in system_prompt and "B's preference" in system_prompt
    assert "a-secret-skill" not in system_prompt and "A's private preference" not in system_prompt

