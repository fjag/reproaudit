from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Dict, List, Set

from ..config import DIMENSION_LABELS, DIMENSIONS_ALL
from ..models.claims import Claim
from ..models.findings import Finding
from ..models.report import ClaimsSummary, DimensionSummary, Report


def render(report: Report, output_path: Path) -> None:
    lines: List[str] = []

    # Header
    m = report.meta
    lines += [
        "# ReproAudit Report",
        "",
        f"**Paper:** {m.get('paper', '(unknown)')}  ",
        f"**Repository:** {m.get('repo_url', '(unknown)')}  ",
        f"**Commit:** `{m.get('repo_commit', '(unknown)')[:12]}`  ",
        f"**Audit date:** {m.get('audit_date', str(date.today()))}  ",
        f"**Tool version:** {m.get('tool_version', '0.1.0')}  ",
        "",
        "---",
        "",
    ]

    # Claims Summary
    if report.claims_summary:
        cs = report.claims_summary
        lines += [
            "## Claims Summary",
            "",
            f"**Total claims extracted:** {cs.total_claims}  ",
            f"**Confirmed claims:** {cs.confirmed_claims}  ",
            "",
            "| Status | Count |",
            "|--------|-------|",
            f"| ✅ Supported (code matches paper) | {cs.supported} |",
            f"| ❌ Unsupported (discrepancy found) | {cs.unsupported} |",
            f"| ❓ Not assessed | {cs.not_assessed} |",
            "",
        ]
        # Calculate support rate for confirmed claims
        if cs.confirmed_claims > 0:
            support_rate = (cs.supported / cs.confirmed_claims) * 100
            lines.append(f"**Claim support rate:** {support_rate:.1f}% of confirmed claims  ")
            lines.append("")
        lines += ["---", ""]

    # Dimension Summary table
    lines += [
        "## Dimension Summary",
        "",
        "| Dimension | Status | Critical | Important | Advisory |",
        "|-----------|--------|----------|-----------|----------|",
    ]
    for dim_summary in report.summary:
        label = DIMENSION_LABELS.get(dim_summary.dimension, dim_summary.dimension)
        status_emoji = {
            "issues_found": "⚠️ Issues found",
            "looks_good": "✅ Looks good",
            "could_not_assess": "❓ Could not assess",
        }.get(dim_summary.status, dim_summary.status)
        lines.append(
            f"| {label} | {status_emoji} | {dim_summary.critical} | "
            f"{dim_summary.important} | {dim_summary.advisory} |"
        )
    lines += ["", "---", ""]

    # Findings by dimension
    lines.append("## Findings")
    lines.append("")

    claims_by_id: Dict[str, Claim] = {c.id: c for c in report.claims}
    active_findings = [f for f in report.findings if not f.suppressed]

    for dim in DIMENSIONS_ALL:
        dim_label = DIMENSION_LABELS[dim]
        dim_findings = [f for f in active_findings if f.dimension == dim]
        if not dim_findings:
            continue

        lines += [f"### {dim_label}", ""]

        for finding in sorted(dim_findings, key=lambda f: _severity_order(f.severity)):
            severity_badge = {
                "critical": "🔴 CRITICAL",
                "important": "🟡 IMPORTANT",
                "advisory": "🔵 ADVISORY",
            }.get(finding.severity, finding.severity.upper())

            instance_suffix = f".{finding.instance}" if finding.instance > 1 else ""
            lines.append(f"#### [{finding.id}{instance_suffix}] {severity_badge}: {finding.title}")
            lines.append("")

            # Confidence caveat for LLM findings
            if finding.source == "llm" and finding.confidence < 0.5:
                lines.append(f"> **Note:** Low-confidence finding ({finding.confidence:.0%}). "
                              "This may indicate an issue — please verify manually.")
                lines.append("")

            # Paper claim reference
            if finding.claim_ref and finding.claim_ref in claims_by_id:
                claim = claims_by_id[finding.claim_ref]
                ref_str = ""
                if claim.source.section:
                    ref_str += f"Section {claim.source.section}"
                if claim.source.page:
                    ref_str += f", p.{claim.source.page}"
                if claim.source.ref:
                    ref_str += f" ({claim.source.ref})"
                lines.append(f"**Paper claim:** {ref_str} — *\"{claim.source.quote[:120]}\"*  ")
                lines.append("")

            # Code location
            if finding.code_location:
                loc = finding.code_location
                loc_str = f"`{loc.file}`"
                if loc.line_start:
                    loc_str += f":{loc.line_start}"
                    if loc.line_end and loc.line_end != loc.line_start:
                        loc_str += f"–{loc.line_end}"
                lines.append(f"**Code location:** {loc_str}  ")
                if loc.snippet:
                    lines.append("")
                    lines.append("```python")
                    lines.append(loc.snippet[:300])
                    lines.append("```")
                lines.append("")

            lines.append(f"**Explanation:** {finding.explanation}  ")
            lines.append("")
            lines.append(f"**Suggestion:** {finding.suggestion}  ")
            lines.append("")
            lines.append("---")
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_summary(findings: List[Finding], claims: List[Claim] = None) -> List[DimensionSummary]:
    summaries: List[DimensionSummary] = []
    for dim in DIMENSIONS_ALL:
        dim_findings = [f for f in findings if f.dimension == dim and not f.suppressed]
        if not dim_findings:
            status = "looks_good"
        else:
            status = "issues_found"
        critical = sum(1 for f in dim_findings if f.severity == "critical")
        important = sum(1 for f in dim_findings if f.severity == "important")
        advisory = sum(1 for f in dim_findings if f.severity == "advisory")
        summaries.append(DimensionSummary(
            dimension=dim,
            status=status,
            critical=critical,
            important=important,
            advisory=advisory,
        ))
    return summaries


def build_claims_summary(claims: List[Claim], findings: List[Finding]) -> ClaimsSummary:
    """Build a summary of claim verification results.

    A claim is considered:
    - supported: confirmed by user AND no CLAIM-* findings reference it
    - unsupported: confirmed by user AND has CLAIM-* findings referencing it
    - not_assessed: not confirmed by user OR not analyzed
    """
    total = len(claims)
    confirmed = [c for c in claims if c.confirmed]
    confirmed_ids: Set[str] = {c.id for c in confirmed}

    # Find claims with issues (referenced by CLAIM-* findings)
    claim_findings = [f for f in findings if f.id.startswith("CLAIM-") and not f.suppressed]
    unsupported_claim_ids: Set[str] = set()
    for f in claim_findings:
        if f.claim_ref and f.claim_ref in confirmed_ids:
            unsupported_claim_ids.add(f.claim_ref)

    # Calculate stats
    unsupported = len(unsupported_claim_ids)
    supported = len(confirmed_ids) - unsupported
    not_assessed = total - len(confirmed_ids)

    return ClaimsSummary(
        total_claims=total,
        confirmed_claims=len(confirmed_ids),
        supported=supported,
        unsupported=unsupported,
        not_assessed=not_assessed,
    )


def _severity_order(severity: str) -> int:
    return {"critical": 0, "important": 1, "advisory": 2}.get(severity, 3)
