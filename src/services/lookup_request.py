from dataclasses import dataclass
from typing import Literal

LookupSource = Literal["propertyfinder", "bayut", "trakheesi", "dld_phone"]


@dataclass(frozen=True, slots=True)
class LookupRequest:
    source: LookupSource
    external_id: str
    raw_input: str