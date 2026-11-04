import json
from threading import Lock
from time import monotonic
from typing import Protocol
from urllib.parse import quote, urlencode

from .._http import HTTPTransport, checked_endpoint
from ..errors import SDKError

SCOPE = "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"


def valid_token(value: str) -> bool:
    return type(value) is str and bool(value) and all(32 < ord(c) < 127 for c in value)


class TokenProvider(Protocol):
    def token(self) -> str: ...


class StaticToken:
    def __init__(self, token: str):
        if not valid_token(token):
            raise SDKError("configuration", "token")
        self._value = token

    def __repr__(self) -> str:
        return "StaticToken([redacted])"

    def token(self) -> str:
        return self._value


class OAuth2TokenProvider:
    """Consulta Integrada client_credentials, with expiry-aware in-memory caching."""

    def __init__(self, client_id: str, client_secret: str, *, token_url: str | None = None,
                 transport: HTTPTransport | None = None):
        if not client_id.strip() or not client_secret.strip():
            raise SDKError("configuration", "token")
        self._client_id = client_id
        self._secret = client_secret
        self._url = token_url or (
            "https://api-seguridad.sunat.gob.pe/v1/clientesextranet/"
            + quote(client_id, safe="") + "/oauth2/token/"
        )
        checked_endpoint(self._url)
        self._transport = transport or HTTPTransport()
        self._lock = Lock()
        self._access_token = ""
        self._expires = 0.0
        self._clock = monotonic

    def __repr__(self) -> str:
        return "OAuth2TokenProvider([redacted])"

    def token(self) -> str:
        with self._lock:
            if self._clock() < self._expires:
                return self._access_token
            started = self._clock()
            form = urlencode({"grant_type": "client_credentials", "scope": SCOPE,
                              "client_id": self._client_id, "client_secret": self._secret})
            body = self._transport.post(self._url, {"Content-Type": "application/x-www-form-urlencoded"},
                                        form.encode("ascii"), "token")
            try:
                result = json.loads(body)
                token, ttl, kind = result["access_token"], result["expires_in"], result["token_type"]
                if not valid_token(token) or type(ttl) is not int or not 0 < ttl <= 86400 * 365:
                    raise ValueError
                if type(kind) is not str or kind.lower() != "bearer":
                    raise ValueError
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise SDKError("protocol", "token") from None
            self._access_token = token
            self._expires = started + ttl - min(30, ttl / 10)
            return token
