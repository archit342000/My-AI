"""
Tool implementation for fetching skill details.
The actual instruction injection is performed in-memory during history compilation.
"""
import logging
from typing import Optional
from backend.database import db
from backend.logging import log_event

logger = logging.getLogger(__name__)


def get_skill_details(skill_name: str, user_id: Optional[str] = None, **kwargs) -> str:
    """
    Retrieves a skill's details by name, among the chat owner's skills (`user_id` is injected by the server).
    Returns a success message if the skill exists, allowing the history compiler
    to dynamically inject the full instructions, or an error message if not found.
    """
    if not user_id:
        log_event("tool_missing_owner", {"tool": "get_skill_details"})
        return "Error: get_skill_details could not run because the chat has no owner."
    logger.info(f"Retrieving details for skill: {skill_name}")
    skill = db.get_skill_by_name(skill_name, user_id)
    if not skill:
        logger.warning(f"Skill '{skill_name}' not found in database.")
        return f"Error: Skill '{skill_name}' not found."

    return f"Successfully loaded skill details for '{skill_name}'."
