import ipaddress
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import SDKError

MAX_RESPONSE_BYTES = 1 << 20


def checked_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        loopback = False
        try:
            loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            pass
        valid = (
            parsed.hostname and parsed.username is None and parsed.password is None
            and not parsed.query and not parsed.fragment
            and (parsed.scheme == "https" or (parsed.scheme == "http" and loopback))
        )
        parsed.port  # Reject malformed ports before a request is made.
    except ValueError:
        valid = False
    if not valid:
        raise SDKError("configuration", "endpoint")
    return value.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTPTransport:
    """Bounded stdlib HTTP transport; redirects and automatic retries are disabled."""

    def __init__(self, timeout: float = 10):
        if timeout <= 0:
            raise SDKError("configuration", "timeout")
        self._timeout = timeout
        self._opener = build_opener(_NoRedirect())

    def post(self, url: str, headers: dict[str, str], body: bytes, operation: str) -> bytes:
        request = Request(url, data=body, headers={"Accept": "application/json", **headers}, method="POST")
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                result = response.read(MAX_RESPONSE_BYTES + 1)
                if len(result) > MAX_RESPONSE_BYTES:
                    raise SDKError("protocol", operation)
                return result
        except HTTPError as exc:
            status = exc.code
            exc.close()
            kind = {401: "authentication", 403: "authorization"}.get(status, "http")
            raise SDKError(kind, operation, status=status) from None
        except (URLError, OSError, ValueError):
            raise SDKError("transport", operation) from None
