from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass
class CodeLocation:
    file: str  # relative path from repo root
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    snippet: Optional[str] = None


@dataclass
class RawFinding:
    """Intermediate output from a single check before dedup/severity assignment."""
    check_id: str
    confidence: float
    code_location: Optional[CodeLocation] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    id: str          # e.g. "EVAL-001"
    instance: int    # disambiguates multiple instances of same rule
    dimension: Literal[
        "claim_code", "eval_integrity",
        "computational_repro", "exec_completeness", "data_availability"
    ]
    severity: Literal["critical", "important", "advisory"]
    title: str
    explanation: str
    suggestion: str
    confidence: float
    source: Literal["rule_based", "llm", "combined"]
    code_location: Optional[CodeLocation] = None
    claim_ref: Optional[str] = None  # Claim.id
    suppressed: bool = False
