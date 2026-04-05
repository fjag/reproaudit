from __future__ import annotations
from typing import List, Optional

from ....llm.client import LLMClient
from ....llm.structured import ClaimMatchResult, LLMFindingResult, extract_structured
from ....models.claims import Claim
from ....models.findings import CodeLocation, Finding, RawFinding
from ....utils.logging import get_logger
from .retriever import CodeSpan
from .prompts import claim_match as _cm
from .prompts import eval_integrity as _ei
from .prompts import data_availability as _da

logger = get_logger(__name__)


def analyze_claim(
    claim: Claim,
    spans: List[CodeSpan],
    client: LLMClient,
) -> Optional[RawFinding]:
    """Check if a claim is correctly implemented in the retrieved code spans."""
    if not spans:
        return None
    span_dicts = [
        {"file": s.file, "line_start": s.line_start, "snippet": s.snippet}
        for s in spans
    ]
    prompt = _cm.build(claim.text, claim.structured, span_dicts)
    try:
        result = extract_structured(client, prompt, ClaimMatchResult)
    except (RuntimeError, ValueError, KeyError) as e:
        logger.debug("Claim match extraction failed for claim %s: %s", claim.id, e)
        return None

    if result.matches:
        return None

    if result.confidence < 0.3:
        return None

    best_span = spans[0]
    return RawFinding(
        check_id=result.finding_type or "CLAIM-001",
        confidence=result.confidence,
        code_location=CodeLocation(
            file=best_span.file,
            line_start=best_span.line_start,
            line_end=best_span.line_end,
            snippet=best_span.snippet[:200],
        ),
        evidence={
            "claim_id": claim.id,
            "discrepancy": result.discrepancy,
            "explanation": result.explanation,
        },
    )


def analyze_eval_integrity(
    file_summaries: list,
    eval_spans: List[CodeSpan],
    client: LLMClient,
) -> Optional[RawFinding]:
    summary_dicts = [{"file": s.path, "summary": s.summary} for s in file_summaries]
    span_dicts = [{"file": s.file, "snippet": s.snippet} for s in eval_spans]
    prompt = _ei.build(summary_dicts, span_dicts)
    try:
        result = extract_structured(client, prompt, LLMFindingResult)
    except (RuntimeError, ValueError, KeyError) as e:
        logger.debug("Eval integrity extraction failed: %s", e)
        return None
    if not result.found:
        return None
    return RawFinding(
        check_id=_severity_to_check_id(result.title),
        confidence=result.confidence,
        code_location=CodeLocation(file=result.file_hint or "") if result.file_hint else None,
        evidence={
            "title": result.title,
            "explanation": result.explanation,
            "suggestion": result.suggestion,
            "severity": result.severity,
        },
    )


def analyze_data_availability(
    readme_text: str,
    file_summaries: list,
    data_claims: List[str],
    client: LLMClient,
) -> Optional[RawFinding]:
    summary_dicts = [{"file": s.path, "summary": s.summary} for s in file_summaries]
    prompt = _da.build(readme_text, summary_dicts, data_claims)
    try:
        result = extract_structured(client, prompt, LLMFindingResult)
    except (RuntimeError, ValueError, KeyError) as e:
        logger.debug("Data availability extraction failed: %s", e)
        return None
    if not result.found:
        return None
    return RawFinding(
        check_id="DATA-001",
        confidence=result.confidence,
        code_location=CodeLocation(file=result.file_hint or "") if result.file_hint else None,
        evidence={
            "title": result.title,
            "explanation": result.explanation,
            "suggestion": result.suggestion,
            "severity": result.severity,
        },
    )


def _severity_to_check_id(title: Optional[str]) -> str:
    if not title:
        return "EVAL-003"
    t = (title or "").upper()
    if "THRESHOLD" in t or "OPTIMIS" in t:
        return "EVAL-006"
    if "SUBGROUP" in t:
        return "EVAL-008"
    if "TRAINING METRIC" in t or "OVERFITTING" in t:
        return "EVAL-009"
    if "CALIBRATION" in t:
        return "EVAL-010"
    return "EVAL-003"
