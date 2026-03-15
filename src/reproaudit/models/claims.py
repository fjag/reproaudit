from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass
class ClaimSource:
    quote: str
    section: Optional[str] = None
    page: Optional[int] = None
    ref: Optional[str] = None  # e.g. "Table 2", "Figure 3"


@dataclass
class Claim:
    id: str  # "C-001"
    type: Literal["quantitative_result", "methodological", "data_description"]
    text: str
    source: ClaimSource
    structured: Dict[str, Any] = field(default_factory=dict)
    confirmed: bool = True  # user sets False in claims.yaml to exclude
