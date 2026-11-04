"""Provisional identity interface. Only synthetic lookups are implemented."""

from typing import Protocol

from ..errors import SDKError
from .models import Identity, IdentityQuery


class IdentityService(Protocol):
    def lookup(self, query: IdentityQuery) -> Identity: ...


class MockIdentityService:
    """An in-memory test provider, with no network access or official RENIEC adapter."""

    def __init__(self, records: list[Identity]):
        self._records: dict[str, Identity] = {}
        for record in records:
            record.__post_init__()
            if record.dni in self._records:
                raise ValueError("duplicate synthetic identity")
            self._records[record.dni] = record

    def lookup(self, query: IdentityQuery) -> Identity:
        query.__post_init__()
        try:
            return self._records[query.dni]
        except KeyError:
            raise SDKError("not_found", "synthetic_identity") from None


__all__ = ["Identity", "IdentityQuery", "IdentityService", "MockIdentityService"]
