"""Contract models. Regenerate through the pinned models generator."""
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class IdentityQuery:
    dni: str

    def __post_init__(self) -> None:
        if type(self.dni) is not str:
            raise ValueError("dni: invalid type")
        if re.fullmatch('^[0-9]{8}$', self.dni, flags=re.ASCII) is None:
            raise ValueError("dni: invalid format")

@dataclass(frozen=True)
class Identity:
    dni: str
    given_names: str
    first_surname: str
    second_surname: str

    def __post_init__(self) -> None:
        if type(self.dni) is not str:
            raise ValueError("dni: invalid type")
        if re.fullmatch('^[0-9]{8}$', self.dni, flags=re.ASCII) is None:
            raise ValueError("dni: invalid format")
        if type(self.given_names) is not str:
            raise ValueError("given_names: invalid type")
        if type(self.first_surname) is not str:
            raise ValueError("first_surname: invalid type")
        if type(self.second_surname) is not str:
            raise ValueError("second_surname: invalid type")
