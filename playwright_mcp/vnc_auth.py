"""websockify auth plugin for the portal VNC: HTTP Basic auth with the playwright_mcp API key.

websockify loads this class with `--auth-plugin playwright_mcp.vnc_auth.ApiKeyBasicAuth --auth-source <secret file>`
and, with `--web-auth`, applies it to the noVNC static files as well as the WebSocket upgrade. The app's
proxies add the credential server-side, so the key never reaches the browser.
"""
import base64
import binascii
import hashlib
import hmac

from websockify.auth_plugins import AuthenticationError


class ApiKeyBasicAuth:
    """Accepts a request only when its Basic-auth password equals the key stored in the secret file."""

    def __init__(self, src):
        self.key_file = src

    def _read_key(self) -> bytes:
        try:
            with open(self.key_file, "rb") as f:
                return f.read().strip()
        except OSError:
            return b""

    def authenticate(self, headers, target_host, target_port):
        """Raises AuthenticationError (401) unless the Basic password matches the key.

        Fails closed: a missing or empty key file rejects everything. The key is read on every call, so
        rotating the secret needs no restart. The username is ignored and nothing secret is logged.

        Args:
            headers: The request headers (a mapping with `get`).
            target_host: Unused; required by the websockify plugin interface.
            target_port: Unused; required by the websockify plugin interface.
        """
        key = self._read_key()
        scheme, _, token = (headers.get("Authorization") or "").partition(" ")
        if not key or scheme.lower() != "basic":
            raise AuthenticationError(response_code=401, response_msg="Unauthorized")
        try:
            decoded = base64.b64decode(token.strip(), validate=True)
        except (binascii.Error, ValueError):
            raise AuthenticationError(response_code=401, response_msg="Unauthorized")
        _, sep, password = decoded.partition(b":")
        if not sep or not hmac.compare_digest(hashlib.sha256(password).digest(), hashlib.sha256(key).digest()):
            raise AuthenticationError(response_code=401, response_msg="Unauthorized")
