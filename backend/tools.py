
MANAGE_CORE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "manage_core_memory",
        "description": "Updates the core memory store. Use this to save, edit, or delete global facts, user preferences, or environmental details. ALWAYS rephrase and compress facts to be as terse as possible before saving to conserve space. Do NOT store project-specific context.",
        "parameters": {
            "type": "object",
            "properties": {
                "additions": {
                    "type": "array",
                    "description": "List of new memories to add.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The extremely concise, compressed fact to remember."
                            },
                            "tag": {
                                "type": "string",
                                "enum": ["user_preference", "user_profile", "environment_global", "explicit_fact"],
                                "description": "The category of the memory."
                            }
                        },
                        "required": ["content", "tag"]
                    }
                },
                "edits": {
                    "type": "array",
                    "description": "List of existing memories to update.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "The exact ID of the memory to edit."
                            },
                            "content": {
                                "type": "string",
                                "description": "The new, updated concise content."
                            },
                            "tag": {
                                "type": "string",
                                "enum": ["user_preference", "user_profile", "environment_global", "explicit_fact"],
                                "description": "The updated category of the memory."
                            }
                        },
                        "required": ["id", "content", "tag"]
                    }
                },
                "deletions": {
                    "type": "array",
                    "description": "List of exact memory IDs to delete (e.g., if they are outdated or contradict new information).",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": []
        }
    }
}

VISIT_PAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "visit_page_tool",
        "description": "Visits a specific URL and extracts its visible text content. Uses an initial request and falls back to a Playwright headless browser if the request fails.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to visit."
                }
            },
            "required": ["url"]
        }
    }
}

GET_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Returns the current local date and time. Use this when you need to know the current date, time, or day of the week, especially when making relative web searches. You MUST blindly trust the time provided by this tool and never rely on your own inherent 'perception' of time, as your training data lacks live temporal awareness.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

FINISH_STEP_TOOL = {
    "type": "function",
    "function": {
        "name": "finish_step",
        "description": "Call this tool mechanically when you have successfully navigated through enough pages and gathered sufficient information to fully satisfy the current step's goal.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

VALIDATE_OUTPUT_FORMAT_TOOL = {
    "type": "function",
    "function": {
        "name": "validate_output_format",
        "description": "SYSTEM-ONLY TOOL — you are FORBIDDEN from calling this tool. It runs automatically after every response to check formatting. If issues are found, you will receive a tool result describing each issue and asking you to output <fix> blocks. Each <fix> block must contain <prefix> (the ~50 tokens before the fix point, copied exactly from your response), <correction> (the fix itself), and <suffix> (the ~50 tokens after the fix point, copied exactly from your response). If the fix point is near the start or end of your response, use whatever tokens are available instead of inventing tokens. Output ONLY the <fix> blocks with no commentary.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
