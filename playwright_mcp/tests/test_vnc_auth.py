"""Tests for the websockify auth plugin of the portal VNC (websockify itself is only present in the container)."""
import base64
import importlib
import sys
import types

import pytest


class FakeAuthenticationError(Exception):
    def __init__(self, response_code=403, response_msg="Forbidden"):
        self.code = response_code
        self.msg = response_msg


@pytest.fixture
def plugin_cls(monkeypatch):
    pkg = types.ModuleType("websockify")
    mod = types.ModuleType("websockify.auth_plugins")
    mod.AuthenticationError = FakeAuthenticationError
    pkg.auth_plugins = mod
    monkeypatch.setitem(sys.modules, "websockify", pkg)
    monkeypatch.setitem(sys.modules, "websockify.auth_plugins", mod)
    monkeypatch.delitem(sys.modules, "playwright_mcp.vnc_auth", raising=False)   # restored on teardown
    return importlib.import_module("playwright_mcp.vnc_auth").ApiKeyBasicAuth


def _basic(user, password):
    raw = user if isinstance(user, bytes) else user.encode()
    pw = password if isinstance(password, bytes) else password.encode()
    return {"Authorization": "Basic " + base64.b64encode(raw + b":" + pw).decode()}


@pytest.fixture
def key_file(tmp_path):
    f = tmp_path / "key"
    f.write_text("s3cret\n")
    return str(f)


def _rejected(auth, headers):
    with pytest.raises(FakeAuthenticationError) as e:
        auth.authenticate(headers, "localhost", 5900)
    return e.value.code == 401


def test_the_right_password_is_accepted_whatever_the_username(plugin_cls, key_file):
    auth = plugin_cls(key_file)
    assert auth.authenticate(_basic("portal", "s3cret"), "h", 1) is None
    assert auth.authenticate(_basic("anyone", "s3cret"), "h", 1) is None


@pytest.mark.parametrize("headers", [
    _basic("portal", "wrong"),
    _basic("portal", "s3cre"),                      # shorter
    _basic("portal", "s3cret-and-more"),            # longer
    _basic("portal", "sécret".encode("utf-8")),     # non-ASCII
    _basic("portal", b"\xff\xfe"),                  # not UTF-8
    {},                                             # no header
    {"Authorization": "Bearer s3cret"},             # other scheme
    {"Authorization": "Basic !!!not-base64!!!"},    # bad base64
    {"Authorization": "Basic " + base64.b64encode(b"no-colon-here").decode()},
])
def test_everything_else_is_rejected_with_401(plugin_cls, key_file, headers):
    assert _rejected(plugin_cls(key_file), headers)


def test_a_missing_or_empty_key_file_rejects_everything(plugin_cls, tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("\n")
    for path in (str(tmp_path / "does-not-exist"), str(empty)):
        auth = plugin_cls(path)
        assert _rejected(auth, _basic("portal", ""))
        assert _rejected(auth, _basic("portal", "anything"))


def test_a_rotated_key_is_picked_up_without_a_restart(plugin_cls, tmp_path):
    f = tmp_path / "key"
    f.write_text("old")
    auth = plugin_cls(str(f))
    assert auth.authenticate(_basic("p", "old"), "h", 1) is None
    f.write_text("new")
    assert _rejected(auth, _basic("p", "old"))
    assert auth.authenticate(_basic("p", "new"), "h", 1) is None


@pytest.mark.parametrize("scheme", ["Basic", "basic", "BASIC"])
def test_the_scheme_is_case_insensitive(plugin_cls, key_file, scheme):
    headers = {"Authorization": scheme + " " + _basic("portal", "s3cret")["Authorization"].split(" ", 1)[1]}
    assert plugin_cls(key_file).authenticate(headers, "h", 1) is None


def test_an_empty_username_and_a_colon_in_the_password(plugin_cls, tmp_path):
    f = tmp_path / "key"
    f.write_text("pa:ss:word")
    auth = plugin_cls(str(f))
    assert auth.authenticate(_basic("", "pa:ss:word"), "h", 1) is None        # username is ignored, may be empty
    assert auth.authenticate(_basic("portal", "pa:ss:word"), "h", 1) is None  # only the first colon splits
    assert _rejected(auth, _basic("portal", "pa"))


@pytest.mark.parametrize("header", [
    "Basic",                                                         # no token
    "Basic ",                                                        # empty token
    "Basic " + base64.b64encode(b"portal:s3cret").decode().rstrip("="),   # unpadded base64 (rejected)
    "Basic  " + base64.b64encode(b"portal:wrong").decode(),          # extra space then a wrong password
])
def test_malformed_basic_headers_are_rejected(plugin_cls, key_file, header):
    assert _rejected(plugin_cls(key_file), {"Authorization": header})

