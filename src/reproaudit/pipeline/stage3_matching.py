from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

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


@dataclass(frozen=True)
class FindingSpec:
    """Specification for a finding type in the catalogue."""
    severity: str
    title: str
    suggestion: str = "Review and address this issue."


# Consolidated finding catalogue - single source of truth
FINDING_CATALOGUE: Dict[str, FindingSpec] = {
    # Claim-Code Consistency
    "CLAIM-001": FindingSpec(
        severity="critical",
        title="Reported hyperparameter differs from code value",
        suggestion="Update the code to match the hyperparameter value stated in the paper, or document the discrepancy.",
    ),
    "CLAIM-002": FindingSpec(
        severity="critical",
        title="Method described in paper has no corresponding code",
        suggestion="Implement the missing method or explain in README why it is omitted.",
    ),
    "CLAIM-003": FindingSpec(
        severity="important",
        title="Evaluation metric described in paper not computed in code",
        suggestion="Add code to compute and report this metric.",
    ),
    "CLAIM-004": FindingSpec(
        severity="important",
        title="Model architecture in paper differs from implementation",
    ),
    "CLAIM-005": FindingSpec(
        severity="advisory",
        title="Ablation study described but no ablation script found",
    ),
    "CLAIM-006": FindingSpec(
        severity="advisory",
        title="Dataset referenced in paper not referenced in code",
    ),

    # Evaluation Integrity
    "EVAL-001": FindingSpec(
        severity="critical",
        title="Preprocessing fit() applied before train/test split (data leakage)",
        suggestion="Fit preprocessors only on training data (after the split), not on the full dataset.",
    ),
    "EVAL-002": FindingSpec(
        severity="critical",
        title="Potential target leakage through input features",
    ),
    "EVAL-003": FindingSpec(
        severity="critical",
        title="Test set used for iterative model selection",
    ),
    "EVAL-004": FindingSpec(
        severity="important",
        title="Accuracy on class-imbalanced data without disclosure",
    ),
    "EVAL-005": FindingSpec(
        severity="important",
        title="ROC-AUC reported without PR-AUC in potential rare-event setting",
        suggestion="Report average_precision_score (PR-AUC) alongside roc_auc_score for imbalanced settings.",
    ),
    "EVAL-006": FindingSpec(
        severity="important",
        title="Decision threshold optimised on evaluation data",
    ),
    "EVAL-007": FindingSpec(
        severity="important",
        title="Single-split evaluation with no uncertainty quantification",
        suggestion="Use cross-validation (KFold) or bootstrap resampling to quantify result uncertainty.",
    ),
    "EVAL-008": FindingSpec(
        severity="advisory",
        title="No subgroup evaluation for sensitive attributes",
    ),
    "EVAL-009": FindingSpec(
        severity="advisory",
        title="Training metrics not reported (overfitting undiagnosable)",
    ),
    "EVAL-010": FindingSpec(
        severity="advisory",
        title="Calibration not assessed when probabilities used downstream",
    ),

    # Computational Reproducibility
    "REPRO-001": FindingSpec(
        severity="critical",
        title="No random seed set in entry-point script(s)",
        suggestion="Add random.seed(42) (or a documented seed value) at the top of your main script.",
    ),
    "REPRO-002": FindingSpec(
        severity="critical",
        title="Framework random generators not seeded",
        suggestion="Seed all framework generators: np.random.seed(), torch.manual_seed(), tf.random.set_seed().",
    ),
    "REPRO-003": FindingSpec(
        severity="important",
        title="sklearn estimators instantiated without random_state",
        suggestion="Pass random_state=<seed> when instantiating this estimator.",
    ),
    "REPRO-004": FindingSpec(
        severity="important",
        title="glob/listdir used for data loading without sorting",
        suggestion="Wrap glob/listdir calls with sorted() to ensure consistent file ordering.",
    ),
    "REPRO-005": FindingSpec(
        severity="important",
        title="Scientific library version unpinned (on watchlist)",
        suggestion="Pin this library to a specific version range in your dependency spec (e.g. ==x.y.z or >=x.y,<x+1).",
    ),
    "REPRO-006": FindingSpec(
        severity="advisory",
        title="GPU non-determinism not acknowledged",
        suggestion="Add torch.use_deterministic_algorithms(True) and set CUBLAS_WORKSPACE_CONFIG=:4096:8.",
    ),
    "REPRO-007": FindingSpec(
        severity="advisory",
        title="Python hash randomisation not disabled",
    ),

    # Execution Completeness
    "EXEC-001": FindingSpec(
        severity="critical",
        title="No entry point identified",
        suggestion="Add a clear entry point (if __name__ == '__main__') or document run commands in README.",
    ),
    "EXEC-002": FindingSpec(
        severity="critical",
        title="Import not found in any dependency specification",
        suggestion="Add this package to requirements.txt or pyproject.toml dependencies.",
    ),
    "EXEC-003": FindingSpec(
        severity="critical",
        title="Hardcoded absolute path pointing to non-repo filesystem",
        suggestion="Replace hardcoded paths with relative paths or environment variable / CLI argument.",
    ),
    "EXEC-004": FindingSpec(
        severity="critical",
        title="Notebook cells have out-of-order execution metadata",
        suggestion="Re-run the notebook top-to-bottom and save it to fix cell execution order.",
    ),
    "EXEC-005": FindingSpec(
        severity="important",
        title="No dependency specification file found",
        suggestion="Add a requirements.txt or pyproject.toml listing all dependencies with version pins.",
    ),
    "EXEC-006": FindingSpec(
        severity="important",
        title="Intermediate file consumed but not produced in repo",
    ),
    "EXEC-007": FindingSpec(
        severity="advisory",
        title="Execution order across scripts not documented",
    ),
    "EXEC-008": FindingSpec(
        severity="advisory",
        title="No data download or preparation script found",
        suggestion="Add a data download script or document data acquisition steps in README.",
    ),

    # Data Availability
    "DATA-001": FindingSpec(
        severity="critical",
        title="Data source referenced in paper not mentioned in repo",
    ),
    "DATA-002": FindingSpec(
        severity="critical",
        title="Restricted dataset used with no access instructions",
    ),
    "DATA-003": FindingSpec(
        severity="important",
        title="No data download script or instructions",
        suggestion="Add a download script or clear instructions for obtaining the required data.",
    ),
    "DATA-004": FindingSpec(
        severity="important",
        title="Expected data format/schema not documented",
    ),
    "DATA-005": FindingSpec(
        severity="advisory",
        title="No checksums or data versioning for input files",
        suggestion="Provide checksums (md5/sha256) for input data files, or use DVC for data versioning.",
    ),
    "DATA-006": FindingSpec(
        severity="advisory",
        title="Sample sizes in paper may differ from code expectations",
    ),
}


