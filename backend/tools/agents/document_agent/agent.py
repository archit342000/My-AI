# backend/tools/agents/document_agent/agent.py
import logging
import json
import os
import time
from typing import AsyncGenerator, Any, List, Dict
from backend.auth.ownership import file_for_chat
from backend.database import db
from backend.logging import log_event, error_detail
from backend import config
from backend.rag import RAGProvider, FileRAG
from backend.models import get_embedding_model, load_model_config
from backend.files.manager import FileManager
from backend.logging import log_tool_call
from backend.tools.agents.document_agent.prompts import DOCUMENT_AGENT_SYSTEM_PROMPT, DOCUMENT_AGENT_VISION_SYSTEM_PROMPT
from backend.tools import get_document_agent_tools, PAGE_BASED_MIME_TYPES
from backend.tools.agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)

def is_vision_model(model_name: str) -> bool:
    """Checks if a model name corresponds to a vision-capable model in config."""
    try:
        cfg = load_model_config()
        vision_models = [cfg['research'].get('vision')]
        for k in ['vision', 'vision2', 'vision_small']:
            v = cfg['general'].get(k)
            if v: vision_models.append(v)
        return model_name in vision_models
    except Exception:
        return False


class DocumentAgent(BaseAgent):
    def __init__(self, agent_handler: Any, agent_config: AgentConfig, mime_type: str, document_agent_tools: List[Dict], file_info_header: str):
        super().__init__(agent_handler, agent_config)
        self.mime_type = mime_type
        self.document_agent_tools = document_agent_tools
        self.file_info_header = file_info_header

    def get_system_prompt(self, **kwargs) -> str:
        return DOCUMENT_AGENT_SYSTEM_PROMPT.format()

    def get_tools(self, iteration: int, task_list: Any, db_history: List[Dict]) -> List[Dict]:
        return self.document_agent_tools

    def format_user_message(self, **kwargs) -> str:
        return self.file_info_header

    def count_tool_turns(self, db_history: List[Dict], tools: List[Dict]) -> int:
        tool_names = {t["function"]["name"] for t in tools}
        return sum(
            1 for m in db_history
            if m.get("role") == "tool" and m.get("name") in tool_names
        )


