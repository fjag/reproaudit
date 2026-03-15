"""EXEC-003: hardcoded absolute paths."""
from __future__ import annotations
import re
from typing import List

from .....models.findings import RawFinding
from .....utils.ast_utils import get_all_string_literals
from ..base import BaseCheck, RepoContext

_PATH_PREFIXES = (
    "/home/", "/Users/", "/root/",
    "C:\\Users\\", "C:/Users/",
    "/mnt/", "/data/", "/scratch/",
    "/tmp/", "/var/", "/opt/",
)


class HardcodedPathsCheck(BaseCheck):
    check_id = "EXEC-003"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for path in ctx.py_files:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            for value, lineno in get_all_string_literals(tree):
                if any(value.startswith(p) for p in _PATH_PREFIXES):
                    findings.append(RawFinding(
                        check_id="EXEC-003",
                        confidence=0.95,
                        code_location=self._loc(path, ctx, lineno, lineno, value[:80]),
                        evidence={"path": value},
                    ))
        return findings
