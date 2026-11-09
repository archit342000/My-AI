# backend/chat/tests/test_prompt_builder.py
import pytest
from unittest.mock import MagicMock, patch
from backend.chat.prompt_builder import PromptBuilder, PromptContext
from backend.prompts import PromptLoader

def test_prompt_builder_default():
    ctx = PromptContext(chat_metadata={})
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert PromptLoader.load_template("core_personality").strip() in prompt
    assert PromptLoader.load_template("formatting_rules").strip() in prompt
    assert PromptLoader.load_template("reasoning_template").strip() in prompt
    assert PromptLoader.load_template("main_ai_task_rules").strip() in prompt
    assert PromptLoader.load_template("research_mode_rules").strip() not in prompt

def test_prompt_builder_research_mode():
    ctx = PromptContext(chat_metadata={"research_mode": 1})
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert PromptLoader.load_template("research_mode_rules").strip() in prompt
    assert PromptLoader.load_template("main_ai_task_rules").strip() not in prompt

def test_prompt_builder_user_preferences():
    preferences = [
        {"id": "p1", "tag": "preference", "content": "Likes dark mode"},
        {"id": "p2", "tag": "personal_info", "content": "Born in Seattle"}
    ]
    ctx = PromptContext(chat_metadata={"user_preferences": 1}, preferences=preferences)
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert PromptLoader.load_template("user_preferences_rules").strip() in prompt
    assert "# Current User Preferences & Profile" in prompt
    assert "- [p1] (preference) Likes dark mode" in prompt
    assert "- [p2] (personal_info) Born in Seattle" in prompt

def test_prompt_builder_mode_directives():
    ctx = PromptContext(chat_metadata={
        "file_system_mode": 1,
        "git_mode": 1,
        "code_execution_mode": 1
    })
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert PromptLoader.load_template("directives/file_system_agent").strip() in prompt
    assert PromptLoader.load_template("directives/git_agent").strip() in prompt
    assert PromptLoader.load_template("directives/run_code").strip() in prompt


def test_prompt_builder_persona_snapshot():
    ctx = PromptContext(chat_metadata={"persona_snapshot": "Adopt a pirate persona."})
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert "# User-Defined Persona/Role" in prompt
    assert "<user_persona>\nAdopt a pirate persona.\n</user_persona>" in prompt

@patch('backend.database.db.get_persona')
def test_prompt_builder_persona_id_fallback(mock_get_persona):
    mock_get_persona.return_value = {"content": "Adopt a ninja persona."}
    ctx = PromptContext(chat_metadata={"persona_id": "ninja_id", "user_id": "owner-1"})
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert "<user_persona>\nAdopt a ninja persona.\n</user_persona>" in prompt
    mock_get_persona.assert_called_once_with("ninja_id", "owner-1")  # looked up among the chat owner's personas

@patch('backend.database.db.get_persona')
def test_prompt_builder_persona_fallback_needs_an_owner(mock_get_persona):
    ctx = PromptContext(chat_metadata={"persona_id": "ninja_id"})  # no user_id on the chat row
    assert "ninja" not in PromptBuilder(ctx).build()
    mock_get_persona.assert_not_called()

def test_prompt_builder_system_prompt_fallback():
    ctx = PromptContext(chat_metadata={"system_prompt": "Adopt a wizard persona."})
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert "<user_persona>\nAdopt a wizard persona.\n</user_persona>" in prompt

def test_prompt_builder_skills():
    skills = [
        {"name": "skill1", "description": "Doing task 1"},
        {"name": "skill2", "description": "Doing task 2"}
    ]
    ctx = PromptContext(chat_metadata={}, skills=skills)
    builder = PromptBuilder(ctx)
    prompt = builder.build()
    
    assert "# Available Skills" in prompt
    assert "- /skill1: Doing task 1" in prompt
    assert "- /skill2: Doing task 2" in prompt