async def flow_fn(
    agent: Any, 
    agent_name: str,
    file_id: str,
    query: str,
    **kwargs
) -> AsyncGenerator[str, None]:
    """Agent flow for analyzing a file and optionally synthesizing an answer."""
    logger.info(f"DocumentAgent starting: file_id='{file_id}', query='{query}'")
    start_time = time.time()
    
    log_tool_call(
        tool_name="document_agent",
        payload={"file_id": file_id, "query": query},
        response_data="Starting Document Agent flow...",
        chat_id=agent.chat_id
    )

    chat_id = agent.chat_id
    parent_message_id = agent.parent_message_id

    try:
        # Only a file of the caller's chats: another user's file (and its name and image) is "not found".
        file_meta = file_for_chat(file_id, chat_id)
        if not file_meta:
            error_msg = f"Error: File with ID {file_id} not found."
            agent.result = error_msg
            yield error_msg
            return

        mime_type = file_meta.get('mime_type', '')
        document_agent_tools = get_document_agent_tools(mime_type)
        original_filename = file_meta.get('original_filename', 'Unknown')
        stored_filename = file_meta.get('stored_filename', '')
        stored_path = os.path.join(config.FILE_STORAGE_PATH, stored_filename)

        is_image = mime_type.startswith('image/')
        
        if is_image:
            # First run/start event is logged manually for vision analysis
            existing_history = db.get_messages(
                chat_id, parent_message_id=parent_message_id,
                parent_type="document_agent"
            )
            if len(existing_history) == 0:
                db.add_message(
                    chat_id=chat_id,
                    role='event',
                    content='Document Agent Started.',
                    parent_id=parent_message_id,
                    parent_type='document_agent'
                )

            if not is_vision_model(agent.model):
                error_msg = (f"Error: The currently loaded model '{agent.model}' does not support vision. "
                           f"I cannot analyze the image '{original_filename}'. "
                           f"Please ask the user to switch to a vision-capable model.")
                agent.result = error_msg
                yield error_msg
                return

            yield f"Event: Using vision analysis for image '{original_filename}'…\n"
            
            embedding_model = get_embedding_model()
            rag_manager = RAGProvider.get_manager(
                persist_path=config.CHROMA_PATH,
                embedding_model=embedding_model
            )
            file_manager = FileManager(rag_manager=rag_manager)
            
            encoded_image, mime = file_manager.encode_file_for_vision(stored_path)
            
            if not encoded_image:
                error_msg = f"Error: Failed to encode image '{original_filename}' for vision."
                agent.result = error_msg
                yield error_msg
                return

            user_content = [
                {"type": "text", "text": f"## Query Executed:\n{query}"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded_image}"}
                }
            ]
            
            messages = [
                {"role": "system", "content": DOCUMENT_AGENT_VISION_SYSTEM_PROMPT.format()},
                {"role": "user", "content": user_content}
            ]
            
            async for chunk in agent.run_inference_step(
                agent_name="document_agent",
                messages=messages,
                model_name=agent.model,
                tools=[],
                tool_choice="none",
                thinking_budget_tokens=config.DOCUMENT_AGENT_THINKING_BUDGET
            ):
                yield chunk

            # Vision completed event
            updated_history = db.get_messages(chat_id, parent_message_id=parent_message_id, parent_type="document_agent")
            if updated_history:
                last_msg = updated_history[-1]
                agent.result = last_msg.get("content")
                if last_msg.get("role") == "assistant":
                    db.add_message(
                        chat_id=chat_id,
                        role='event',
                        content='Document Agent Completed.',
                        parent_id=parent_message_id,
                        parent_type='document_agent'
                    )
        else:
            # Autonomous Document Investigation Loop
            yield f"Event: Initiating investigation of '{original_filename}'…\n"

            if mime_type in PAGE_BASED_MIME_TYPES:
                read_hint = "This is a page-based document. Use `read_uploaded_file(page=N)` to read specific pages."
            else:
                read_hint = "This is a text/code file. Use `read_uploaded_file(start_line=X, end_line=Y)` to read specific line ranges."

            file_info_header = f"""
## File Under Investigation
- **Filename**: {original_filename}
- **File ID**: {file_id}
- **Type**: {mime_type}

## User Query / Objective
{query}

## Instructions
You are the File Agent. You must investigate the file above to satisfy the user query.
You have tools to perform semantic searches (RAG), literal searches (grep), and read specific lines/pages.

1.  **Formulate a Plan**: Use the tools to find the required information.
2.  **Verify**: If a search gives you a hint, use `read_uploaded_file` to verify the surrounding context.
    - {read_hint}
3.  **Synthesize**: Once you have all the facts, provide a comprehensive answer.

**Begin your investigation now.**
"""
            cfg = AgentConfig(
                name="document_agent",
                display_name="Document Agent",
                max_turns=config.DOCUMENT_AGENT_MAX_TURNS,
                failsafe_turns=config.DOCUMENT_AGENT_FAILSAFE_TURNS,
                max_tokens=config.DOCUMENT_AGENT_MAX_TOKENS,
                thinking_budget=config.DOCUMENT_AGENT_THINKING_BUDGET,
            )
            da = DocumentAgent(agent, cfg, mime_type, document_agent_tools, file_info_header)
            async for chunk in da.run(query=query):
                yield chunk

        if not agent.result:
            agent.result = "Error: Document agent completed but returned no content."

    except Exception as e:
        logger.error(f"Document agent failed: {e}", exc_info=True)
        log_event("document_agent_error", {"chat_id": chat_id, "error": error_detail(e)})
        error_msg = "Document agent failed. Try again."
        agent.result = error_msg
        
        # Log failure event to database
        try:
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Document Agent failed. Try again.',
                parent_id=parent_message_id,
                parent_type='document_agent'
            )
        except Exception as db_err:
            logger.error(f"Failed to log document agent failure event: {db_err}")
        yield error_msg

    finally:
        log_tool_call(
            tool_name="document_agent",
            payload={"file_id": file_id, "query": query},
            response_data=agent.result,
            chat_id=agent.chat_id,
            duration_s=time.time() - start_time
        )