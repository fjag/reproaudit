from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set


DIMENSIONS_ALL: List[str] = [
    "claim_code",
    "eval_integrity",
    "computational_repro",
    "exec_completeness",
    "data_availability",
]

DIMENSION_LABELS: dict[str, str] = {
    "claim_code": "Claim–Code Consistency",
    "eval_integrity": "Evaluation Integrity",
    "computational_repro": "Computational Reproducibility",
    "exec_completeness": "Execution Completeness",
    "data_availability": "Data Availability",
}


@dataclass
class Config:
    paper_paths: List[Path]
    repo_url: str
    output_dir: Path
    model: str = "claude-sonnet-4-6"
    dimensions: List[str] = field(default_factory=lambda: list(DIMENSIONS_ALL))
    suppress: Set[str] = field(default_factory=set)
    no_cache: bool = False
    no_confirm: bool = False
    verbose: bool = False
    log_file: Optional[str] = None

    @property
    def cache_dir(self) -> Path:
        return self.output_dir / "analysis_cache"

    @property
    def claims_path(self) -> Path:
        return self.output_dir / "claims.yaml"

    @property
    def report_path(self) -> Path:
        return self.output_dir / "report.md"
