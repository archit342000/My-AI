
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
        "description": "Visits a specific URL and extracts its visible text content using a headless browser. Supports different detail levels for optimized extraction.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to visit."
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["basic", "standard", "deep"],
                    "description": "The depth of extraction: 'basic' for clean text (fast), 'standard' for balanced data (includes tables/links), 'deep' for complex real-time dashboards (full render)."
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

INITIATE_RESEARCH_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "initiate_research_plan",
        "description": "Starts the internal Research Scout and Planning sub-process to prepare a comprehensive research strategy. This tool manages the fact-finding (scouting) and strategy design (planning) phases. Use this tool when the user provides a topic or query that requires deep research. The tool may return clarifying questions if the topic is ambiguous, or a detailed research plan if the topic is clear.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The primary research topic or question to investigate."
                },
                "edits": {
                    "type": "string",
                    "description": "OPTIONAL: Specific edits or feedback from the user to apply to a previously generated research plan. Use this when the user asks for changes to the strategy."
                }
            },
            "required": ["topic"]
        }
    }
}

EXECUTE_RESEARCH_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_research_plan",
        "description": "SYSTEM-ONLY TOOL — you are FORBIDDEN from calling this tool directly. This tool is invoked automatically by the system after a research plan is approved. Do not attempt to call this tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The research topic."
                },
                "plan": {
                    "type": "string",
                    "description": "The approved XML research plan."
                }
            },
            "required": ["topic", "plan"]
        }
    }
}

CREATE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "create_canvas",
        "description": (
            "Creates a new persistent side-panel canvas for writing or editing long-form content such as documents, reports, code, articles, plans, or structured data. "
            "The system automatically generates a unique ID for the canvas. "
            "Use this tool only for creating new canvases, not for editing existing ones. "
            "After creation, use the returned canvas_id with manage_canvas for subsequent operations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Display title for the canvas tab header."
                },
                "content": {
                    "type": "string",
                    "description": "The initial Markdown content for the canvas."
                }
            },
            "required": ["title", "content"]
        }
    }
}

MANAGE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "manage_canvas",
        "description": (
            "Manages a persistent side-panel canvas for writing or editing long-form content such as documents, reports, code, articles, plans, or structured data. "
            "Use this tool when the user requests content that benefits from an editable, persistent document view rather than inline chat response. "
            "Actions: 'replace' overwrites the entire canvas content, 'patch' replaces a targeted section identified by 'target_section', 'append' adds content to the end, 'delete_section' removes a targeted section identified by 'target_section'. "
            "Use create_canvas for creating new canvases."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["replace", "patch", "append", "delete_section"],
                    "description": "The type of modification. 'replace' to overwrite all content, 'patch' to replace a specific section, 'append' to add to the end, 'delete_section' to remove a specific section."
                },
                "id": {
                    "type": "string",
                    "description": "A stable, unique identifier for the canvas (e.g., 'market_report', 'code_review_1'). Reuse the same ID to edit an existing canvas. Get this ID from create_canvas response."
                },
                "title": {
                    "type": "string",
                    "description": "Display title for the canvas tab header."
                },
                "content": {
                    "type": "string",
                    "description": "The Markdown content to write, append, or use as a replacement."
                },
                "target_section": {
                    "type": "string",
                    "description": "Required for 'patch' and 'delete_section' actions: the exact heading text or unique string that identifies the section to replace or delete. The section is identified by the heading and extends to the next heading of equal or higher level."
                }
            },
            "required": ["action", "id", "content"]
        }
    }
}

PREVIEW_CANVASES_TOOL = {
    "type": "function",
    "function": {
        "name": "preview_canvases",
        "description": "SYSTEM-ONLY TOOL — this tool is automatically invoked by the system and you are FORBIDDEN from calling it. The system will provide canvas inventory as a tool response before your turn. Use the information from the tool response, do not attempt to call this tool.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

READ_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "read_canvas",
        "description": (
            "Reads content from a persistent canvas. Can read the full canvas or a specific section. "
            "IMPORTANT: The content returned is transient - it is available for your current reasoning but will NOT be stored in conversation history. "
            "If you need to reference the content in later turns, you must call read_canvas again. "
            "Use this tool when you need to see actual canvas content beyond the preview."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The canvas ID (e.g., '1', '2')"
                },
                "target_section": {
                    "type": "string",
                    "description": "OPTIONAL: Read only this specific section. If omitted, reads the entire canvas."
                }
            },
            "required": ["id"]
        }
    }
}

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read content from an uploaded file. Use this when the user asks about a specific file or wants to analyze its contents. For images, you can also use vision to directly analyze the file content.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The unique ID of the file to read (e.g., 'file_abc123')"
                },
                "query": {
                    "type": "string",
                    "description": "OPTIONAL: Specific question about the file content. If omitted, returns full content."
                }
            },
            "required": ["file_id"]
        }
    }
}

