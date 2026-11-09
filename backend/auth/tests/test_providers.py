import time
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.auth import providers
from backend.auth.providers import (
    CloudflareAccessProvider, Identity, IdentityProvider, StaticProvider, get_provider,
)

TEAM = "team.cloudflareaccess.com"
AUD = "aud-tag"
ISS = f"https://{TEAM}"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class StubJWKS:
    def __init__(self, key=None, error=None):
        self.key, self.error = key, error

    def get_signing_key_from_jwt(self, token):
        if self.error:
            raise self.error
        return SimpleNamespace(key=self.key.public_key())


def make_token(signing_key, **over):
    now = int(time.time())
    claims = {"email": "User@Example.com", "aud": AUD, "iss": ISS, "iat": now, "exp": now + 300}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, signing_key, algorithm="RS256")


@pytest.fixture
def events():
    with patch("backend.auth.providers.log_event") as m:
        yield m


@pytest.fixture
def provider(key):
    return CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(key))


def auth(provider, token):
    return provider.authenticate({"Cf-Access-Jwt-Assertion": token})


def test_valid_token_returns_lowercased_identity(provider, key, events):
    assert auth(provider, make_token(key)) == Identity("user@example.com")
    events.assert_not_called()


@pytest.mark.parametrize("name,over,signer,reason", [
    ("bad signature", {}, "other", "InvalidSignatureError"),
    ("wrong aud", {"aud": "nope"}, "key", "InvalidAudienceError"),
    ("wrong iss", {"iss": "https://evil.example"}, "key", "InvalidIssuerError"),
    ("expired", {"exp": int(time.time()) - 10, "iat": int(time.time()) - 100}, "key", "ExpiredSignatureError"),
    ("no email", {"email": None}, "key", "MissingRequiredClaimError"),
    ("no exp", {"exp": None}, "key", "MissingRequiredClaimError"),
    ("no iat", {"iat": None}, "key", "MissingRequiredClaimError"),
    ("no aud", {"aud": None}, "key", "MissingRequiredClaimError"),
    ("no iss", {"iss": None}, "key", "MissingRequiredClaimError"),
])
def test_rejected_tokens(provider, key, other_key, events, name, over, signer, reason):
    token = make_token(key if signer == "key" else other_key, **over)
    assert auth(provider, token) is None
    events.assert_called_once_with("auth_rejected", {"reason": reason})


def test_blank_email_claim_rejected(provider, key, events):
    assert auth(provider, make_token(key, email="   ")) is None
    events.assert_called_once_with("auth_rejected", {"reason": "InvalidEmailClaim"})


def test_hs256_token_rejected(provider, key, events):
    token = jwt.encode({"email": "a@x.io", "aud": AUD, "iss": ISS, "iat": 1, "exp": 4102444800},
                       "secret-secret-secret-secret-secret", algorithm="HS256")
    assert auth(provider, token) is None
    assert events.call_args.args[0] == "auth_rejected"


def test_alg_none_token_rejected(provider, events):
    token = jwt.encode({"email": "a@x.io", "aud": AUD, "iss": ISS, "iat": 1, "exp": 4102444800},
                       None, algorithm="none")
    assert auth(provider, token) is None
    assert events.call_args.args[0] == "auth_rejected"


def test_malformed_token_rejected(provider, events):
    assert auth(provider, "not-a-jwt") is None
    events.assert_called_once()
    assert events.call_args.args[0] == "auth_rejected"


@pytest.mark.parametrize("headers", [{}, {"Cf-Access-Jwt-Assertion": ""}])
def test_missing_header_returns_none_without_logging(provider, events, headers):
    assert provider.authenticate(headers) is None
    events.assert_not_called()


def test_cookie_is_ignored(provider, key, events):
    assert provider.authenticate({"Cookie": f"CF_Authorization={make_token(key)}"}) is None
    events.assert_not_called()


def test_unknown_kid_is_a_rejection(key, events):
    p = CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(error=jwt.PyJWKClientError("no kid")))
    assert auth(p, make_token(key)) is None
    events.assert_called_once_with("auth_rejected", {"reason": "PyJWKClientError"})


def test_jwks_outage_fails_closed_and_logs_jwks_error(key, events):
    p = CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(error=jwt.PyJWKClientConnectionError("down")))
    assert auth(p, make_token(key)) is None
    events.assert_called_once_with("auth_jwks_error", {"reason": "PyJWKClientConnectionError"})


def test_jwks_socket_error_fails_closed_and_logs_jwks_error(key, events):
    p = CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(error=ConnectionResetError("reset")))
    assert auth(p, make_token(key)) is None
    events.assert_called_once_with("auth_jwks_error", {"reason": "ConnectionResetError"})


def test_jwks_non_json_reply_fails_closed_and_logs_jwks_error(key, events):
    import json
    p = CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(error=json.JSONDecodeError("bad", "<html>", 0)))
    assert auth(p, make_token(key)) is None
    events.assert_called_once_with("auth_jwks_error", {"reason": "JSONDecodeError"})


def test_jwk_set_parse_failure_is_a_jwks_error(key, events):
    p = CloudflareAccessProvider(TEAM, AUD, jwks_client=StubJWKS(error=jwt.PyJWKSetError("Invalid JWK Set value")))
    assert auth(p, make_token(key)) is None
    events.assert_called_once_with("auth_jwks_error", {"reason": "PyJWKSetError"})


def test_default_jwks_client_points_at_team_certs():
    p = CloudflareAccessProvider(TEAM, AUD)
    assert p.issuer == ISS
    assert p.jwks_client.uri == f"{ISS}/cdn-cgi/access/certs"
    assert p.jwks_client.timeout == providers.JWKS_TIMEOUT_SECONDS


def test_static_provider_always_returns_its_email():
    p = StaticProvider("dev@x.io")
    assert p.authenticate({}) == Identity("dev@x.io")
    assert isinstance(p, IdentityProvider)


def test_get_provider_picks_class_from_config_and_caches():
    with patch.object(providers, "_provider", None):
        with patch("backend.config.AUTH_PROVIDER", "static"), patch("backend.config.AUTH_STATIC_EMAIL", "d@x.io"):
            first = get_provider()
            assert isinstance(first, StaticProvider) and get_provider() is first
    with patch.object(providers, "_provider", None):
        with patch("backend.config.AUTH_PROVIDER", "cloudflare_access"), \
             patch("backend.config.CF_ACCESS_TEAM_DOMAIN", TEAM), patch("backend.config.CF_ACCESS_AUD", AUD):
            assert isinstance(get_provider(), CloudflareAccessProvider)
