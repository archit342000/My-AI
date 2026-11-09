import pytest
import os
from unittest.mock import patch, mock_open
import importlib

@pytest.fixture
def clean_env():
    # Clear relevant env vars to ensure clean test state
    vars_to_clear = ["DATA_DIR"]
    old_values = {v: os.environ.get(v) for v in vars_to_clear}
    for v in vars_to_clear:
        if v in os.environ:
            del os.environ[v]
    yield
    # Restore env vars
    for v, val in old_values.items():
        if val is not None:
            os.environ[v] = val

def test_get_secret_env(clean_env):
    from backend.config import get_secret
    with patch.dict(os.environ, {"MY_SECRET": "value123"}):
        assert get_secret("MY_SECRET") == "value123"

def test_get_secret_file(clean_env):
    from backend.config import get_secret
    # Mocking open for /run/secrets/
    with patch("builtins.open", mock_open(read_data="secret_from_file")):
        assert get_secret("MY_FILE_SECRET") == "secret_from_file"

def test_config_paths(clean_env):
    import backend.config
    with patch.dict(os.environ, {"DATA_DIR": "/tmp/my-data"}):
        with patch("os.makedirs"):
            importlib.reload(backend.config)
            assert backend.config.DATA_DIR == "/tmp/my-data"


# --- validate_auth_config ---

def _auth(**over):
    base = {"AUTH_PROVIDER": "cloudflare_access", "ADMIN_EMAIL": "a@x.io",
            "CF_ACCESS_TEAM_DOMAIN": "t.cloudflareaccess.com", "CF_ACCESS_AUD": "aud",
            "AUTH_STATIC_EMAIL": ""}
    base.update(over)
    return patch.multiple("backend.config", **base)


def test_validate_auth_config_cloudflare_ok():
    from backend.config import validate_auth_config
    with _auth():
        validate_auth_config()


def test_validate_auth_config_static_ok():
    from backend.config import validate_auth_config
    with _auth(AUTH_PROVIDER="static", AUTH_STATIC_EMAIL="a@x.io", CF_ACCESS_TEAM_DOMAIN="", CF_ACCESS_AUD=""):
        validate_auth_config()


@pytest.mark.parametrize("over,msg", [
    ({"AUTH_PROVIDER": "basic"}, "AUTH_PROVIDER"),
    ({"ADMIN_EMAIL": ""}, "ADMIN_EMAIL"),
    ({"CF_ACCESS_TEAM_DOMAIN": ""}, "CF_ACCESS_TEAM_DOMAIN"),
    ({"CF_ACCESS_AUD": ""}, "CF_ACCESS_AUD"),
    ({"CF_ACCESS_TEAM_DOMAIN": "https://t.cloudflareaccess.com"}, "bare host"),
    ({"CF_ACCESS_TEAM_DOMAIN": "t.cloudflareaccess.com/path"}, "bare host"),
    ({"CF_ACCESS_TEAM_DOMAIN": "t .cloudflareaccess.com"}, "bare host"),
    ({"CF_ACCESS_TEAM_DOMAIN": "t.cloudflareaccess.com:443"}, "bare host"),
    ({"AUTH_PROVIDER": "static", "AUTH_STATIC_EMAIL": ""}, "AUTH_STATIC_EMAIL"),
])
def test_validate_auth_config_rejects(over, msg):
    from backend.config import validate_auth_config
    with _auth(**over):
        with pytest.raises(ValueError, match=msg):
            validate_auth_config()


def test_team_domain_is_lowercased(clean_env):
    import backend.config
    env = {"CF_ACCESS_TEAM_DOMAIN": " MyTeam.CloudflareAccess.com ", "DATA_DIR": "/tmp/my-data"}
    with patch.dict(os.environ, env):
        with patch("os.makedirs"):
            importlib.reload(backend.config)
            assert backend.config.CF_ACCESS_TEAM_DOMAIN == "myteam.cloudflareaccess.com"
    importlib.reload(backend.config)


