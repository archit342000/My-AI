import pytest
from flask import Flask, request

from backend.utils import merge_tool_call_deltas, read_json_object

def test_merge_tool_call_deltas_new_function():
    existing = {}
    delta = {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1'}}
    merge_tool_call_deltas(existing, delta)
    assert existing == {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1'}}

def test_merge_tool_call_deltas_accumulate_arguments():
    existing = {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1'}}
    delta = {"function": {"arguments": ', "b": 2}'}}
    merge_tool_call_deltas(existing, delta)
    assert existing == {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1, "b": 2}'}}

def test_merge_tool_call_deltas_partial_delta():
    existing = {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1}'}}
    delta = {"id": "call_1"}
    merge_tool_call_deltas(existing, delta)
    assert existing == {"id": "call_1", "function": {"name": "test_tool", "arguments": '{"a": 1}'}}


# ---- read_json_object ---------------------------------------------------------------------------------------

def _read(body=None, content_type="application/json", **kwargs):
    with Flask(__name__).test_request_context(method="POST", data=body, content_type=content_type):
        data, err = read_json_object(**kwargs)
        return data, (err[0].get_json(), err[1]) if err else None


INVALID = {"error": "Request body must be a JSON object"}


def test_read_json_object_returns_a_dict_body_as_is():
    assert _read('{"a": 1}') == ({"a": 1}, None)
    assert _read("{}") == ({}, None)
    assert _read('{"a": 1}', required=False) == ({"a": 1}, None)


@pytest.mark.parametrize("body", [None, "", "  \n", "null", "[]", '""', "0", "false"])
def test_read_json_object_absent_body(body):
    assert _read(body, required=False) == ({}, None)
    data, err = _read(body, required=True)
    assert data is None and err == (INVALID, 400)


@pytest.mark.parametrize("body", ["{bad", "[1]", '"x"', "5", "true"])
@pytest.mark.parametrize("required", [True, False])
def test_read_json_object_invalid_body_is_always_an_error(body, required):
    data, err = _read(body, required=required)
    assert data is None and err == (INVALID, 400)


@pytest.mark.parametrize("required", [True, False])
def test_read_json_object_non_json_content_type_is_an_error(required):
    data, err = _read('{"a": 1}', content_type="text/plain", required=required)
    assert data is None and err == (INVALID, 400)


def test_read_json_object_merges_extra_into_the_error():
    data, err = _read("[1]", extra={"success": False})
    assert err == ({**INVALID, "success": False}, 400)


def test_read_json_object_shares_flasks_cached_parse():
    """A before_request hook that rewrites the body (as the file system blueprint does) stays visible."""
    with Flask(__name__).test_request_context(method="POST", data='{"workspace_id": "default"}', content_type="application/json"):
        request.get_json(silent=True)["workspace_id"] = "ws-1"
        data, err = read_json_object()
        assert err is None and data["workspace_id"] == "ws-1" and data is request.get_json(silent=True)


@pytest.mark.parametrize("content_type", ["application/json; charset=utf-8", "application/problem+json", "application/vnd.api+json"])
def test_read_json_object_accepts_json_content_type_variants(content_type):
    assert _read('{"a": 1}', content_type=content_type) == ({"a": 1}, None)


def test_read_json_object_accepts_a_utf8_bom_and_non_ascii_text():
    assert _read('\ufeff{"name": "café"}'.encode("utf-8")) == ({"name": "café"}, None)


def test_read_json_object_treats_absurdly_nested_json_as_invalid_not_a_crash():
    data, err = _read("[" * 200000 + "]" * 200000)
    assert data is None and err == (INVALID, 400)
