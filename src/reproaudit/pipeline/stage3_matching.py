from __future__ import annotations
from collections import defaultdict
from typing import List

from ..models.claims import Claim
from ..models.findings import Finding, RawFinding
from ..config import DIMENSION_LABELS

# Map check_id prefix to dimension
_CHECK_TO_DIM = {
    "CLAIM": "claim_code",
    "EVAL": "eval_integrity",
    "REPRO": "computational_repro",
    "EXEC": "exec_completeness",
    "DATA": "data_availability",
}

# Catalogue severities for rule-based checks
_SEVERITIES = {
    "CLAIM-001": "critical", "CLAIM-002": "critical",
    "CLAIM-003": "important", "CLAIM-004": "important",
    "CLAIM-005": "advisory", "CLAIM-006": "advisory",
    "EVAL-001": "critical", "EVAL-002": "critical",
    "EVAL-003": "critical",
    "EVAL-004": "important", "EVAL-005": "important",
    "EVAL-006": "important", "EVAL-007": "important",
    "EVAL-008": "advisory", "EVAL-009": "advisory", "EVAL-010": "advisory",
    "REPRO-001": "critical", "REPRO-002": "critical",
    "REPRO-003": "important", "REPRO-004": "important", "REPRO-005": "important",
    "REPRO-006": "advisory", "REPRO-007": "advisory",
    "EXEC-001": "critical", "EXEC-002": "critical",
    "EXEC-003": "critical", "EXEC-004": "critical",
    "EXEC-005": "important", "EXEC-006": "important",
    "EXEC-007": "advisory", "EXEC-008": "advisory",
    "DATA-001": "critical", "DATA-002": "critical",
    "DATA-003": "important", "DATA-004": "important",
    "DATA-005": "advisory", "DATA-006": "advisory",
}

_TITLES = {
    "CLAIM-001": "Reported hyperparameter differs from code value",
    "CLAIM-002": "Method described in paper has no corresponding code",
    "CLAIM-003": "Evaluation metric described in paper not computed in code",
    "CLAIM-004": "Model architecture in paper differs from implementation",
    "CLAIM-005": "Ablation study described but no ablation script found",
    "CLAIM-006": "Dataset referenced in paper not referenced in code",
    "EVAL-001": "Preprocessing fit() applied before train/test split (data leakage)",
    "EVAL-002": "Potential target leakage through input features",
    "EVAL-003": "Test set used for iterative model selection",
    "EVAL-004": "Accuracy on class-imbalanced data without disclosure",
    "EVAL-005": "ROC-AUC reported without PR-AUC in potential rare-event setting",
    "EVAL-006": "Decision threshold optimised on evaluation data",
    "EVAL-007": "Single-split evaluation with no uncertainty quantification",
    "EVAL-008": "No subgroup evaluation for sensitive attributes",
    "EVAL-009": "Training metrics not reported (overfitting undiagnosable)",
    "EVAL-010": "Calibration not assessed when probabilities used downstream",
    "REPRO-001": "No random seed set in entry-point script(s)",
    "REPRO-002": "Framework random generators not seeded",
    "REPRO-003": "sklearn estimators instantiated without random_state",
    "REPRO-004": "glob/listdir used for data loading without sorting",
    "REPRO-005": "Scientific library version unpinned (on watchlist)",
    "REPRO-006": "GPU non-determinism not acknowledged",
    "REPRO-007": "Python hash randomisation not disabled",
    "EXEC-001": "No entry point identified",
    "EXEC-002": "Import not found in any dependency specification",
    "EXEC-003": "Hardcoded absolute path pointing to non-repo filesystem",
    "EXEC-004": "Notebook cells have out-of-order execution metadata",
    "EXEC-005": "No dependency specification file found",
    "EXEC-006": "Intermediate file consumed but not produced in repo",
    "EXEC-007": "Execution order across scripts not documented",
    "EXEC-008": "No data download or preparation script found",
    "DATA-001": "Data source referenced in paper not mentioned in repo",
    "DATA-002": "Restricted dataset used with no access instructions",
    "DATA-003": "No data download script or instructions",
    "DATA-004": "Expected data format/schema not documented",
    "DATA-005": "No checksums or data versioning for input files",
    "DATA-006": "Sample sizes in paper may differ from code expectations",
}

