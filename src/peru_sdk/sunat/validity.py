from datetime import date
import json
import re

from .._http import HTTPTransport, MAX_RESPONSE_BYTES, checked_endpoint
from ..errors import SDKError
from .auth import TokenProvider, valid_token
from .models import ValidityQuery, ValidityResult


def parse_validity_response(body: bytes) -> ValidityResult:
    """Normalize status codes without treating query success as document acceptance."""
    try:
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError
        def reject_constant(value):
            raise ValueError("non-JSON constant")
        response = json.loads(body.decode("utf-8"), parse_constant=reject_constant)
        if type(response) is not dict or type(response.get("success")) is not bool:
            raise ValueError
        if not response["success"]:
            code = response.get("errorCode", "")
            if type(code) is not str or re.fullmatch(r"[A-Za-z0-9_.-]{0,64}", code) is None:
                code = ""
            raise SDKError("remote", "validity", code=code)
        data = response["data"]
        if type(data) is not dict:
            raise ValueError

        def read_code(name: str) -> str:
            value = data[name]
            if type(value) is int and value >= 0:
                return str(value)
            if type(value) is str and re.fullmatch(r"[0-9]+", value) is not None:
                return value
            raise ValueError

        observations = data.get("observaciones", data.get("Observaciones"))
        if observations is None:
            observations = []
        if type(observations) is not list or any(type(v) is not str for v in observations):
            raise ValueError
        return ValidityResult(read_code("estadoCp"), read_code("estadoRuc"),
                              read_code("condDomiRuc"), tuple(observations))
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
        raise SDKError("protocol", "validity") from None


class ValidityClient:
    """Read-only Consulta Integrada client. No implicit retries or global credentials."""

    def __init__(self, requester_ruc: str, token_provider: TokenProvider, *,
                 base_url: str = "https://api.sunat.gob.pe", transport: HTTPTransport | None = None):
        if type(requester_ruc) is not str or re.fullmatch(r"[0-9]{11}", requester_ruc) is None or token_provider is None:
            raise SDKError("configuration", "validity")
        self._url = (checked_endpoint(base_url) + "/v1/contribuyente/contribuyentes/"
                     + requester_ruc + "/validarcomprobante")
        self._tokens = token_provider
        self._transport = transport or HTTPTransport()

    def check(self, query: ValidityQuery) -> ValidityResult:
        # Revalidate even when passed an instance created outside the normal constructor.
        query.__post_init__()
        data = {"numRuc": query.issuer_ruc, "codComp": query.document_type,
                "numeroSerie": query.series, "numero": query.number,
                "fechaEmision": date.fromisoformat(query.issued_on).strftime("%d/%m/%Y")}
        # The contract permits only JSON decimal literals; never round through binary float.
        body = (json.dumps(data, separators=(",", ":")).encode("utf-8")[:-1]
                + b',"monto":' + query.amount.encode("ascii") + b"}")
        token = self._tokens.token()
        if not valid_token(token):
            raise SDKError("configuration", "token")
        response = self._transport.post(self._url, {"Content-Type": "application/json",
                                                    "Authorization": "Bearer " + token}, body, "validity")
        return parse_validity_response(response)
