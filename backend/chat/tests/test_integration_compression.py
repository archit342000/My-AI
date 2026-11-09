import pytest
import json
from unittest.mock import patch, MagicMock
from backend.database.init_db import init_db
from backend.database import db, response_cache
from backend.chat.handler import ChatHandler
from backend.chat.tests.conftest import MockServerState


@pytest.fixture
def temp_db(tmp_path):
    temp_db_path = str(tmp_path / "test_integration.db")
    with patch("backend.database.init_db.DB_PATH", temp_db_path), patch(
        "backend.database.db_layer.DB_PATH", temp_db_path
    ), patch("backend.database.db_wrapper.DB_PATH", temp_db_path):
        init_db()
        yield temp_db_path


@pytest.mark.anyio
@patch("backend.chat.handler.task_manager")
async def test_integration_no_compression(mock_task_manager, temp_db):
    # Setup database environment
    with patch("backend.database.init_db.DB_PATH", temp_db), patch(
        "backend.database.db_layer.DB_PATH", temp_db
    ), patch("backend.database.db_wrapper.DB_PATH", temp_db):
        mock_task_manager.is_interrupted.return_value = False

        # Ensure response cache is initialized for the chat
        response_cache.initialize_chat("chat_1", overwrite=True)

        # Ensure chat exists
        db.ensure_chat_exists("chat_1", "u1")
        # Save a system prompt and some message history
        db.update_chat(
            "chat_1",
            last_model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
            system_prompt="Standard System Prompt",
        )
        db.add_message(
            chat_id="chat_1", role="user", content="Hello there"
        )

        # Mock server returns normal output
        MockServerState.chat_responses = [
            [
                {"choices": [{"delta": {"content": "General response"}}]},
                {"timings": {"prompt_n": 5}},
            ]
        ]

        handler = ChatHandler("chat_1")
        # Run stream
        chunks = []
        async for chunk in handler._run_orchestrated_stream(
            user_message={"id": 2, "role": "user", "content": "How are you?"},
            model_name="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
        ):
            chunks.append(chunk)

        # Assert correct response streamed
        assert any("General response" in c for c in chunks)

        # Assert no compression metadata in database
        chat = db.get_chat("chat_1")
        assert chat.get("history_compression") is None


@pytest.mark.anyio
@patch("backend.chat.handler.task_manager")
async def test_integration_trigger_compression(
    mock_task_manager, temp_db
):
    # Setup database environment
    with patch("backend.database.init_db.DB_PATH", temp_db), patch(
        "backend.database.db_layer.DB_PATH", temp_db
    ), patch("backend.database.db_wrapper.DB_PATH", temp_db):
        mock_task_manager.is_interrupted.return_value = False

        # Initialize response cache
        response_cache.initialize_chat("chat_2", overwrite=True)

        # Set context window size very small to trigger compression immediately in both imported sites
        with patch("backend.inference.compression.get_model_metadata") as mock_meta1, \
             patch("backend.models.get_model_metadata") as mock_meta2:
            
            mock_meta1.return_value = {
                "context_window": 100,
                "tokenizer": "Qwen/Qwen3.6-35B-A3B",
            }
            mock_meta2.return_value = {
                "context_window": 100,
                "tokenizer": "Qwen/Qwen3.6-35B-A3B",
            }

            db.ensure_chat_exists("chat_2", "u1")
            db.update_chat(
                "chat_2",
                last_model="Qwen/Qwen3.6-35B-A3B",
                system_prompt="Standard System Prompt",
            )

            # Build some history that we will compress
            db.add_message(
                chat_id="chat_2", role="user", content="First question"
            )
            msg2_id = db.add_message(
                chat_id="chat_2",
                role="assistant",
                content="First response",
            )

            # Set up responses in MockServerState:
            # First POST response is the summarizer call (blocking)
            # Second POST response is the final completion call (streaming)
            MockServerState.chat_responses = [
                # Summarizer response
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "You answered the first question.",
                            }
                        }
                    ]
                },
                # Stream response
                [
                    {"choices": [{"delta": {"content": "Final response content."}}]},
                    {"timings": {"prompt_n": 5}},
                ],
            ]

            handler = ChatHandler("chat_2")
            chunks = []
            async for chunk in handler._run_orchestrated_stream(
                user_message={"id": 3, "role": "user", "content": "Second question"},
                model_name="Qwen/Qwen3.6-35B-A3B",
            ):
                chunks.append(chunk)

            # Verify that compression saved the metadata to the database
            chat = db.get_chat("chat_2")
            assert chat.get("history_compression") is not None
            comp_data = json.loads(chat.get("history_compression"))
            assert comp_data["boundary_message_id"] == msg2_id
            assert comp_data["summary_text"] == "You answered the first question."

            # Verify response matches the final response content
            assert any("Final response content." in c for c in chunks)


@pytest.mark.anyio
@patch("backend.chat.handler.task_manager")
async def test_integration_deletion_safeguard_invalidation(
    mock_task_manager, temp_db
):
    with patch("backend.database.init_db.DB_PATH", temp_db), patch(
        "backend.database.db_layer.DB_PATH", temp_db
    ), patch("backend.database.db_wrapper.DB_PATH", temp_db):

        db.ensure_chat_exists("chat_3", "u1")
        
        id1 = db.add_message(chat_id="chat_3", role="user", content="msg 1")
        id2 = db.add_message(
            chat_id="chat_3", role="assistant", content="msg 2"
        )
        id3 = db.add_message(chat_id="chat_3", role="user", content="msg 3")

        comp_data = {
            "boundary_message_id": id2,
            "summary_text": "Summary content.",
            "file_notes": "",
            "images": [],
        }
        db.update_chat(
            "chat_3", history_compression=json.dumps(comp_data), last_model="gpt-4"
        )

        # Deleting a message before the boundary (id1 <= id2)
        db.delete_message("chat_3", id1)

        # Assert that history_compression is cleared
        chat = db.get_chat("chat_3")
        assert chat.get("history_compression") is None
