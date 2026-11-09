"""Helpers for editing a stored user message without losing its images or attachment note."""
import json

# The router appends this block to a user message that has file attachments (router.py chat_completions;
# the React transcript strips it for display with splitAttachmentNote in frontend/src/lib/chat-model.ts).
# The full prefix is used, not just "[System Note:", so text a user types is never taken for the router note.
NOTE_MARKER = "\n\n[System Note: The user has attached the following files"


def _split_note(text: str) -> tuple[str, str]:
    """Return (text before the trailing attachment note, the note itself or "")."""
    index = text.rfind(NOTE_MARKER)
    if index < 0:
        return text, ""
    return text[:index], text[index:]


def _with_note(new_text: str, note: str) -> str:
    """Append the attachment `note` to `new_text`, unless there is no note or `new_text` already contains one."""
    if not note or NOTE_MARKER in new_text:
        return new_text
    return new_text + note


_PART_TYPES = ("text", "image_url")


def _parse_parts(content: str):
    """
    Return the content parts if `content` is a stored multimodal message, else None.
    That is a non-empty JSON list whose items are all objects of type "text" or "image_url", the
    only shape the router writes; anything else (including plain text that looks like JSON) is plain.
    """
    try:
        parts = json.loads(content)
    except (TypeError, ValueError):
        return None
    if isinstance(parts, list) and parts and all(isinstance(part, dict) and part.get("type") in _PART_TYPES for part in parts):
        return parts
    return None


def merge_edited_user_content(old_content: str, new_text: str) -> str:
    """
    Build the stored content for an edited user message.

    The editor only holds the message text, so the rest of the stored message has to be carried over:
    - Multimodal content (a JSON list of parts): the first text part gets `new_text`; every other part
      (images) is kept in order. A text part is inserted when there is none. The router writes at most
      one text part per message, so only the first is replaced.
    - Plain content: `new_text` is used as is.
    In both cases a trailing "[System Note: ...]" attachment note on the old text is re-appended
    unless `new_text` already contains one, so the model still gets the attached file ids.
    """
    parts = _parse_parts(old_content)
    if parts is None:
        _, note = _split_note(old_content or "")
        return _with_note(new_text, note)

    for part in parts:
        if part.get("type") == "text":
            _, note = _split_note(str(part.get("text", "")))
            part["text"] = _with_note(new_text, note)
            break
    else:
        parts.insert(0, {"type": "text", "text": new_text})
    return json.dumps(parts)
