"""REPRO-006: GPU non-determinism not acknowledged."""
from __future__ import annotations
import re
from typing import List

from .....models.findings import RawFinding
from ..base import BaseCheck, RepoContext

_CUDA_RE = re.compile(r"\bcuda\b|\bcudnn\b|\btorch\.cuda\b", re.IGNORECASE)
_DETERMINISTIC_RE = re.compile(
    r"torch\.use_deterministic_algorithms|"
    r"torch\.backends\.cudnn\.deterministic|"
    r"CUBLAS_WORKSPACE_CONFIG",
    re.IGNORECASE,
)


class GPUDeterminismCheck(BaseCheck):
    check_id = "REPRO-006"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        all_text = ""
        for path in ctx.py_files:
            try:
                all_text += path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        if _CUDA_RE.search(all_text) and not _DETERMINISTIC_RE.search(all_text):
            return [RawFinding(
                check_id="REPRO-006",
                confidence=0.8,
                evidence={"message": "CUDA operations found but torch.use_deterministic_algorithms "
                          "or cudnn.deterministic not set."},
            )]
        return []
