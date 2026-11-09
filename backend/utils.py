"""Small shared helpers for the backend: tool-call delta merging and request body reading."""
import json

from flask import jsonify, request


def merge_tool_call_deltas(existing: dict, delta: dict) -> None:
    """
    In-place merges a tool call delta chunk into the existing accumulated tool call.
    """
    if 'function' in delta:
        if 'function' not in existing:
            existing['function'] = {}
        if 'arguments' in delta['function']:
            existing['function']['arguments'] = (existing['function'].get('arguments') or '') + (delta['function'].get('arguments') or '')
        if 'name' in delta['function']:
            existing['function']['name'] = delta['function']['name']
    if 'id' in delta:
        existing['id'] = delta['id']


def read_json_object(required: bool = True, extra: dict | None = None) -> tuple[dict | None, tuple | None]:
    """
    Reads the JSON object body of the current Flask request without raising.

    A body that is not JSON (wrong content type or malformed) and a JSON value that is not an object
    become a 400 `{"error": "Request body must be a JSON object"}` instead of Flask's HTML 400/415 page
    or an AttributeError on `.get`. An absent body (nothing, whitespace, `null`, `[]`, `""`, `0`, `false`)
    is an error when `required` is True and `{}` when it is False, for routes whose fields are all
    optional (this deliberately accepts a body-less call, which Flask's `request.json` used to reject).
    The returned dict is Flask's cached parse, so changes made by a `before_request` hook stay visible.

    Args:
        required: True when the route needs a body; an absent body is then an error.
        extra: Extra keys for the error body, e.g. `{"success": False}` for the personas and skills routes.

    Returns:
        `(data, None)` on success, or `(None, (response, 400))` for a route to return as is.
    """
    def error():
        return None, (jsonify({"error": "Request body must be a JSON object", **(extra or {})}), 400)

    raw = request.get_data(cache=True)
    if raw.strip():
        if not request.is_json:
            return error()
        try:
            data = request.get_json(silent=True)
            if data is None:
                json.loads(raw)    # raises for malformed JSON; the literal `null` passes and counts as absent
        except (ValueError, RecursionError):
            return error()
        if isinstance(data, dict):
            return data, None
        if data:                   # [1], "x", 5, true: a value, but not an object
            return error()
    # absent: nothing, `null`, [], "", 0, false
    return error() if required else ({}, None)
