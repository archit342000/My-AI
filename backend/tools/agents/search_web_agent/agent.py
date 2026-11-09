import json
import logging
import asyncio
from typing import AsyncGenerator, Any
from backend.database import db
from backend.mcp_client import tavily_client
from backend.tools.agents.search_web_agent.prompts import SEARCH_AGENT_SYSTEM_PROMPT
from backend import config
from backend.auth.rate_limit import check_search_limit

logger = logging.getLogger(__name__)

async def flow_fn(
    agent: Any, 
    agent_name: str,
    query: str, 
    topic: str = "general", 
    time_range: str | None = None,
    context: str = "Provide a comprehensive and accurate summary of the search results.",
    return_raw_results: bool = False,
    depth: str = "normal",
    **kwargs
) -> AsyncGenerator[str, None]:
    """
    Executes a web search and, if not bypassed, synthesizes the result.
    """
    logger.info(f"SearchWebAgent starting: query='{query}', time_range={time_range}, depth={depth}, return_raw_results={return_raw_results}")

    chat_id = agent.chat_id
    parent_message_id = agent.parent_message_id

    try:
        existing_history = db.get_messages(
            chat_id, parent_message_id=parent_message_id,
            parent_type="search_web"
        )
        is_resume = len(existing_history) > 0

        if not is_resume:
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Started.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
        else:
            logger.info(f"SearchWebAgent resuming: chat_id={chat_id} existing_msgs={len(existing_history)}")

        # One search is one hit against the chat owner's daily limit, however many retries it needs.
        limit_message = check_search_limit(chat_id)
        if limit_message:
            agent.result = limit_message
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Failed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
            yield limit_message
            return

        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Step 1: Execute the raw search via MCP
                await tavily_client.connect()

                arguments = {
                    "query": query, 
                    "max_results": config.MAX_SEARCH_RESULTS,
                    "depth": depth
                }
                if topic == "news":
                    arguments["topic"] = "news"
                if time_range:
                    arguments["time_range"] = time_range

                result = await asyncio.wait_for(
                    tavily_client.execute_tool("async_tavily_search_tool", arguments),
                    timeout=config.TIMEOUT_TAVILY_SEARCH_ASYNC
                )
                # Success — break out of retry loop
                last_error = None
                break
                
            except Exception as e:
                last_error = e
                logger.warning(f"search_web attempt {attempt+1}/{max_retries+1} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep((attempt + 1) * 1.0)
        
        if last_error:
            error_msg = f"Search failed after {max_retries+1} attempts: {str(last_error)}"
            agent.result = error_msg
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Failed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
            yield error_msg
            return

        content = result.content[0].text
        res_json = json.loads(content)
        answer = res_json.get("answer", "")
        results = res_json.get("results", [])
        
        if not results and not answer:
            agent.result = "No results found for this query."
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Completed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
            yield agent.result
            return
            
        # Optimization: If depth is "normal", return Tavily's answer or the formatted results directly.
        # This bypasses the expensive and slow LLM synthesis phase for all "normal" queries.
        if depth == "normal":
            if answer:
                logger.info("SearchWebAgent: Using Tavily's native answer (depth='normal').")
                agent.result = answer
                db.add_message(
                    chat_id=chat_id,
                    role='event',
                    content='Search Web Agent Completed.',
                    parent_id=parent_message_id,
                    parent_type='search_web'
                )
                yield answer
                return
            else:
                logger.info("SearchWebAgent: Using Tavily's results snippets (depth='normal', no answer).")
                # Format snippets into a readable string
                formatted_results = ""
                for r in results:
                    url = r.get("url")
                    title = r.get("title", "No Title")
                    content = r.get("content", "")
                    if len(content) > config.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT:
                        content = content[:config.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT] + "\n[... Content truncated due to length ...]"
                    formatted_results += f"\n---\nTitle: {title}\nURL: {url}\n{content}\n"
                
                agent.result = formatted_results
                db.add_message(
                    chat_id=chat_id,
                    role='event',
                    content='Search Web Agent Completed.',
                    parent_id=parent_message_id,
                    parent_type='search_web'
                )
                yield formatted_results
                return

        raw_results_str = ""
        for r in results:
            url = r.get("url")
            snip = r.get("raw_content", r.get("content", ""))
            if snip:
                if len(snip) > config.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT:
                    snip = snip[:config.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT] + "\n[... Content truncated due to length ...]"
                raw_results_str += f"\n---\n[Source]: {url}\n{snip}\n"
                
        # Step 2: Return early if raw results are requested
        if return_raw_results:
            agent.result = raw_results_str
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Completed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
            yield raw_results_str
            return

        # Step 3: Synthesize the results using a single inference step
        user_prompt = f"""
## Input Data

**Query Executed:** {query}

**Context (What to extract):** {context}

**Raw Results:**
{raw_results_str}
"""
        messages = [
            {"role": "system", "content": SEARCH_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        async for chunk in agent.run_inference_step(
            agent_name="search_web",
            messages=messages,
            model_name=agent.model,
            tools=[], # No tools allowed for the synthesizer
            tool_choice="none",
            max_tokens=config.SEARCH_WEB_AGENT_MAX_TOKENS,
            thinking_budget_tokens=config.SEARCH_WEB_AGENT_THINKING_BUDGET
        ):
            yield chunk
            
        updated_history = db.get_messages(
            agent.chat_id, 
            parent_message_id=agent.parent_message_id, 
            parent_type="search_web"
        )
        if updated_history:
            last_msg = updated_history[-1]
            agent.result = last_msg.get("content", "Search complete.")
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Completed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
        else:
            agent.result = "Search agent failed to return a response."
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Failed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
            
        logger.info(f"SearchWebAgent synthesis complete.")

    except Exception as e:
        logger.error(f"SearchWebAgent failed: {e}", exc_info=True)
        error_msg = f"Search failed: {str(e)}"
        agent.result = error_msg
        try:
            db.add_message(
                chat_id=chat_id,
                role='event',
                content='Search Web Agent Failed.',
                parent_id=parent_message_id,
                parent_type='search_web'
            )
        except Exception as db_err:
            logger.error(f"Failed to log search agent failure event: {db_err}")
        yield error_msg