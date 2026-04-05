from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .summarizer import FileSummary


@dataclass
class CodeSpan:
    file: str
    line_start: int
    line_end: int
    snippet: str
    relevance: float


def retrieve_for_claim(
    claim_text: str,
    claim_structured: Dict[str, Any],
    summaries: List[FileSummary],
    repo_root: Path,
    top_k: int = 3,
    context_lines: int = 20,
) -> List[CodeSpan]:
    """Retrieve code spans most relevant to a claim.

    Strategy:
    1. Score each file summary by keyword overlap with the claim.
    2. For top-K files, keyword-search within the file for claim terms.
    3. Return ±context_lines around each match.
    """
    query_terms = _extract_terms(claim_text, claim_structured)
    scored = _score_summaries(summaries, query_terms)
    top_files = [s.path for s in scored[:top_k]]

    spans: List[CodeSpan] = []
    for rel_path in top_files:
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            continue
        try:
            lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        matches = _find_keyword_lines(lines, query_terms)
        if not matches:
            # Use first N lines as fallback
            matches = [0]
        for match_line in matches[:2]:
            start = max(0, match_line - context_lines)
            end = min(len(lines), match_line + context_lines)
            snippet = "\n".join(lines[start:end])
            score = next((s.relevance for s in scored if s.path == rel_path), 0.5)
            spans.append(CodeSpan(
                file=rel_path,
                line_start=start + 1,
                line_end=end,
                snippet=snippet,
                relevance=score,
            ))
    return spans


def _extract_terms(text: str, structured: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    # Add structured values as exact terms
    for v in structured.values():
        if isinstance(v, (int, float, str)):
            terms.append(str(v))
    # Add significant words from text (>4 chars, not stopwords)
    _STOP = {"with", "that", "this", "from", "have", "they", "their",
              "were", "been", "which", "using", "used", "model", "data"}
    for word in text.lower().split():
        word = word.strip(".,;:()")
        if len(word) > 4 and word not in _STOP:
            terms.append(word)
    return list(dict.fromkeys(terms))[:15]  # deduplicate, max 15


@dataclass
class _ScoredSummary:
    path: str
    relevance: float


def _score_summaries(summaries: List[FileSummary], terms: List[str]) -> List[_ScoredSummary]:
    results: List[_ScoredSummary] = []
    for s in summaries:
        haystack = (s.summary + " " + " ".join(s.key_symbols)).lower()
        score = sum(1 for t in terms if t.lower() in haystack) / max(len(terms), 1)
        results.append(_ScoredSummary(path=s.path, relevance=score))
    return sorted(results, key=lambda x: x.relevance, reverse=True)


def _find_keyword_lines(lines: List[str], terms: List[str]) -> List[int]:
    hits: List[int] = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(t.lower() in line_lower for t in terms[:8]):
            hits.append(i)
    return hits[:3]
