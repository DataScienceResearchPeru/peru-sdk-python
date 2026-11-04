"""Contract models. Regenerate through the pinned models generator."""
from dataclasses import dataclass
from datetime import date
import re

@dataclass(frozen=True)
class ValidityQuery:
    issuer_ruc: str
    document_type: str
    series: str
    number: int
    issued_on: str
    amount: str

    def __post_init__(self) -> None:
        if type(self.issuer_ruc) is not str:
            raise ValueError("issuer_ruc: invalid type")
        if re.fullmatch('^[0-9]{11}$', self.issuer_ruc, flags=re.ASCII) is None:
            raise ValueError("issuer_ruc: invalid format")
        if type(self.document_type) is not str:
            raise ValueError("document_type: invalid type")
        if re.fullmatch('^[A-Z0-9]{2}$', self.document_type, flags=re.ASCII) is None:
            raise ValueError("document_type: invalid format")
        if type(self.series) is not str:
            raise ValueError("series: invalid type")
        if re.fullmatch('^[A-Z0-9]{4}$', self.series, flags=re.ASCII) is None:
            raise ValueError("series: invalid format")
        if type(self.number) is not int:
            raise ValueError("number: invalid type")
        if self.number < 1:
            raise ValueError("number: out of range")
        if self.number > 99999999:
            raise ValueError("number: out of range")
        if type(self.issued_on) is not str:
            raise ValueError("issued_on: invalid type")
        try:
            parsed = date.fromisoformat(self.issued_on)
        except ValueError:
            raise ValueError("issued_on: invalid date") from None
        if parsed.isoformat() != self.issued_on:
            raise ValueError("issued_on: expected YYYY-MM-DD")
        if type(self.amount) is not str:
            raise ValueError("amount: invalid type")
        if re.fullmatch('^(0|[1-9][0-9]{0,14})([.][0-9]{1,2})?$', self.amount, flags=re.ASCII) is None:
            raise ValueError("amount: invalid format")

@dataclass(frozen=True)
class ValidityResult:
    document_status: str
    issuer_status: str
    issuer_address_status: str
    observations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.document_status) is not str:
            raise ValueError("document_status: invalid type")
        if re.fullmatch('^[0-9]+$', self.document_status, flags=re.ASCII) is None:
            raise ValueError("document_status: invalid format")
        if type(self.issuer_status) is not str:
            raise ValueError("issuer_status: invalid type")
        if type(self.issuer_address_status) is not str:
            raise ValueError("issuer_address_status: invalid type")
        if type(self.observations) is not tuple or any(type(v) is not str for v in self.observations):
            raise ValueError("observations: invalid type")
