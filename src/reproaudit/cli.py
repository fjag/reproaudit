from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional, Tuple

import click
from rich.console import Console

from .config import Config, DIMENSIONS_ALL
from .pipeline.orchestrator import run_stage1, run_stage2_and_3
from .utils.logging import setup_logging

console = Console()
_STATE_FILE = "reproaudit_state.json"


@click.group()
def cli():
    """ReproAudit — Scientific reproducibility auditor for ML research papers."""


@cli.command()
@click.option("--paper", "papers", multiple=True, required=True,
              type=click.Path(exists=True, path_type=Path),
              help="Path to paper PDF (repeat for supplementary PDFs).")
@click.option("--repo", required=True, help="Public GitHub repository URL.")
@click.option("--output", "output_dir", default="./reproaudit_output",
              type=click.Path(path_type=Path), help="Output directory.")
@click.option("--model", default="claude-sonnet-4-6", show_default=True,
              help="Anthropic model to use.")
@click.option("--dimensions", default=None,
              help="Comma-separated subset of dimensions to run (default: all).")
@click.option("--suppress", default=None,
              help="Comma-separated finding IDs to suppress (e.g. REPRO-004,EXEC-008).")
@click.option("--no-cache", is_flag=True, default=False, help="Disable caching.")
@click.option("--no-confirm", is_flag=True, default=False,
              help="Skip claim confirmation step and proceed immediately.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose logging.")
@click.option("--log-file", default=None, type=click.Path(), help="Write logs to file.")
def audit(
    papers: Tuple[Path, ...],
    repo: str,
    output_dir: Path,
    model: str,
    dimensions: Optional[str],
    suppress: Optional[str],
    no_cache: bool,
    no_confirm: bool,
    verbose: bool,
    log_file: Optional[str],
):
    """Extract claims from PDFs and pause for review before repo analysis."""
    setup_logging(verbose=verbose, log_file=log_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = Config(
        paper_paths=list(papers),
        repo_url=repo,
        output_dir=output_dir,
        model=model,
        dimensions=dimensions.split(",") if dimensions else list(DIMENSIONS_ALL),
        suppress=set(suppress.split(",")) if suppress else set(),
        no_cache=no_cache,
        no_confirm=no_confirm,
        verbose=verbose,
        log_file=log_file,
    )

    console.print(f"[bold]ReproAudit[/bold] — auditing {repo}")
    console.print(f"Papers: {', '.join(p.name for p in papers)}")
    console.print()

    run_stage1(config)

    if no_confirm:
        console.print("\n[bold]--no-confirm set: proceeding to analysis...[/bold]\n")
        run_stage2_and_3(config)


@cli.command()
@click.option("--output", "output_dir", default="./reproaudit_output",
              type=click.Path(exists=True, path_type=Path),
              help="Output directory from the audit run.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose logging.")
@click.option("--log-file", default=None, type=click.Path(), help="Write logs to file.")
def resume(output_dir: Path, verbose: bool, log_file: Optional[str]):
    """Resume analysis after reviewing claims.yaml."""
    setup_logging(verbose=verbose, log_file=log_file)
    state_path = output_dir / _STATE_FILE
    if not state_path.exists():
        raise click.ClickException(
            f"No audit state found in {output_dir}. Run `reproaudit audit` first."
        )

    state = json.loads(state_path.read_text())
    config = Config(
        paper_paths=[Path(p) for p in state["paper_paths"]],
        repo_url=state["repo_url"],
        output_dir=output_dir,
        model=state.get("model", "claude-sonnet-4-6"),
        dimensions=state.get("dimensions", list(DIMENSIONS_ALL)),
        suppress=set(state.get("suppress", [])),
        no_cache=state.get("no_cache", False),
        verbose=verbose,
        log_file=log_file,
    )

    console.print(f"[bold]ReproAudit resume[/bold] — {config.repo_url}")
    console.print()
    run_stage2_and_3(config)


@cli.group()
def findings():
    """Commands for browsing the finding catalogue."""


@findings.command(name="list")
def findings_list():
    """Print all finding IDs and their descriptions."""
    from .pipeline.stage3_matching import FINDING_CATALOGUE
    from rich.table import Table

    table = Table(title="ReproAudit Finding Catalogue", show_lines=True)
    table.add_column("ID", style="bold")
    table.add_column("Severity")
    table.add_column("Description")

    for fid, spec in sorted(FINDING_CATALOGUE.items()):
        colour = {"critical": "red", "important": "yellow", "advisory": "blue"}.get(spec.severity, "white")
        table.add_row(fid, f"[{colour}]{spec.severity}[/{colour}]", spec.title)

    console.print(table)


@findings.command(name="explain")
@click.argument("finding_id")
def findings_explain(finding_id: str):
    """Explain a specific finding type."""
    from .pipeline.stage3_matching import FINDING_CATALOGUE

    finding_id = finding_id.upper()
    spec = FINDING_CATALOGUE.get(finding_id)
    if not spec:
        raise click.ClickException(f"Unknown finding ID: {finding_id}")

    console.print(f"[bold]{finding_id}[/bold] — {spec.title}")
    console.print(f"Severity: [bold]{spec.severity}[/bold]")
    console.print(f"\nSuggestion: {spec.suggestion}")
