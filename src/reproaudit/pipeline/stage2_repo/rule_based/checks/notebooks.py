"""EXEC-004: out-of-order notebook cell execution."""
from __future__ import annotations
import json
from typing import List, Optional

from .....models.findings import CodeLocation, RawFinding
from ..base import BaseCheck, RepoContext


class NotebookOrderCheck(BaseCheck):
    check_id = "EXEC-004"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for path in ctx.notebook_files:
            try:
                nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError, IOError):
                continue
            cells = nb.get("cells", [])
            counts: List[Optional[int]] = []
            for cell in cells:
                if cell.get("cell_type") == "code":
                    counts.append(cell.get("execution_count"))

            executed = [(i, c) for i, c in enumerate(counts) if c is not None]
            if len(executed) < 2:
                continue

            # Check for non-monotonic execution
            prev = executed[0][1]
            for idx, count in executed[1:]:
                if count < prev:
                    findings.append(RawFinding(
                        check_id="EXEC-004",
                        confidence=0.95,
                        code_location=CodeLocation(
                            file=ctx.rel(path),
                            snippet=f"Cell {idx+1} has execution_count={count}, previous was {prev}",
                        ),
                        evidence={"notebook": ctx.rel(path), "cell_index": idx, "count": count},
                    ))
                    break  # one finding per notebook
                prev = count

        return findings
