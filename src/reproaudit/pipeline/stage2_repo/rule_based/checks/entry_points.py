"""EXEC-001: no clear entry point found."""
from __future__ import annotations
from typing import List

from .....models.findings import RawFinding
from ..base import BaseCheck, RepoContext


class EntryPointCheck(BaseCheck):
    check_id = "EXEC-001"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        # Check for __main__ blocks
        for path in ctx.py_files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "__main__" in text:
                    return []
            except OSError:
                continue

        # Check for Makefile with run targets
        for path in ctx.config_files:
            if path.name == "Makefile":
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if "python" in text:
                        return []
                except OSError:
                    continue

        # Check README for run instructions
        for path in ctx.readme_files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
                if "python " in text or "bash " in text or "sh " in text:
                    return []
            except OSError:
                continue

        # No entry point found
        return [RawFinding(
            check_id="EXEC-001",
            confidence=0.8,
            evidence={"message": "No entry point found: no __main__ block, no documented run command."},
        )]
