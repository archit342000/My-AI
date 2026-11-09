"""Identity providers: turn request headers into a verified identity."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional

import jwt

from backend import config
from backend.logging import log_event

ACCESS_JWT_HEADER = "Cf-Access-Jwt-Assertion"
JWKS_TIMEOUT_SECONDS = 5
JWKS_LIFESPAN_SECONDS = 300
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "email"]


@dataclass(frozen=True)
class Identity:
    """A verified caller identity."""
    email: str


class IdentityProvider(ABC):
    """Maps request headers to an Identity, or None when the caller is not authenticated."""

    @abstractmethod
    def authenticate(self, headers: Mapping[str, str]) -> Optional[Identity]:
        ...


class CloudflareAccessProvider(IdentityProvider):
    """Verifies the Cloudflare Access JWT in the Cf-Access-Jwt-Assertion header (RS256 only)."""

    def __init__(self, team_domain: str, audience: str, jwks_client=None):
        self.issuer = f"https://{team_domain}"
        self.audience = audience
        self.jwks_client = jwks_client or jwt.PyJWKClient(
            f"{self.issuer}/cdn-cgi/access/certs",
            cache_keys=True,
            lifespan=JWKS_LIFESPAN_SECONDS,
            timeout=JWKS_TIMEOUT_SECONDS,
        )

    def authenticate(self, headers: Mapping[str, str]) -> Optional[Identity]:
        token = headers.get(ACCESS_JWT_HEADER)
        if not token:
            return None
        try:
            key = self.jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": REQUIRED_CLAIMS},
            )
        except (jwt.PyJWKClientConnectionError, jwt.PyJWKSetError, OSError, ValueError) as e:
            log_event("auth_jwks_error", {"reason": type(e).__name__})
            return None
        except jwt.PyJWTError as e:
            log_event("auth_rejected", {"reason": type(e).__name__})
            return None
        email = claims.get("email")
        if not isinstance(email, str) or not email.strip():
            log_event("auth_rejected", {"reason": "InvalidEmailClaim"})
            return None
        return Identity(email=email.strip().lower())


class StaticProvider(IdentityProvider):
    """Development only: every request is the same user. There is no verification."""

    def __init__(self, email: str):
        self.email = email

    def authenticate(self, headers: Mapping[str, str]) -> Optional[Identity]:
        return Identity(email=self.email)


_provider: Optional[IdentityProvider] = None


def get_provider() -> IdentityProvider:
    """Build the provider named by config.AUTH_PROVIDER once and reuse it."""
    global _provider
    if _provider is None:
        if config.AUTH_PROVIDER == "static":
            _provider = StaticProvider(config.AUTH_STATIC_EMAIL)
        else:
            _provider = CloudflareAccessProvider(config.CF_ACCESS_TEAM_DOMAIN, config.CF_ACCESS_AUD)
    return _provider
