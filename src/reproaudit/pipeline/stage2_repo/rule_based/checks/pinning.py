"""REPRO-005: scientific library version unpinned (watchlist check)."""
from __future__ import annotations
import re
from typing import List

from .....models.findings import RawFinding
from .....utils.watchlist import WATCHLIST_BY_INSTALL
from ..base import BaseCheck, RepoContext

_PINNED_RE = re.compile(r"==|>=.*,\s*<")  # == or >=x,<y considered pinned


class PinningCheck(BaseCheck):
    check_id = "REPRO-005"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        deps = ctx.get_dependencies()

        for install_name, entry in WATCHLIST_BY_INSTALL.items():
            spec = deps.get(install_name.lower(), "")
            if not spec:
                continue  # not used in this repo — no finding
            if not _PINNED_RE.search(spec):
                findings.append(RawFinding(
                    check_id="REPRO-005",
                    confidence=0.9,
                    evidence={
                        "package": install_name,
                        "current_spec": spec or "(no version pin)",
                        "reason": entry.reason,
                        "suggested_pin": entry.safe_pin,
                    },
                ))
        return findings
