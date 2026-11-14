import logging
from typing import AsyncGenerator, Any
from backend.mcp_client import playwright_client
from backend.tools.agents.visit_page_agent.prompts import VISIT_PAGE_SYSTEM_PROMPT
from backend import config
from backend.database import db

logger = logging.getLogger(__name__)

async def flow_fn(
    agent: Any, 
    agent_name: str,
    url: str, 
    query: str | None = None,
    detail_level: str = "standard",
    **kwargs
) -> AsyncGenerator[str, None]:
    """Agent flow for visiting a page and optionally synthesizing an answer."""
    logger.info(f"VisitPageAgent starting: url='{url}', query='{query}', detail_level={detail_level}")

    chat_id = agent.chat_id
    parent_message_id = agent.parent_message_id

    try:
        existing_history = db.get_messages(
            chat_id, parent_message_id=parent_message_id,
            parent_type="visit_page"
        )
        is_resume = len(existing_history) > 0

        if not is_resume:
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Started.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )
        else:
            logger.info(f"VisitPageAgent resuming: chat_id={chat_id} existing_msgs={len(existing_history)}")

        await playwright_client.connect()
        arguments = {
            "url": url,
            "max_chars": config.MAX_CHARS_VISIT_PAGE,
            "detail_level": detail_level
        }

        # 1. Execute Playwright MCP Tool (Scraping)
        result = await playwright_client.execute_tool("visit_page_tool", arguments)
        content = result.content[0].text
        
        if not content or content.startswith("Error:"):
            error_msg = content if content else "Unknown error extracting content."
            agent.result = error_msg
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Failed.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )
            yield error_msg
            return

        # The page was read: report it as a source (the page tool returns no title, so the address stands in).
        agent.sources.append({"kind": "web", "title": url, "locator": url, "detail": None})

        # 2. Raw Extraction Mode (No Query)
        if not query:
            logger.info("VisitPageAgent: No query provided, returning raw content.")
            agent.result = content
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Completed.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )
            yield content
            return

        # 3. Agent Synthesis Mode (Query Provided)
        logger.info("VisitPageAgent: Query provided, starting synthesis.")
        user_prompt = f"## Query Executed:\n{query}\n\n## Raw Extracted Text:\n{content}"
        
        messages = [
            {"role": "system", "content": VISIT_PAGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        async for chunk in agent.run_inference_step(
            agent_name="visit_page",
            messages=messages,
            model_name=agent.model,
            tools=[], # Pure synthesis, no tools
            tool_choice="none",
            max_tokens=config.VISIT_PAGE_AGENT_MAX_TOKENS,
            thinking_budget_tokens=config.VISIT_PAGE_AGENT_THINKING_BUDGET
        ):
            yield chunk

        # Retrieve the final synthesized text from the database
        updated_history = db.get_messages(
            agent.chat_id, 
            parent_message_id=agent.parent_message_id, 
            parent_type="visit_page"
        )
        if updated_history:
            last_msg = updated_history[-1]
            agent.result = last_msg.get("content", "Reading complete.")
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Completed.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )
        else:
            agent.result = "Visit page agent failed to return a response."
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Failed.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )

    except Exception as e:
        error_msg = f"Visit page failed: {str(e)}"
        logger.error(error_msg)
        agent.result = error_msg
        try:
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Visit Page Agent Failed.',
                parent_id=parent_message_id,
                parent_type='visit_page'
            )
        except Exception as db_err:
            logger.error(f"Failed to log error event to database: {db_err}")
        yield error_msg
