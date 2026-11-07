# backend/chat/validators.py
"""
Pre-dispatch validation for tool call arguments.
Enforces clipboard compliance through deterministic checks (hard rejection)
and pattern-based heuristics with AI confirmation (soft rejection).
"""
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from backend import config
from backend.logging import log_event

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    PASS = "pass"
    HARD_REJECT = "hard_reject"
    SOFT_REJECT = "soft_reject"


@dataclass
class ValidationResult:
    """Outcome of a pre-dispatch validation check."""
    status: ValidationStatus
    message: str = ""
    matched_patterns: List[str] = field(default_factory=list)


# ── Regex Patterns for Soft Rejection ───────────────────────────────

_SOFT_REJECT_PATTERNS: List[tuple] = [
    (re.compile(r'(?:with|using|containing)\s+(?:the\s+)?following\s+content', re.IGNORECASE),
     "phrase: 'with the following content'"),

    (re.compile(r'(?:write|create|save|put|add)\s+(?:the\s+)?following\s+(?:code|text|content|data)', re.IGNORECASE),
     "phrase: 'write/create the following code/text'"),

    (re.compile(r'(?:here\s+is|here\'s)\s+(?:the\s+)?(?:content|code|text|file)', re.IGNORECASE),
     "phrase: 'here is the content/code'"),

    (re.compile(r'(?:exactly|verbatim)\s+as\s+(?:follows|shown|written|below)', re.IGNORECASE),
     "phrase: 'verbatim/exactly as follows'"),

    (re.compile(r'content\s*(?:is|should\s+be|=)\s*[:\n\r]', re.IGNORECASE),
     "phrase: 'content is/should be:' followed by block"),

    (re.compile(r'(?:paste|insert|place)\s+(?:this|the\s+following)\s+(?:into|in|at)', re.IGNORECASE),
     "phrase: 'paste/insert this into'"),

    (re.compile(r'(?:with|having)\s+(?:this|these)\s+(?:exact|specific)\s+contents?', re.IGNORECASE),
     "phrase: 'with this exact content'"),

    (re.compile(r'```[\s\S]*?```', re.DOTALL),
     "code fence block (```)"),
]

_SOFT_REJECT_MIN_LENGTH = 300


def validate_fs_agent_instruction(args: Dict[str, Any]) -> ValidationResult:
    """
    Validates the file_system_agent tool call arguments.
    Returns ValidationResult with status pass, hard_reject, or soft_reject.
    """
    instruction = args.get("instruction", "")
    clipboard_keys = args.get("clipboard_keys") or []
    instruction_len = len(instruction)

    # ── Tier 1: Hard length limit ─────────────────────────────────
    if instruction_len > config.MAX_FS_AGENT_INSTRUCTION_LENGTH:
        log_event("clipboard_enforcement_hard_reject", {
            "instruction_length": instruction_len,
            "threshold": config.MAX_FS_AGENT_INSTRUCTION_LENGTH,
            "has_clipboard_keys": bool(clipboard_keys),
        })
        return ValidationResult(
            status=ValidationStatus.HARD_REJECT,
            message=(
                f"REJECTED: Your instruction is {instruction_len:,} characters, "
                f"exceeding the {config.MAX_FS_AGENT_INSTRUCTION_LENGTH:,}-character limit. "
                f"This usually means you embedded verbatim content directly.\n"
                f"You MUST:\n"
                f"1. Call clipboard_write(content=<the verbatim content>) to get a cb-... key.\n"
                f"2. Call file_system_agent(instruction=<short task description>, "
                f"clipboard_keys=[<the key>]).\n"
                f"Do NOT embed code, file contents, or large text blocks in the instruction."
            ),
        )

    # ── Tier 2: Soft rejection (regex + heuristics) ───────────────
    # Skip if clipboard_keys provided — AI is already using the flow correctly
    if not clipboard_keys and instruction_len >= _SOFT_REJECT_MIN_LENGTH:
        matched = _detect_content_patterns(instruction)
        if matched:
            pattern_descriptions = [desc for _, desc in matched]
            log_event("clipboard_enforcement_soft_reject", {
                "instruction_length": instruction_len,
                "matched_patterns": pattern_descriptions,
            })
            patterns_str = "; ".join(pattern_descriptions)
            return ValidationResult(
                status=ValidationStatus.SOFT_REJECT,
                message=(
                    f"[SOFT REJECT] Your file_system_agent instruction triggered "
                    f"content-embedding detection.\n"
                    f"Detected patterns: {patterns_str}\n\n"
                    f"If your instruction contains verbatim code/text that should be "
                    f"transferred via clipboard_write, respond with exactly: REWRITE\n"
                    f"If this is a legitimate task description that does NOT contain "
                    f"embedded content, respond with exactly: PROCEED\n\n"
                    f"You must respond with ONLY one of these two words."
                ),
                matched_patterns=pattern_descriptions,
            )

    return ValidationResult(status=ValidationStatus.PASS)


def parse_confirmation_response(response_text: str) -> bool:
    """
    Parses the AI's in-conversation confirmation response.
    Returns True for PROCEED, False for REWRITE.
    Conservative default: unparseable → False (reject).
    """
    cleaned = response_text.strip().upper()
    think_pattern = re.compile(r'<think>.*?</think>', re.DOTALL)
    cleaned = think_pattern.sub('', cleaned).strip()

    if "PROCEED" in cleaned:
        return True
    if "REWRITE" in cleaned:
        return False

    logger.warning(
        f"[VALIDATOR] Unparseable confirmation: '{response_text[:100]}'. "
        f"Defaulting to REWRITE."
    )
    return False


def _detect_content_patterns(instruction: str) -> List[tuple]:
    """Returns list of (pattern, description) for all matching patterns."""
    return [
        (pattern, desc)
        for pattern, desc in _SOFT_REJECT_PATTERNS
        if pattern.search(instruction)
    ]
