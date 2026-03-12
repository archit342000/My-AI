import asyncio
import logging
import base64
import json
import os
import aiohttp
from playwright.async_api import async_playwright
import websockets

logger = logging.getLogger("browser_agent")

active_tasks = {}
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://host.docker.internal:1234/v1")

def add_interrupt_message(task_id: str, message: str):
    if task_id in active_tasks:
        active_tasks[task_id]["interrupts"].append(message)

async def stream_screenshots(page, websocket_clients):
    while True:
        try:
            if not websocket_clients:
                await asyncio.sleep(0.5)
                continue

            # Use lower quality jpeg for fast streaming
            screenshot = await page.screenshot(type="jpeg", quality=40)
            b64 = base64.b64encode(screenshot).decode('utf-8')
            payload = json.dumps({"image": f"data:image/jpeg;base64,{b64}"})

            # Broadcast
            disconnected = set()
            for ws in websocket_clients:
                try:
                    await ws.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(ws)

            websocket_clients.difference_update(disconnected)
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Screenshot stream error: {e}")
            await asyncio.sleep(1)

async def call_llm(messages, tools):
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": "qwen2.5-vl-7b-instruct", # Assume vision model
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 1024
        }

        try:
            async with session.post(f"{LM_STUDIO_URL}/chat/completions", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"LLM API Error: {resp.status} - {text}")
                    return None

                data = await resp.json()
                return data['choices'][0]['message']
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None

def get_browser_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "goto_url",
                "description": "Navigate the browser to a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to navigate to (e.g. https://google.com)"}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "click_element",
                "description": "Click an element on the page using a CSS selector or text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector to click"}
                    },
                    "required": ["selector"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "type_text",
                "description": "Type text into an input field.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector of the input field"},
                        "text": {"type": "string", "description": "Text to type"}
                    },
                    "required": ["selector", "text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "press_key",
                "description": "Press a key on the keyboard (e.g. 'Enter').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "The key to press"}
                    },
                    "required": ["key"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": "Ask the user for help, 2FA codes, or clarification, pausing execution until they reply.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "The question to ask the user"}
                    },
                    "required": ["question"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finish_task",
                "description": "Call this when the goal has been successfully achieved or is impossible.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "result": {"type": "string", "description": "Summary of what was achieved or why it failed"}
                    },
                    "required": ["result"]
                }
            }
        }
    ]

async def run_browser_task(task_id: str, goal: str, mode: str):
    from .server import connected_clients

    active_tasks[task_id] = {"interrupts": [], "status": "running"}

    # Ensure URL formatting
    import re
    if not goal.startswith("http") and re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", goal):
        initial_url = f"https://{goal}"
        goal_text = f"Navigate to {initial_url} and explore"
    else:
        initial_url = None
        goal_text = goal

    system_prompt = f"""You are an autonomous browser agent. Your goal is: {goal_text}
You control a Chromium browser. You will be provided with a screenshot of the current page.
Observe the page and use the tools provided to navigate, click, and type to achieve the goal.
If you need user input (like a 2FA code or login credentials), use the `ask_user` tool.
Once the goal is complete, use the `finish_task` tool.
Do not hallucinate selectors. Guess reasonable selectors if they are obvious (like input[type='text'], button, etc) or use text selectors (e.g., text='Login').
"""

    messages = [{"role": "system", "content": system_prompt}]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Start screenshot streamer
        stream_task = asyncio.create_task(stream_screenshots(page, connected_clients))

        try:
            if initial_url:
                await page.goto(initial_url, wait_until="domcontentloaded", timeout=30000)
            else:
                await page.goto("https://www.google.com", wait_until="domcontentloaded")

            await asyncio.sleep(2)

            max_steps = 30
            step = 0

            while step < max_steps:
                step += 1

                # Check for user interrupts
                if active_tasks[task_id]["interrupts"]:
                    interrupt_msg = active_tasks[task_id]["interrupts"].pop(0)
                    logger.info(f"Task {task_id} interrupted: {interrupt_msg}")

                    messages.append({
                        "role": "user",
                        "content": f"USER INTERRUPTION/GUIDANCE: {interrupt_msg}. Adjust your actions based on this."
                    })
                else:
                    # Take screenshot for the LLM
                    try:
                        screenshot = await page.screenshot(type="jpeg", quality=70)
                        b64 = base64.b64encode(screenshot).decode('utf-8')

                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Here is the current browser screen. What is the next step to achieve the goal?"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                            ]
                        })
                    except Exception as e:
                        logger.error(f"Failed to capture screenshot for LLM: {e}")
                        messages.append({"role": "user", "content": f"Failed to get screenshot. Current URL: {page.url}"})

                # Call LLM
                response = await call_llm(messages, get_browser_tools())

                if not response:
                    return "Error communicating with LLM vision model."

                messages.append(response) # Add assistant response to history

                # Handle tool calls
                if "tool_calls" in response and response["tool_calls"]:
                    for tool_call in response["tool_calls"]:
                        fn_name = tool_call["function"]["name"]
                        try:
                            args = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        logger.info(f"LLM executing: {fn_name}({args})")

                        tool_result = ""

                        try:
                            if fn_name == "goto_url":
                                await page.goto(args.get("url"), wait_until="domcontentloaded", timeout=30000)
                                await asyncio.sleep(2)
                                tool_result = f"Navigated to {page.url}"

                            elif fn_name == "click_element":
                                selector = args.get("selector")
                                await page.click(selector, timeout=5000)
                                await asyncio.sleep(1)
                                tool_result = f"Clicked {selector}"

                            elif fn_name == "type_text":
                                selector = args.get("selector")
                                text = args.get("text")
                                await page.fill(selector, text, timeout=5000)
                                await asyncio.sleep(0.5)
                                tool_result = f"Typed text into {selector}"

                            elif fn_name == "press_key":
                                key = args.get("key")
                                await page.keyboard.press(key)
                                await asyncio.sleep(1)
                                tool_result = f"Pressed {key}"

                            elif fn_name == "ask_user":
                                question = args.get("question")
                                tool_result = f"Paused for user input. The user sees: '{question}'"
                                # We return this directly to the main chat so the user can answer
                                return f"BROWSER PAUSED FOR INPUT: {question}"

                            elif fn_name == "finish_task":
                                result = args.get("result")
                                return f"Browser task completed: {result}"

                        except Exception as e:
                            tool_result = f"Error executing tool: {str(e)}"
                            logger.warning(tool_result)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_result
                        })
                else:
                    # No tool calls, LLM just responded with text
                    content = response.get("content", "")
                    if mode == "semi-automatic":
                        return f"Browser agent says: {content}. Awaiting further instruction."
                    else:
                        messages.append({
                            "role": "user",
                            "content": "You must use a tool to interact with the browser or finish the task."
                        })

                # Cleanup old images from history to save context window
                # Keep only system prompt and last 4 turns
                if len(messages) > 10:
                    new_messages = [messages[0]]
                    new_messages.extend(messages[-6:])
                    messages = new_messages

            return "Task failed: Exceeded maximum steps (30) without finishing."

        except Exception as e:
            logger.error(f"Browser task error: {e}")
            return f"Browser task failed due to error: {str(e)}"

        finally:
            stream_task.cancel()
            await browser.close()
            if task_id in active_tasks:
                del active_tasks[task_id]
