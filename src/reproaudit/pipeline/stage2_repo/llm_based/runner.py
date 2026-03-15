from __future__ import annotations
from pathlib import Path
from typing import List

from ....llm.client import LLMClient
from ....models.claims import Claim
from ....models.findings import RawFinding
from ....utils.cache import DiskCache
from ..rule_based.base import RepoContext
from .summarizer import FileSummary, summarize_files
from .retriever import retrieve_for_claim
from .analyzer import analyze_claim, analyze_eval_integrity, analyze_data_availability


def run_llm_analysis(
    ctx: RepoContext,
    claims: List[Claim],
    client: LLMClient,
    cache: DiskCache,
) -> List[RawFinding]:
    findings: List[RawFinding] = []

    # 1. Summarize all in-scope Python files
    summaries = summarize_files(ctx.py_files, ctx.repo_root, client, cache)

    # 2. Claim-code matching
    confirmed_claims = [c for c in claims if c.confirmed]
    for claim in confirmed_claims:
        spans = retrieve_for_claim(
            claim.text,
            claim.structured,
            summaries,
            ctx.repo_root,
        )
        finding = analyze_claim(claim, spans, client)
        if finding:
            finding.evidence["claim_id"] = claim.id
            findings.append(finding)

    # 3. Evaluation integrity LLM checks
    eval_summaries = [s for s in summaries if s.role in ("evaluation", "training", "pipeline_orchestration")]
    if not eval_summaries:
        eval_summaries = summaries  # fallback
    eval_spans = []
    for s in eval_summaries[:3]:
        abs_path = ctx.repo_root / s.path
        if abs_path.exists():
            try:
                lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
                snippet = "\n".join(lines[:100])
                from .retriever import CodeSpan
                eval_spans.append(CodeSpan(s.path, 1, min(100, len(lines)), snippet, 1.0))
            except OSError:
                pass
    finding = analyze_eval_integrity(summaries, eval_spans, client)
    if finding:
        findings.append(finding)

    # 4. Data availability LLM check
    readme_text = ""
    for rf in ctx.readme_files:
        try:
            readme_text += rf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    data_claims = [
        c.text for c in confirmed_claims if c.type == "data_description"
    ]
    finding = analyze_data_availability(readme_text, summaries, data_claims, client)
    if finding:
        findings.append(finding)

    return findings
