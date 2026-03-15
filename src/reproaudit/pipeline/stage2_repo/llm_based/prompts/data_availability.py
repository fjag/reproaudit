def build(readme_text: str, file_summaries: list[dict], paper_data_claims: list[str]) -> str:
    summaries = "\n".join(f"- {s['file']}: {s['summary']}" for s in file_summaries)
    claims_text = "\n".join(f"- {c}" for c in paper_data_claims) if paper_data_claims else "(none extracted)"
    return f"""\
You are auditing data availability and documentation in a research code repository.

PAPER DATA CLAIMS (from the paper):
{claims_text}

README:
{readme_text[:3000]}

REPOSITORY FILE SUMMARIES:
{summaries}

Check for these issues:
- DATA-001: Data source referenced in paper but not mentioned in repo (no download link, no reference)
- DATA-002: Controlled-access or restricted dataset (e.g. requires IRB, DUA, EULA, application) with no access instructions
- DATA-004: Expected data format/schema not documented anywhere

For each issue found, report: found=true, severity, title, explanation, suggestion, confidence, file_hint.
If no issues found, report found=false.
Return only ONE finding per call (the most important one).
"""