def test_empty_static_email_env_falls_back_to_admin_email(clean_env):
    """Compose passes AUTH_STATIC_EMAIL="" when unset; that must still default to ADMIN_EMAIL."""
    import backend.config
    env = {"ADMIN_EMAIL": "admin@x.io", "AUTH_STATIC_EMAIL": "", "DATA_DIR": "/tmp/my-data"}
    with patch.dict(os.environ, env):
        with patch("os.makedirs"):
            importlib.reload(backend.config)
            assert backend.config.AUTH_STATIC_EMAIL == "admin@x.io"
    importlib.reload(backend.config)


def test_auth_emails_are_normalised(clean_env):
    import backend.config
    env = {"ADMIN_EMAIL": "  Admin@X.io ", "DATA_DIR": "/tmp/my-data"}
    with patch.dict(os.environ, env):
        with patch("os.makedirs"):
            importlib.reload(backend.config)
            assert backend.config.ADMIN_EMAIL == "admin@x.io"
            assert backend.config.AUTH_STATIC_EMAIL == "admin@x.io"
    # Restore the module to the real environment so later tests see the original values.
    importlib.reload(backend.config)


def test_rate_limit_settings_have_defaults_and_read_the_environment(clean_env, monkeypatch):
    import backend.config as c
    keys = ("RATE_LIMIT_TURNS_PER_MINUTE", "RATE_LIMIT_SEARCHES_PER_DAY", "RATE_LIMIT_EXEMPT_ADMIN")
    try:
        for key in keys:
            monkeypatch.delenv(key, raising=False)
        importlib.reload(c)
        assert (c.RATE_LIMIT_TURNS_PER_MINUTE, c.RATE_LIMIT_SEARCHES_PER_DAY, c.RATE_LIMIT_EXEMPT_ADMIN) == (10, 200, True)
        monkeypatch.setenv("RATE_LIMIT_TURNS_PER_MINUTE", "3")
        monkeypatch.setenv("RATE_LIMIT_SEARCHES_PER_DAY", "7")
        monkeypatch.setenv("RATE_LIMIT_EXEMPT_ADMIN", "false")
        importlib.reload(c)
        assert (c.RATE_LIMIT_TURNS_PER_MINUTE, c.RATE_LIMIT_SEARCHES_PER_DAY, c.RATE_LIMIT_EXEMPT_ADMIN) == (3, 7, False)
    finally:
        monkeypatch.undo()
        importlib.reload(c)


def _reload_with(monkeypatch, **env):
    import backend.config as c
    for key in ("CODE_RUNNER_MAX_QUEUED_PER_USER", "CODE_RUNNER_QUEUE_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(c)
    return c


def test_run_queue_settings_have_defaults(clean_env, monkeypatch):
    try:
        c = _reload_with(monkeypatch)
        assert c.CODE_RUNNER_MAX_QUEUED_PER_USER == 2
        assert c.CODE_RUNNER_QUEUE_TIMEOUT == 120
    finally:
        monkeypatch.undo()
        importlib.reload(c)


def test_run_queue_settings_read_the_environment_and_clamp_bad_values(clean_env, monkeypatch):
    import backend.config as c
    try:
        c = _reload_with(monkeypatch, CODE_RUNNER_MAX_QUEUED_PER_USER="5", CODE_RUNNER_QUEUE_TIMEOUT="30")
        assert (c.CODE_RUNNER_MAX_QUEUED_PER_USER, c.CODE_RUNNER_QUEUE_TIMEOUT) == (5, 30)
        c = _reload_with(monkeypatch, CODE_RUNNER_MAX_QUEUED_PER_USER="0", CODE_RUNNER_QUEUE_TIMEOUT="-4")
        assert (c.CODE_RUNNER_MAX_QUEUED_PER_USER, c.CODE_RUNNER_QUEUE_TIMEOUT) == (1, 0)  # never refuses every run
    finally:
        monkeypatch.undo()
        importlib.reload(c)
