"""
Output Format Validation & Healing Module

Validates AI responses for structural formatting issues and provides two
repair strategies:

1. Contextual Splice (cheap): The AI outputs ~50 tokens of prefix context,
   the correction, and ~50 tokens of suffix context for each fix. A fuzzy
   pattern-matching algorithm locates the splice points and applies all
   patches in a single pass.

2. Full Regeneration (expensive): If the splice fails (can't locate the
   fix points), the AI is asked to regenerate the entire response from
   scratch.
"""

import json
import uuid
import re
from backend.logger import log_event


# ==================== VALIDATION ====================

def validate_output_format(full_content, full_reasoning=""):
    """
    Validates the combined output from an AI response.
    
    Returns:
        List of error dicts if issues found, empty list if valid.
        Each error dict has 'code', 'message', and optionally 'details'.
    """
    errors = []
    combined = full_content or ""
    
    # --- Check 1: Unclosed <think> tag ---
    think_count = combined.count("<think>")
    close_think_count = combined.count("</think>")
    
    if think_count > close_think_count:
        errors.append({
            "code": "MISSING_CLOSE_THINK",
            "message": (
                "Your response contains an opening <think> tag but is missing the "
                "corresponding </think> closing tag. Your reasoning block must be closed "
                "with </think> before the user-facing response begins."
            ),
            "details": f"Found {think_count} <think> tag(s) but only {close_think_count} </think> tag(s)."
        })
    
    # --- Check 2: Empty content after think block ---
    if think_count > 0 and close_think_count > 0:
        content_after_think = combined.split("</think>")[-1].strip()
        if len(content_after_think) < 5:
            errors.append({
                "code": "EMPTY_RESPONSE",
                "message": (
                    "Your response contains a reasoning block but no actual user-facing "
                    "content after the </think> tag. Please provide substantive content."
                ),
            })
    
    # --- Check 3: Completely empty response ---
    if not combined.strip() and not (full_reasoning or "").strip():
        errors.append({
            "code": "NO_OUTPUT",
            "message": "Your response was completely empty. Please generate a response."
        })
    
    return errors


# ==================== FIX PARSING ====================

def parse_fixes(ai_response):
    """
    Parse <fix> blocks from the AI's fix output.
    
    Expected format per fix:
        <fix>
        <prefix>~50 tokens before the fix point</prefix>
        <correction>the actual fix</correction>
        <suffix>~50 tokens after the fix point</suffix>
        </fix>
    
    Returns:
        List of dicts with 'prefix', 'correction', 'suffix' keys.
        Empty list if no valid fixes were parsed.
    """
    fixes = []
    fix_pattern = re.compile(r'<fix>(.*?)</fix>', re.DOTALL)
    
    for match in fix_pattern.finditer(ai_response):
        fix_block = match.group(1)
        
        prefix_match = re.search(r'<prefix>(.*?)</prefix>', fix_block, re.DOTALL)
        correction_match = re.search(r'<correction>(.*?)</correction>', fix_block, re.DOTALL)
        suffix_match = re.search(r'<suffix>(.*?)</suffix>', fix_block, re.DOTALL)
        
        if correction_match:
            suffix = suffix_match.group(1) if suffix_match else ''
            # Sanitize suffix: the model may bleed into the fabricated tool_call
            # message (same role) when generating anchors. Truncate at boundary.
            if '<tool_call>' in suffix:
                suffix = suffix.split('<tool_call>')[0]
            fixes.append({
                'prefix': prefix_match.group(1) if prefix_match else '',
                'correction': correction_match.group(1),
                'suffix': suffix
            })
    
    return fixes


# ==================== FUZZY PATTERN MATCHING ====================

def _normalize_whitespace(text):
    """Collapse all whitespace sequences into single spaces."""
    return re.sub(r'\s+', ' ', text.strip())


