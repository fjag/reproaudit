"""EVAL-005: no PR-AUC alongside ROC-AUC in rare-event settings
EVAL-007: single-split evaluation with no uncertainty quantification
"""
from __future__ import annotations
import re
from typing import List

from .....models.findings import RawFinding
from ..base import BaseCheck, RepoContext

_ROC_AUC = re.compile(r"\broc_auc_score\b|\bauc\b", re.IGNORECASE)
_PR_AUC = re.compile(r"\baverage_precision_score\b|\bprecision_recall\b|\bpr_auc\b", re.IGNORECASE)
_CV = re.compile(r"\bKFold\b|\bStratifiedKFold\b|\bcross_val_score\b|\bcross_validate\b")
_BOOTSTRAP = re.compile(r"\bbootstrap\b", re.IGNORECASE)
_TRAIN_TEST_SPLIT = re.compile(r"\btrain_test_split\b")


class EvalMetricsCheck(BaseCheck):
    check_id = "EVAL-005"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        all_text = ""
        for path in ctx.py_files:
            try:
                all_text += path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        # EVAL-005: ROC-AUC without PR-AUC
        if _ROC_AUC.search(all_text) and not _PR_AUC.search(all_text):
            findings.append(RawFinding(
                check_id="EVAL-005",
                confidence=0.65,
                evidence={"message": "roc_auc_score used but no average_precision_score (PR-AUC) found. "
                          "In imbalanced/rare-event settings, PR-AUC is also needed."},
            ))

        # EVAL-007: single split with no CV or bootstrap
        has_split = bool(_TRAIN_TEST_SPLIT.search(all_text))
        has_cv = bool(_CV.search(all_text))
        has_bootstrap = bool(_BOOTSTRAP.search(all_text))
        if has_split and not has_cv and not has_bootstrap:
            findings.append(RawFinding(
                check_id="EVAL-007",
                confidence=0.6,
                evidence={"message": "train_test_split found but no cross-validation or bootstrap. "
                          "Single-split evaluation lacks uncertainty quantification."},
            ))

        return findings
