def build(file_summaries: list[dict], code_spans: list[dict]) -> str:
    summaries = "\n".join(f"- {s['file']}: {s['summary']}" for s in file_summaries)
    spans = "\n\n".join(
        f"[{s['file']}]\n{s['snippet'][:2000]}"
        for s in code_spans
    )
    return f"""\
You are auditing evaluation methodology in a research code repository for reproducibility issues.

REPOSITORY FILE SUMMARIES:
{summaries}

EVALUATION CODE SPANS:
{spans}

Check for these issues and report only those you have evidence for:

- EVAL-003: Test set used for iterative model selection (not just final evaluation)
- EVAL-006: Decision threshold optimised on evaluation/test data
- EVAL-008: No subgroup evaluation despite apparent sensitive attributes (age, sex, race, site)
- EVAL-009: Training metrics not logged (overfitting undiagnosable)
- EVAL-010: Probabilities used downstream but calibration not assessed

For each issue found, report: found=true, severity, title, explanation, suggestion, confidence, file_hint.
If no issues found, report found=false.
Return only ONE finding per call (the most important one if multiple exist).
"""