_SUGGESTIONS = {
    "REPRO-001": "Add random.seed(42) (or a documented seed value) at the top of your main script.",
    "REPRO-002": "Seed all framework generators: np.random.seed(), torch.manual_seed(), tf.random.set_seed().",
    "REPRO-003": "Pass random_state=<seed> when instantiating this estimator.",
    "REPRO-004": "Wrap glob/listdir calls with sorted() to ensure consistent file ordering.",
    "REPRO-005": "Pin this library to a specific version range in your dependency spec (e.g. ==x.y.z or >=x.y,<x+1).",
    "REPRO-006": "Add torch.use_deterministic_algorithms(True) and set CUBLAS_WORKSPACE_CONFIG=:4096:8.",
    "EXEC-001": "Add a clear entry point (if __name__ == '__main__') or document run commands in README.",
    "EXEC-002": "Add this package to requirements.txt or pyproject.toml dependencies.",
    "EXEC-003": "Replace hardcoded paths with relative paths or environment variable / CLI argument.",
    "EXEC-004": "Re-run the notebook top-to-bottom and save it to fix cell execution order.",
    "EXEC-005": "Add a requirements.txt or pyproject.toml listing all dependencies with version pins.",
    "EXEC-008": "Add a data download script or document data acquisition steps in README.",
    "EVAL-001": "Fit preprocessors only on training data (after the split), not on the full dataset.",
    "EVAL-005": "Report average_precision_score (PR-AUC) alongside roc_auc_score for imbalanced settings.",
    "EVAL-007": "Use cross-validation (KFold) or bootstrap resampling to quantify result uncertainty.",
    "DATA-003": "Add a download script or clear instructions for obtaining the required data.",
    "DATA-005": "Provide checksums (md5/sha256) for input data files, or use DVC for data versioning.",
    "CLAIM-001": "Update the code to match the hyperparameter value stated in the paper, or document the discrepancy.",
    "CLAIM-002": "Implement the missing method or explain in README why it is omitted.",
    "CLAIM-003": "Add code to compute and report this metric.",
}


def build_findings(
    raw_findings: List[RawFinding],
    claims: List[Claim],
    suppress: set,
) -> List[Finding]:
    """Deduplicate raw findings, assign severities, cross-reference claims."""
    deduped = _deduplicate(raw_findings)
    claims_by_id = {c.id: c for c in claims}

    # Count instances per check_id
    instance_counter: dict = defaultdict(int)
    findings: List[Finding] = []

    for raw in deduped:
        check_id = raw.check_id
        if check_id in suppress:
            continue

        instance_counter[check_id] += 1
        instance = instance_counter[check_id]

        prefix = check_id.split("-")[0]
        dimension = _CHECK_TO_DIM.get(prefix, "exec_completeness")

        # Severity: use catalogue; LLM evidence may override downward
        severity = _SEVERITIES.get(check_id, "advisory")
        if raw.confidence < 0.6 and severity == "critical":
            severity = "important"

        # Source
        source = "rule_based" if raw.confidence >= 0.8 else "llm"
        if raw.evidence.get("claim_id"):
            source = "llm"

        # Explanation and suggestion
        explanation = raw.evidence.get("explanation") or raw.evidence.get("message", "")
        if not explanation:
            explanation = _default_explanation(check_id, raw.evidence)
        suggestion = _SUGGESTIONS.get(check_id, "Review and address this issue.")

        title = _TITLES.get(check_id, check_id)
        if raw.evidence.get("title"):
            title = raw.evidence["title"]

        claim_ref = raw.evidence.get("claim_id")

        findings.append(Finding(
            id=check_id,
            instance=instance,
            dimension=dimension,
            severity=severity,
            title=title,
            explanation=explanation,
            suggestion=suggestion,
            confidence=raw.confidence,
            source=source,
            code_location=raw.code_location,
            claim_ref=claim_ref,
        ))

    return findings


def _deduplicate(raw: List[RawFinding]) -> List[RawFinding]:
    """Merge findings with same check_id and overlapping code location (within 5 lines)."""
    kept: List[RawFinding] = []
    for finding in raw:
        duplicate = False
        for existing in kept:
            if existing.check_id != finding.check_id:
                continue
            # Both have no location → same finding
            if existing.code_location is None and finding.code_location is None:
                duplicate = True
                break
            # One has location, other doesn't → not same
            if existing.code_location is None or finding.code_location is None:
                continue
            # Same file, within 5 lines
            if existing.code_location.file == finding.code_location.file:
                e_line = existing.code_location.line_start or 0
                f_line = finding.code_location.line_start or 0
                if abs(e_line - f_line) <= 5:
                    # Keep higher-confidence one
                    if finding.confidence > existing.confidence:
                        kept.remove(existing)
                        kept.append(finding)
                    duplicate = True
                    break
        if not duplicate:
            kept.append(finding)
    return kept


def _default_explanation(check_id: str, evidence: dict) -> str:
    parts = []
    for k, v in evidence.items():
        if k not in ("claim_id", "title", "suggestion", "severity"):
            parts.append(f"{k}: {v}")
    return "; ".join(parts) if parts else _TITLES.get(check_id, check_id)
