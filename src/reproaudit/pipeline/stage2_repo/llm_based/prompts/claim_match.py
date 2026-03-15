def build(claim_text: str, claim_structured: dict, code_spans: list[dict]) -> str:
    spans_text = "\n\n".join(
        f"[{s['file']}:{s.get('line_start', '?')}]\n{s['snippet']}"
        for s in code_spans
    )
    structured_str = ", ".join(f"{k}={v}" for k, v in claim_structured.items()) if claim_structured else "none"
    return f"""\
You are auditing whether a research paper's claim is correctly implemented in its companion code.

CLAIM: {claim_text}
Structured fields: {structured_str}

RELEVANT CODE SPANS:
{spans_text}

Determine:
1. Does the code implement this claim? (matches: true/false)
2. If not, what is the discrepancy? (e.g. "paper says lr=0.001 but code has lr=0.01")
3. Confidence in your assessment (0.0 to 1.0)
4. If there is a discrepancy, what finding type applies? Use one of: CLAIM-001 (hyperparameter mismatch), CLAIM-002 (method not implemented), CLAIM-003 (metric not computed), CLAIM-004 (architecture mismatch), or null.
5. Brief explanation.

Be conservative: if the code spans don't clearly show the relevant implementation, set confidence below 0.5.
"""
