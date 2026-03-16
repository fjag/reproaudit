# ReproAudit

A static reproducibility auditor for research papers with companion GitHub repositories, targeting applied ML, data science, computational biology, and bioinformatics fields, where Python-based analysis code is routinely shared alongside publications.

ReproAudit takes a research paper PDF and any supplementary documents, along with a GitHub repository URL, then produces a structured Markdown audit report identifying specific issues that would prevent or undermine reproduction of the paper's claimed results. It does **not** execute any code from the repository — analysis is entirely static.

> **ReproAudit is an experimental tool. Use findings as a starting point for manual review, not as definitive conclusions. Provided without warranty or support commitments.**

---

## What it does

ReproAudit runs a three-stage pipeline:

1. **Claim extraction** — parses the paper and (optional) any supplementary documents PDFs using an LLM to extract quantitative results, methodological claims, and data descriptions. Pauses for you to review the claims to analyse before continuing.
2. **Repository analysis** — clones the GitHub repo and runs two analysis passes:
   - Rule-based static analysis (AST parsing, import resolution, pattern matching).
   - LLM-based analysis (file summarisation, claim–code matching, evaluation methodology checks).
3. **Report generation** — cross-references claims against findings and produces a structured Markdown report.

### What it checks

| Dimension | Examples |
|-----------|---------|
| Claim–Code Consistency | Hyperparameter values, missing methods, metric mismatches |
| Evaluation Integrity | Data leakage, single-split evaluation, ROC-AUC without PR-AUC |
| Computational Reproducibility | Unseeded random generators, unpinned library versions |
| Execution Completeness | Missing entry points, hardcoded paths, unresolvable imports |
| Data Availability | Missing download scripts, undocumented data sources |

---

## Requirements

- Python 3.11 or higher
- An [Anthropic API key](https://console.anthropic.com) with available credits (see [Cost](#cost))
- Git installed and accessible on your PATH
- One or more PDF files: the main paper and, optionally, any supplementary material (provided by you — the tool does not fetch papers from publishers)
- A public GitHub repository URL

---

## Installation

### 1. Clone or download this repository

```bash
git clone https://github.com/fjag/reproaudit
cd reproaudit
```

### 2. Create a virtual environment

```bash
python3 -m venv --copies .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install the package

```bash
pip install -e .
```

### 4. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

To avoid setting this every session, add it to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.).

---

## Usage

### Step 1 — Run the audit

```bash
reproaudit audit --paper paper.pdf --repo https://github.com/user/repo
```

With supplementary PDFs:

```bash
reproaudit audit --paper paper.pdf --paper supplement.pdf --repo https://github.com/user/repo
```

The tool extracts claims from the PDF and writes them to `reproaudit_output/claims.yaml`, then pauses.

### Step 2 — Review claims

Open `reproaudit_output/claims.yaml` and verify the extracted claims. Set `confirmed: false` on any claim that was incorrectly extracted (or you are not interested in) to exclude it from analysis.

### Step 3 — Resume analysis

```bash
reproaudit resume
```

This clones the repository, runs all checks, and writes the report to `reproaudit_output/report.md`.

### Additional options

```
--output DIR          Output directory (default: ./reproaudit_output)
--model MODEL         Anthropic model (default: claude-sonnet-4-6)
--dimensions DIMS     Comma-separated subset of dimensions to run
--suppress IDS        Comma-separated finding IDs to suppress (e.g. REPRO-004,EXEC-008)
--no-confirm          Skip claim review step and proceed immediately
--no-cache            Disable caching (re-runs will re-call the LLM)
```

Browse the finding catalogue:

```bash
reproaudit findings list
reproaudit findings explain EVAL-001
```

---

## Cost

ReproAudit calls the Anthropic API (Claude) for claim extraction and LLM-based analysis. Typical costs using `claude-sonnet-4-6` (but first test to verify before running full analysis on an actual paper):

| Scenario | Estimated cost |
|----------|---------------|
| Short paper + small repo (~10 files) | ~$0.10–0.20 |
| Typical ML paper + medium repo (~20 files) | ~$0.30–0.50 |
| Long paper + large repo (~50 files) | ~$0.70–1.00 |

Caching is enabled by default — re-running on the same inputs does not incur additional API costs.

You need an Anthropic account with API credits at [console.anthropic.com](https://console.anthropic.com). A Claude Pro subscription does **not** include API access — these are separate products.

---

## Output

```
reproaudit_output/
  claims.yaml      # Extracted paper claims — review and edit before resuming
  report.md        # Full audit report
  analysis_cache/  # Cached LLM responses (speeds up re-runs)
```

---

## Limitations

- Python repositories only
- Public GitHub repositories only (no private repos)
- Static analysis only — the tool never executes repository code
- LLM-based findings carry a confidence score; low-confidence findings are framed as questions
- PDF parsing quality affects claim extraction accuracy — complex layouts (scanned PDFs, multi-column equations) may degrade results
- Leakage detection operates within individual source files only; pipelines where data flows across multiple scripts or notebooks are not analysed.

For a full discussion of scope and known limitations, see [SPECS.md](SPECS.md).
For architecture and implementation details, see [TECHNICAL.md](TECHNICAL.md).

---

## Acknowledgements

This tool was co-developed with [Claude Code](https://claude.ai/claude-code) (Anthropic), which assisted in system design, specification, and implementation.

---

## Disclaimer

ReproAudit is an experimental research tool intended to assist — not replace — expert judgement. Findings should be treated as a starting point for manual review, not as definitive conclusions. Accuracy is not guaranteed, and results may vary depending on code structure and documentation quality. The author assumes no responsibility for decisions made based on this tool's output. This project is maintained on a best-effort basis with no commitment to updates or user support.
