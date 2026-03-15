"""DATA-003: no data download script
DATA-005: no checksums/data versioning
EXEC-008: no data preparation script
"""
from __future__ import annotations
import re
from typing import List

from .....models.findings import RawFinding
from ..base import BaseCheck, RepoContext

_DOWNLOAD_KEYWORDS = re.compile(
    r"\b(wget|curl|download|urlretrieve|requests\.get|boto3|gsutil|"
    r"kaggle|zenodo|figshare|dvc pull|dvc run)\b",
    re.IGNORECASE,
)
_CHECKSUM_KEYWORDS = re.compile(
    r"\b(md5|sha256|sha512|checksum|hash|dvc|data\.dvc)\b",
    re.IGNORECASE,
)


class DataFilesCheck(BaseCheck):
    check_id = "DATA-003"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []

        all_text = ""
        for path in ctx.py_files + ctx.config_files + ctx.readme_files:
            try:
                all_text += path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        if not _DOWNLOAD_KEYWORDS.search(all_text):
            findings.append(RawFinding(
                check_id="DATA-003",
                confidence=0.7,
                evidence={"message": "No data download script or download command found in repo."},
            ))

        if not _CHECKSUM_KEYWORDS.search(all_text):
            findings.append(RawFinding(
                check_id="DATA-005",
                confidence=0.7,
                evidence={"message": "No checksums or data versioning (DVC, md5, sha256) found."},
            ))

        return findings
