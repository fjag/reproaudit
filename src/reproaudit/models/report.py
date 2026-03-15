from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal

from .claims import Claim
from .findings import Finding


@dataclass
class DimensionSummary:
    dimension: str
    status: Literal["issues_found", "looks_good", "could_not_assess"]
    critical: int = 0
    important: int = 0
    advisory: int = 0


@dataclass
class Report:
    meta: Dict[str, str]  # paper, repo_url, repo_commit, audit_date, tool_version
    claims: List[Claim] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    summary: List[DimensionSummary] = field(default_factory=list)
