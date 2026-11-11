import asyncio
import sqlite3
import time
import json
import logging
from typing import AsyncGenerator, Callable, Any, Optional
from backend.database import db
from backend.logging import log_event
from backend.task_manager import task_manager

logger = logging.getLogger(__name__)


def _id_after(message_id: Any, after: Any) -> bool:
    """True when a message id comes after another (ids are integers; a non-integer id never does)."""
    try:
        return int(message_id) > int(after)
    except (TypeError, ValueError):
        return False

class TurnHandler:
    """
    Orchestrates the entire execution of an assistant turn.
    
    This process is responsible for:
    1. Serialization: Ensuring strictly one turn executes at a time globally (configurable).
    2. Execution: Running the provided 'run' function which generates the output.
    3. Persistence: Ensuring all turn-related metadata and chat states are finalized.
    """
    
    @classmethod
    async def handle_turn(
        cls,
        chat_id: str,
        parent_message_id: int,
        run_fn: Callable[..., AsyncGenerator[str, None]],
        model: Optional[str] = None,
        *args,
        sources: Any = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Wraps a turn execution with standardized persistence.
        
        Args:
            chat_id: The ID of the chat undergoing the turn.
            parent_message_id: The ID of the user message that triggered this turn.
            run_fn: An async generator function that defines the turn logic.
            model: Optional model name used for persistence tagging.
            sources: The chat's source registry (consumed here, not passed to run_fn): when the turn's answer cites
                numbered sources, they are stored with the answer and sent after a normal finish.
            *args, **kwargs: Arguments passed through to the run_fn.
            
        Yields:
            Chunks yielded by the run_fn.
        """
        log_event("turn_handler_start", {"chat_id": chat_id, "parent_id": parent_message_id, "model": model})
        
        start_time = time.time()
        
        try:
            # Iterate over the provided run function to yield chunks back to the client
            async for chunk in run_fn(*args, **kwargs):
                yield chunk
            
            # Constant persistence logic: ensure the turn is finalized in the database
            cls._persist_final_state(chat_id, parent_message_id, model)

            # Cited sources go out only after a normal finish: an exception, a cancellation or a stop skips this.
            if sources is not None and not task_manager.is_interrupted(chat_id):
                cited_line = cls._store_cited_sources(chat_id, parent_message_id, sources)
                if cited_line:
                    yield cited_line
            
        except Exception as e:
            log_event("turn_handler_error", {"chat_id": chat_id, "error": str(e)})
            logger.error(f"Error during assistant turn for chat {chat_id}: {str(e)}", exc_info=True)
            raise
        finally:
            duration = time.time() - start_time
            log_event("turn_handler_end", {"chat_id": chat_id, "duration": duration})

    @classmethod
    def _store_cited_sources(cls, chat_id: str, parent_message_id: Optional[int], sources: Any) -> Optional[str]:
        """
        Store the sources the turn's answer cited (`[[n]]`) on the turn's last assistant row, and return the `sources` SSE line.
        Returns None when nothing was cited (answers without sources are unchanged) or the turn has no answer row.
        """
        if parent_message_id is None:
            return None
        try:
            rows = [m for m in db.get_messages(chat_id)
                    if m.get("role") == "assistant" and (m.get("parent_type") in (None, "main")) and _id_after(m.get("id"), parent_message_id)]
            if not rows:
                return None
            cited = sources.cited("\n".join(str(m.get("content") or "") for m in rows))
            if not cited:
                return None
            db.add_collection(chat_id=chat_id, parent_message_id=rows[-1]["id"], parent_type="main",
                              collection_type="sources", items=cited, overwrite=True)
            return "data: " + json.dumps({"sources": cited}) + "\n\n"
        except (ValueError, TypeError, KeyError, sqlite3.Error) as e:
            log_event("turn_sources_error", {"chat_id": chat_id, "error": str(e)})
            logger.error(f"Failed to store the cited sources of turn {parent_message_id}: {str(e)}")
            return None

    @classmethod
    def _persist_final_state(cls, chat_id: str, parent_message_id: int, model: Optional[str] = None):
        """
        Unified persistence logic that must run at the end of every turn.
1. Update chat timestamp.
        """
        try:
            # 1. Update the chat's activity timestamp
            db.update_chat(chat_id, timestamp=time.time())
            
            log_event("turn_persistence_finalized", {
                "chat_id": chat_id, 
                "parent_id": parent_message_id
            })
            
        except Exception as e:
            log_event("turn_persistence_error", {"chat_id": chat_id, "error": str(e)})
            logger.error(f"Failed to finalize persistence for turn {parent_message_id}: {str(e)}")
