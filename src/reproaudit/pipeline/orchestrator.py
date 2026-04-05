from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import List

from ..config import Config
from ..llm.client import LLMClient
from ..models.claims import Claim
from ..models.findings import Finding
from ..models.report import Report
from ..reporting.markdown import build_claims_summary, build_summary, render
from ..utils.cache import DiskCache
from ..utils.logging import get_logger
from . import stage1_claims
from .stage2_repo.cloner import clone_repo
from .stage2_repo.rule_based.runner import build_context, run_all_checks
from .stage2_repo.llm_based.runner import run_llm_analysis
from .stage3_matching import build_findings

logger = get_logger(__name__)

TOOL_VERSION = "0.2.0"
_STATE_FILE = "reproaudit_state.json"


def run_stage1(config: Config) -> None:
    """Extract claims from PDFs and write claims.yaml. Then exit."""
    logger.info("Starting Stage 1: Claims extraction")
    client = LLMClient(model=config.model)
    claims = stage1_claims.run(config, client)
    logger.info("Extracted %d claims", len(claims))
    print(f"\n✓ Extracted {len(claims)} claims.")
    print(f"  Review and edit: {config.claims_path}")
    print(f"\nThen run: reproaudit resume --output {config.output_dir}")

    # Save state for resume
    import json
    state = {
        "repo_url": config.repo_url,
        "model": config.model,
        "dimensions": config.dimensions,
        "suppress": list(config.suppress),
        "no_cache": config.no_cache,
        "paper_paths": [str(p) for p in config.paper_paths],
    }
    (config.output_dir / _STATE_FILE).write_text(json.dumps(state, indent=2))


def run_stage2_and_3(config: Config) -> Report:
    """Run repo analysis and generate the report. Called by `resume`."""
    logger.info("Starting Stage 2 & 3: Repo analysis and report generation")
    client = LLMClient(model=config.model)
    cache = DiskCache(config.cache_dir)

    # Load claims
    claims = stage1_claims.run(config, client)
    confirmed_claims = [c for c in claims if c.confirmed]
    logger.info("Loaded %d confirmed claims", len(confirmed_claims))
    print(f"  Loaded {len(confirmed_claims)} confirmed claims.")

    # Clone repo
    logger.info("Cloning repository: %s", config.repo_url)
    print(f"  Cloning {config.repo_url}...")
    repo = clone_repo(config.repo_url)
    commit_sha = repo.commit_sha
    logger.info("Cloned at commit %s", commit_sha[:8])
    print(f"  Cloned at commit {commit_sha[:8]}")

    try:
        # Rule-based analysis
        logger.info("Running rule-based checks")
        print("  Running rule-based checks...")
        ctx = build_context(repo.path)
        raw_rule = run_all_checks(ctx)
        logger.info("Rule-based analysis found %d raw findings", len(raw_rule))
        print(f"  Rule-based: {len(raw_rule)} raw findings")

        # LLM-based analysis
        logger.info("Running LLM-based analysis")
        print("  Running LLM-based analysis...")
        raw_llm = run_llm_analysis(ctx, confirmed_claims, client, cache)
        logger.info("LLM-based analysis found %d raw findings", len(raw_llm))
        print(f"  LLM-based: {len(raw_llm)} raw findings")

        # Stage 3: match and build findings
        all_raw = raw_rule + raw_llm
        findings = build_findings(all_raw, claims, config.suppress)

        # Build report
        summary = build_summary(findings, claims)
        claims_summary = build_claims_summary(claims, findings)
        report = Report(
            meta={
                "paper": ", ".join(p.name for p in config.paper_paths),
                "repo_url": config.repo_url,
                "repo_commit": commit_sha,
                "audit_date": str(date.today()),
                "tool_version": TOOL_VERSION,
            },
            claims=claims,
            findings=findings,
            summary=summary,
            claims_summary=claims_summary,
        )

        # Render
        render(report, config.report_path)
        print(f"\n✓ Report written to {config.report_path}")
        _print_claims_summary(claims_summary)
        _print_summary(summary)

    finally:
        repo.cleanup()

    return report


def _print_claims_summary(claims_summary) -> None:
    from rich.table import Table
    from rich.console import Console

    if claims_summary is None:
        return

    console = Console()
    cs = claims_summary

    table = Table(title="Claims Summary", show_header=True)
    table.add_column("Status")
    table.add_column("Count", justify="right")

    table.add_row("✓ Supported", str(cs.supported), style="green")
    table.add_row("✗ Unsupported", str(cs.unsupported), style="red" if cs.unsupported > 0 else None)
    table.add_row("? Not assessed", str(cs.not_assessed), style="dim")
    table.add_row("─" * 15, "─" * 5)
    table.add_row("Total confirmed", str(cs.confirmed_claims), style="bold")

    console.print(table)

    # Print support rate
    if cs.confirmed_claims > 0:
        support_rate = (cs.supported / cs.confirmed_claims) * 100
        color = "green" if support_rate >= 80 else "yellow" if support_rate >= 50 else "red"
        console.print(f"[{color}]Claim support rate: {support_rate:.1f}%[/{color}]")
    console.print()


def _print_summary(summary) -> None:
    from rich.table import Table
    from rich.console import Console
    from ..config import DIMENSION_LABELS

    console = Console()
    table = Table(title="Dimension Summary", show_header=True)
    table.add_column("Dimension")
    table.add_column("Status")
    table.add_column("Critical", justify="right")
    table.add_column("Important", justify="right")
    table.add_column("Advisory", justify="right")

    for s in summary:
        label = DIMENSION_LABELS.get(s.dimension, s.dimension)
        status = {"issues_found": "⚠ Issues", "looks_good": "✓ OK", "could_not_assess": "? N/A"}.get(s.status, s.status)
        table.add_row(label, status, str(s.critical), str(s.important), str(s.advisory))

    console.print(table)