def get_finding_spec(check_id: str) -> FindingSpec:
    """Get the specification for a finding type, with fallback defaults."""
    return FINDING_CATALOGUE.get(
        check_id,
        FindingSpec(severity="advisory", title=check_id)
    )


def build_findings(
    raw_findings: List[RawFinding],
    claims: List[Claim],
    suppress: set,
) -> List[Finding]:
    """Deduplicate raw findings, assign severities, cross-reference claims."""
    deduped = _deduplicate(raw_findings)
    claims_by_id = {c.id: c for c in claims}

    # Count instances per check_id
    instance_counter: Dict[str, int] = defaultdict(int)
    findings: List[Finding] = []

    for raw in deduped:
        check_id = raw.check_id
        if check_id in suppress:
            continue

        instance_counter[check_id] += 1
        instance = instance_counter[check_id]

        prefix = check_id.split("-")[0]
        dimension = _CHECK_TO_DIM.get(prefix, "exec_completeness")

        # Get spec from catalogue
        spec = get_finding_spec(check_id)

        # Severity: use catalogue; LLM evidence may override downward
        severity = spec.severity
        if raw.confidence < 0.6 and severity == "critical":
            severity = "important"

        # Source
        source = "rule_based" if raw.confidence >= 0.8 else "llm"
        if raw.evidence.get("claim_id"):
            source = "llm"

        # Explanation and suggestion
        explanation = raw.evidence.get("explanation") or raw.evidence.get("message", "")
        if not explanation:
            explanation = _default_explanation(check_id, raw.evidence, spec.title)
        suggestion = spec.suggestion

        title = spec.title
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


def _default_explanation(check_id: str, evidence: dict, fallback_title: str) -> str:
    parts = []
    for k, v in evidence.items():
        if k not in ("claim_id", "title", "suggestion", "severity"):
            parts.append(f"{k}: {v}")
    return "; ".join(parts) if parts else fallback_title