def _fuzzy_find(haystack, needle):
    """
    Find needle in haystack with increasing tolerance levels.
    
    Strategy:
    1. Exact substring match
    2. Whitespace-flexible regex match
    3. Longest common substring (accept if ≥70% matched)
    
    Returns:
        (start_index, end_index) in the original haystack, or None if not found.
    """
    if not needle or not needle.strip():
        return None
    
    # Level 1: Exact match
    idx = haystack.find(needle)
    if idx != -1:
        return idx, idx + len(needle)
    
    # Level 2: Whitespace-flexible match
    # Escape regex special chars, then allow flexible whitespace
    try:
        escaped = re.escape(needle)
        # Replace escaped whitespace chars with flexible \s+ pattern
        flexible = re.sub(r'(\\ |\\\n|\\\r|\\\t)+', r'\\s+', escaped)
        match = re.search(flexible, haystack)
        if match:
            return match.start(), match.end()
    except re.error:
        pass
    
    # Level 3: Longest common prefix match from each position
    # Used when the AI slightly misremembers a few characters
    norm_needle = _normalize_whitespace(needle)
    norm_haystack = _normalize_whitespace(haystack)
    
    if len(norm_needle) < 10:
        return None  # Too short for fuzzy matching
    
    best_start = None
    best_len = 0
    
    for i in range(len(norm_haystack)):
        match_len = 0
        j = 0
        while (j < len(norm_needle) and 
               i + match_len < len(norm_haystack)):
            if norm_haystack[i + match_len] == norm_needle[j]:
                match_len += 1
                j += 1
            else:
                break
        
        if match_len > best_len:
            best_len = match_len
            best_start = i
    
    # Accept if ≥70% of the needle was matched
    if best_len >= len(norm_needle) * 0.7 and best_len > 15:
        # Map back from normalized positions to original haystack positions
        # This is approximate but sufficient for our splice purposes
        orig_pos = _map_normalized_to_original(haystack, best_start, best_len)
        if orig_pos:
            return orig_pos
    
    return None


def _map_normalized_to_original(original, norm_start, norm_len):
    """
    Map a position in normalized text back to the original text.
    Returns (start, end) in original, or None.
    """
    # Walk through original text, tracking normalized position
    norm_pos = 0
    orig_start = None
    in_whitespace = False
    
    i = 0
    # Skip leading whitespace in original to match normalized
    while i < len(original) and original[i] in ' \t\n\r':
        i += 1
    
    for idx in range(i, len(original)):
        char = original[idx]
        
        if char in ' \t\n\r':
            if not in_whitespace:
                if norm_pos == norm_start and orig_start is None:
                    orig_start = idx
                norm_pos += 1
                in_whitespace = True
        else:
            in_whitespace = False
            if norm_pos == norm_start and orig_start is None:
                orig_start = idx
            norm_pos += 1
        
        if orig_start is not None and norm_pos >= norm_start + norm_len:
            return orig_start, idx + 1
    
    # Handle match at the end
    if orig_start is not None:
        return orig_start, len(original)
    
    return None


def find_fix_locations(original_content, fixes):
    """
    Find ALL fix locations in the original content WITHOUT applying them.
    
    This must be done before any fixes are applied to preserve the original
    character positions (applying a fix would shift all subsequent indices).
    
    Returns:
        List of (start, end, correction) tuples sorted by position,
        or None if any fix could not be located.
    """
    locations = []
    
    for fix in fixes:
        prefix = fix['prefix']
        correction = fix['correction']
        suffix = fix['suffix']
        
        if not prefix and not suffix:
            return None  # Need at least one anchor
        
        if prefix:
            # Find the prefix in original
            prefix_result = _fuzzy_find(original_content, prefix)
            if prefix_result is None:
                log_event("validation_fix_error", {"error": "prefix_not_found", "prefix_head": prefix[:80]})
                return None
            
            _, prefix_end = prefix_result
            
            if suffix:
                # Find suffix AFTER the prefix
                remaining = original_content[prefix_end:]
                suffix_result = _fuzzy_find(remaining, suffix)
                if suffix_result is None:
                    log_event("validation_fix_error", {"error": "suffix_not_found_after_prefix", "suffix_head": suffix[:80]})
                    return None
                
                suffix_start_in_remaining, _ = suffix_result
                # The fix replaces content between prefix_end and prefix_end + suffix_start
                fix_start = prefix_end
                fix_end = prefix_end + suffix_start_in_remaining
            else:
                # No suffix — insertion point is right after prefix
                fix_start = prefix_end
                fix_end = prefix_end
        else:
            # No prefix — find suffix and insert before it
            suffix_result = _fuzzy_find(original_content, suffix)
            if suffix_result is None:
                log_event("validation_fix_error", {"error": "suffix_not_found", "suffix_head": suffix[:80]})
                return None
            
            fix_start, _ = suffix_result
            fix_end = fix_start
        
        locations.append((fix_start, fix_end, correction))
    
    # Sort by position (ascending)
    locations.sort(key=lambda x: x[0])
    
    # Check for overlapping fixes
    for i in range(1, len(locations)):
        if locations[i][0] < locations[i-1][1]:
            log_event("validation_fix_error", {"error": "overlapping_fixes", "loc1": locations[i-1], "loc2": locations[i]})
            return None
    
    return locations


