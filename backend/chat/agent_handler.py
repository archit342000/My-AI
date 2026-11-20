import logging
import json
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Union

from backend.database import db
from backend.inference import ManualChunkEmitter
from backend.logging import log_event
from backend.chat.models import AgentResult

logger = logging.getLogger(__name__)

AGENT_PROFILES = {
    "search_web": "precision",
    "visit_page": "precision",
    "research_agent": "precision",
    "document_agent": "precision",
    "file_system_agent": "precision",
    "browsing_agent": "precision",
    "git_agent": "precision"
}

class AgentHandler:
    """
    Handles the execution logic for sub-agents
    within a chat turn.
    
    This handler ensures that agent activity:
    1. Is correctly anchored to the current assistant message.
    2. Uses standardized streaming via the main ChatHandler's logic.
    3. Persists to the sub_agent_messages table.
    """

    def __init__(self, chat_id: str, main_chat_handler: Any, parent_message_id: Optional[Any] = None):
        self.chat_id = chat_id
        self.main_chat_handler = main_chat_handler
        self.parent_message_id = parent_message_id
        self.emitter = ManualChunkEmitter()
        self._chat_handler = None
        self.result: Optional[Union[str, AgentResult]] = None

    @property
    def chat_handler(self):
        """Lazy-initialize an isolated ChatHandler for this agent."""
        if self._chat_handler is None:
            from .handler import ChatHandler
            self._chat_handler = ChatHandler(self.chat_id)
        
        # Sync the anchoring context dynamically
        if self._chat_handler:
            self._chat_handler.tool_handler.parent_message_id = self.parent_message_id
            self._chat_handler.tool_handler.turn_anchor_id = self.parent_message_id
            self._chat_handler.tool_handler.agent_handler.parent_message_id = self.parent_message_id
            
            # Ensure the isolated handler is aware of the model context
            if hasattr(self.main_chat_handler, 'active_model'):
                self._chat_handler.active_model = self.main_chat_handler.active_model
        return self._chat_handler
    
    @property
    def model(self) -> str:
        """Returns the active model from the isolated chat handler."""
        if not hasattr(self.chat_handler, 'active_model'):
            raise AttributeError("AgentHandler: active_model not set. Ensure turn is initialized correctly.")
        return self.chat_handler.active_model

    async def execute_agent(
        self, 
        agent_name: str, 
        flow_fn: Any,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Executes a specific agent flow with standardized orchestration.
        """
        log_event("agent_start", {"chat_id": self.chat_id, "agent": agent_name})
        self.result = None  # a helper that sets no result must not inherit the previous run's
        
        # Standardize iteration to allow capturing return values from async generators
        it = flow_fn(agent=self, agent_name=agent_name, **kwargs).__aiter__()
        try:
            while True:
                chunk = await it.__anext__()
                yield chunk
        except StopAsyncIteration:
            return

    # async def emit_status(self, agent_name: str, status_text: str) -> AsyncGenerator[str, None]:
    #     """Convenience method for agents to emit a 'thinking' or 'status' update."""
    #     async for chunk in self.chat_handler._run_orchestrated_stream(
    #         user_message={"id": self.parent_message_id},
    #         model_name=self.model,
    #         parent_type=agent_name,
    #         custom_stream=self.emitter.stream_message(thinking=status_text)
    #     ):
    #         yield chunk

    # async def emit_event(self, agent_name: str, event_text: str) -> AsyncGenerator[str, None]:
    #     """Emits an 'event' role message, persists it, and streams it to the UI."""
    #     db.add_message(
    #         chat_id=self.chat_id,
    #         role="event",
    #         content=event_text,
    #         parent_message_id=self.parent_message_id,
    #         parent_type=agent_name
    #     )
    #     async for chunk in self.chat_handler._run_orchestrated_stream(
    #         user_message={"id": self.parent_message_id},
    #         model_name=self.model,
    #         parent_type=agent_name,
    #         custom_stream=self.emitter.stream_message(event=event_text)
    #     ):
    #         yield chunk

    async def run_inference_step(
        self, 
        agent_name: str, 
        messages: List[Dict[str, Any]], 
        model_name: str,
        custom_stream: Optional[AsyncGenerator[str, None]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Runs a single turn for an agent. 
        Defaults to LLM inference, but can accept a custom_stream for manual turns.
        """
        if custom_stream is None:
            # Apply agent-specific profiles
            profile_name = AGENT_PROFILES.get(agent_name)
            if profile_name:
                try:
                    from .handler import THINKING_PROFILES
                    if profile_name in THINKING_PROFILES:
                        profile_params = THINKING_PROFILES[profile_name]
                        if 'enable_thinking' in profile_params:
                            if 'chat_template_kwargs' not in kwargs:
                                kwargs['chat_template_kwargs'] = {}
                            kwargs['chat_template_kwargs']['enable_thinking'] = profile_params['enable_thinking']
                        
                        for param in ['temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty', 'frequency_penalty']:
                            if param in profile_params and param not in kwargs:
                                kwargs[param] = profile_params[param]
                except ImportError:
                    logger.warning("AgentHandler: Failed to import THINKING_PROFILES for agent profiles.")
            else:
                # Inherit parameters from the main chat metadata
                from backend.database import db
                chat_metadata = db.get_chat(self.chat_id)
                if chat_metadata:
                    if 'enable_thinking' in chat_metadata and chat_metadata['enable_thinking'] is not None:
                        if 'chat_template_kwargs' not in kwargs:
                            kwargs['chat_template_kwargs'] = {}
                        kwargs['chat_template_kwargs']['enable_thinking'] = bool(chat_metadata['enable_thinking'])
                    
                    for param in ['temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty', 'frequency_penalty', 'thinking_budget_tokens']:
                        if param in chat_metadata and chat_metadata[param] is not None and param not in kwargs:
                            kwargs[param] = chat_metadata[param]

            custom_stream = self.chat_handler.engine.stream(
                messages=messages,
                model=model_name,
                chat_id=self.chat_id,
                **kwargs
            )

        # Use the master ChatHandler logic to ensure caching/flushing
        async for chunk in self.chat_handler._run_orchestrated_stream(
            user_message={"id": self.parent_message_id},
            model_name=model_name,
            parent_type=agent_name,
            custom_stream=custom_stream,
            agent_parent_message_id=self.parent_message_id
        ):
            yield chunk
