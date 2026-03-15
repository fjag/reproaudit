"""REPRO-004: unsorted glob/listdir used for data loading."""
from __future__ import annotations
from typing import List

from .....models.findings import RawFinding
from .....utils.ast_utils import find_calls_by_attr
from ..base import BaseCheck, RepoContext

_UNSORTED_CALLS = ["glob.glob", "os.listdir", "Path.glob", "pathlib.Path.glob"]


class SortingCheck(BaseCheck):
    check_id = "REPRO-004"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for path in ctx.py_files:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            import ast as _ast
            for call_node, lineno in find_calls_by_attr(tree, _UNSORTED_CALLS):
                # Check if the call is wrapped in sorted()
                parent_text = ""
                try:
                    src = path.read_text(encoding="utf-8", errors="replace").splitlines()
                    if lineno > 0 and lineno <= len(src):
                        parent_text = src[lineno - 1]
                except OSError:
                    pass
                if "sorted(" not in parent_text:
                    findings.append(RawFinding(
                        check_id="REPRO-004",
                        confidence=0.75,
                        code_location=self._loc(path, ctx, lineno, lineno, parent_text.strip()[:80]),
                        evidence={"line": parent_text.strip()},
                    ))
        return findings