def apply_fixes(original_content, locations):
    """
    Apply all fixes to the original content.
    
    Locations must be sorted by position (ascending).
    Applies in REVERSE order to preserve character indices.
    
    Returns:
        The fixed content string.
    """
    result = original_content
    for start, end, correction in reversed(locations):
        result = result[:start] + correction + result[end:]
    return result


# ==================== MESSAGE BUILDERS ====================

def build_fix_messages(original_messages, assistant_content, validation_errors):
    """
    Build the message list for a fix attempt.
    
    Injects a fabricated tool_call on the assistant's message and a tool
    result describing the errors and the expected fix format.
    """
    tool_call_id = f"auto_fmt_{uuid.uuid4().hex[:8]}"
    
    error_lines = []
    for e in validation_errors:
        line = f"- [{e['code']}] {e['message']}"
        if e.get('details'):
            line += f"\n  Details: {e['details']}"
        error_lines.append(line)
    error_descriptions = "\n".join(error_lines)
    
    tool_result = f"""FORMAT VALIDATION FAILED. The following issues were detected in your response:

{error_descriptions}

You must fix these issues. For EACH issue, output a <fix> block containing:

<fix>
<prefix>Copy ~50 tokens (roughly 200 characters) from your previous response that appear immediately BEFORE the point needing correction. If the fix point is near the very start of the response, include only the tokens that are actually available — do NOT invent tokens.</prefix>
<correction>The exact text to insert or replace at this point (e.g., </think>).</correction>
<suffix>Copy ~50 tokens (roughly 200 characters) from your previous response that appear immediately AFTER the point needing correction. If the fix point is near the very end of the response, include only the tokens that are actually available — do NOT invent tokens.</suffix>
</fix>

Rules:
- Output ONLY the <fix> blocks. No commentary, no apologies, no explanations.
- If there are multiple issues, output multiple <fix> blocks.
- The prefix and suffix MUST be exact copies from your previous response so the system can locate the fix point.
- If fewer than 50 tokens exist before or after the fix point, use however many are available."""

    messages = list(original_messages)
    messages.append({
        "role": "assistant",
        "content": assistant_content,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": "validate_output_format",
                "arguments": "{}"
            }
        }]
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": "validate_output_format",
        "content": tool_result
    })
    
    return messages


def build_regeneration_messages(original_messages, validation_errors):
    """
    Build messages for a full regeneration after the fix attempt failed.
    """
    tool_call_id = f"auto_regen_{uuid.uuid4().hex[:8]}"
    
    error_lines = [f"- [{e['code']}] {e['message']}" for e in validation_errors]
    error_descriptions = "\n".join(error_lines)
    
    messages = list(original_messages)
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": "validate_output_format",
                "arguments": "{}"
            }
        }]
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": "validate_output_format",
        "content": f"""FORMAT VALIDATION FAILED and the previous fix attempt was unsuccessful. You must generate a COMPLETE new response from scratch.

Issues that were detected:
{error_descriptions}

Generate the full response again with correct formatting. Ensure:
- Your <think> reasoning block is properly closed with </think> before the user-facing content.
- There is meaningful content after your reasoning block.
- Do NOT reference the previous failed attempt or apologize for it. Just output the correct response."""
    })
    
    return messages
