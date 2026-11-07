# backend/chat/tests/test_validators.py
import pytest
from backend.chat.validators import (
    validate_fs_agent_instruction,
    parse_confirmation_response,
    ValidationStatus,
)
from backend import config

def test_validate_fs_agent_instruction_pass():
    # Short instructions without embedded code or patterns should pass
    args = {"instruction": "List files in the current directory."}
    result = validate_fs_agent_instruction(args)
    assert result.status == ValidationStatus.PASS

    # Instructions specifying clipboard keys should pass even if long or containing patterns
    args_cb = {
        "instruction": "Write the following content to main.py",
        "clipboard_keys": ["cb-1234"]
    }
    result_cb = validate_fs_agent_instruction(args_cb)
    assert result_cb.status == ValidationStatus.PASS

def test_validate_fs_agent_instruction_hard_reject():
    # Length exceeding the configuration limit
    long_instruction = "x" * (config.MAX_FS_AGENT_INSTRUCTION_LENGTH + 1)
    args = {"instruction": long_instruction}
    result = validate_fs_agent_instruction(args)
    assert result.status == ValidationStatus.HARD_REJECT
    assert "REJECTED:" in result.message

def test_validate_fs_agent_instruction_soft_reject():
    # Long enough instructions (>300 chars) matching soft reject patterns
    
    # 1. Pattern: "with the following content"
    inst1 = "Please write a python script to hello.py with the following content: print('hello world') and run it immediately."
    inst1 += " " * (300 - len(inst1) + 1) # pad to ensure it meets min length
    args = {"instruction": inst1}
    result = validate_fs_agent_instruction(args)
    assert result.status == ValidationStatus.SOFT_REJECT
    assert "phrase: 'with the following content'" in result.matched_patterns

    # 2. Pattern: code block
    inst_code = "Could you create a file index.html with: \n```html\n<div>Hello</div>\n```"
    inst_code += " " * (300 - len(inst_code) + 1)
    args = {"instruction": inst_code}
    result = validate_fs_agent_instruction(args)
    assert result.status == ValidationStatus.SOFT_REJECT
    assert "code fence block (```)" in result.matched_patterns

def test_parse_confirmation_response():
    # Test True cases (PROCEED)
    assert parse_confirmation_response("PROCEED") is True
    assert parse_confirmation_response("   proceed   ") is True
    assert parse_confirmation_response("<think>I should proceed</think> PROCEED") is True
    assert parse_confirmation_response("Please PROCEED now.") is True

    # Test False cases (REWRITE)
    assert parse_confirmation_response("REWRITE") is False
    assert parse_confirmation_response("   rewrite   ") is False
    assert parse_confirmation_response("<think>Let's rewrite</think> REWRITE") is False
    assert parse_confirmation_response("I want to REWRITE the command.") is False

    # Test default case (Unparseable)
    assert parse_confirmation_response("What are you talking about?") is False
    assert parse_confirmation_response("") is False
