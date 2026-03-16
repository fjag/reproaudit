# ReproAudit — Product Specification

This document describes what ReproAudit does, why, and for whom. For implementation details see [TECHNICAL.md](TECHNICAL.md).

---

## Problem

Published research papers in applied ML, data science, computational biology, and bioinformatics increasingly share code on GitHub. But the gap between what papers claim and what their repositories actually support is large. Reviewers, students, and researchers routinely discover they cannot reproduce reported results — not because the science is fraudulent, but because:

- Evaluation methodology is flawed (data leakage, single-split evaluation, wrong metrics)
- Code doesn't match the described methods (wrong hyperparameters, missing components)
- Dependencies are underspecified or unpinned
- Execution instructions are missing or incomplete
- Data is inaccessible or undocumented

No existing tool systematically audits the alignment between a paper's claims and its companion code.

---

## What the tool does

ReproAudit takes a research paper and its GitHub repository as input, and produces a structured reproducibility audit report identifying specific issues that would prevent or undermine reproduction of the paper's claimed results.

It does **not** execute the code. All analysis is static: AST parsing, pattern matching, and LLM-based reasoning anchored to claims extracted from the paper.

---

## Users

- **Reviewers** checking supplementary code alongside a submission
- **Students** attempting to reproduce published results
- **Researchers** auditing their own work before submission
- **Team leads** spot-checking code quality on team outputs

---

## Inputs and outputs

### Inputs
- One or more PDFs: the main manuscript plus any supplementary material. The user provides these — the tool does not fetch anything from publishers.
- A public GitHub repository URL.

### Outputs
A Markdown report organised into five dimensions, each containing individual findings. Each finding includes:
- Severity level: **critical** / **important** / **advisory**
- Plain-language explanation of the issue and why it matters
- Pointer to the specific code location (file, line where available)
- Where relevant, the specific paper claim that is contradicted
- A concrete suggestion for how to fix it

---

## The five dimensions

### 1. Claim–Code Consistency
Does the code implement what the paper describes?

| Finding | Severity |
|---------|----------|
| Hyperparameter in paper differs from hardcoded value in code | Critical |
| Method described in paper has no corresponding code | Critical |
| Evaluation metric described in paper not computed in code | Important |
| Model architecture in paper differs from implementation | Important |
| Ablation study described but no ablation script found | Advisory |
| Dataset referenced in paper not referenced in code | Advisory |

### 2. Evaluation Integrity
Is the evaluation methodology sound?

| Finding | Severity |
|---------|----------|
| Preprocessing fit() applied before train/test split (data leakage) | Critical |
| Test set used for iterative model selection | Critical |
| ROC-AUC reported without PR-AUC in potential rare-event setting | Important |
| Threshold optimised on evaluation data | Important |
| Single-split evaluation with no uncertainty quantification | Important |
| No subgroup evaluation for sensitive attributes | Advisory |
| Training metrics not reported (overfitting undiagnosable) | Advisory |
| Calibration not assessed when probabilities used downstream | Advisory |

### 3. Computational Reproducibility
Can someone run this code and get the same numbers?

| Finding | Severity |
|---------|----------|
| No random seed set in entry-point script(s) | Critical |
| NumPy/PyTorch/TensorFlow generators not seeded | Critical |
| sklearn estimators instantiated without random_state | Important |
| glob/listdir used for data loading without sorting | Important |
| Scientific library version unpinned (watchlist package) | Important |
| GPU non-determinism not acknowledged | Advisory |

**Library watchlist:** numpy, scikit-learn, PyTorch, TensorFlow, pandas, scipy, lifelines, statsmodels — all have known behavioural changes across minor versions.

### 4. Execution Completeness
Can someone run this code at all?

| Finding | Severity |
|---------|----------|
| No entry point identified | Critical |
| Import not found in any dependency specification | Critical |
| Hardcoded absolute path pointing to non-repo filesystem | Critical |
| Notebook cells have out-of-order execution metadata | Critical |
| No dependency specification file found | Important |
| No data download or preparation script | Advisory |

### 5. Data Availability
Can someone obtain the required data?

| Finding | Severity |
|---------|----------|
| Data source referenced in paper not mentioned in repo | Critical |
| Restricted dataset used with no access instructions | Critical |
| No data download script or instructions | Important |
| Expected data format/schema not documented | Important |
| No checksums or data versioning for input files | Advisory |

---

## Severity taxonomy

| Level | Meaning |
|-------|---------|
| **Critical** | Can invalidate or make it impossible to reproduce the claimed results |
| **Important** | Substantially weakens confidence in results or reproducibility |
| **Advisory** | Best-practice absence that creates long-term maintenance or reproducibility debt |

---

## Interaction flow

```
1. reproaudit audit --paper paper.pdf --repo https://github.com/user/repo
   → Parses PDF, extracts claims, writes claims.yaml
   → Pauses

2. User reviews/edits claims.yaml
   → Can mark confirmed: false to exclude a misextracted claim

3. reproaudit resume
   → Clones repo, runs rule-based + LLM analysis
   → Produces report.md
```

---

## Scope (v1)

**In scope:**
- Python repositories
- Public GitHub URLs
- scikit-learn, PyTorch, TensorFlow/Keras, and common scientific Python libraries
- Applied ML, data science, computational biology, bioinformatics

**Out of scope:**
- R, Julia, or multi-language repos
- Private repositories
- Executing any code from the repository
- Fetching papers from publishers (user provides PDFs)

---

## Known limitations and caveats

### Brief critique

The following issues were identified during specification and inform the current design:

**Data leakage detection is intrafile only.** Detecting preprocessing-before-split reliably requires interprocedural data-flow analysis. The current implementation detects the pattern only within a single file and flags it at 0.7 confidence (advisory when uncertain). Cross-file leakage is not detected.

**LLM findings cannot reliably produce line-level precision.** LLMs hallucinate line numbers. The architecture uses a retrieve-then-cite pattern: rule-based or keyword retrieval finds candidate code spans, the LLM reasons about those spans, and the span's location (from the retrieval step) is cited. Pure LLM findings cite files only.

**PDF parsing is lossy.** Complex layouts — multi-column papers, scanned figures, LaTeX-rendered tables — degrade text extraction. Claim extraction accuracy depends directly on parse quality. The tool degrades gracefully (fewer extracted claims) rather than failing.

**"Results with no corresponding code" is scoped conservatively.** Determining which code generates which figure/table is unreliable for complex repos. v1 only checks that some evaluation code exists, not that every reported metric has a corresponding computation.

**The "does not fetch from the internet" principle**: The tool does not fetch research papers, datasets, or domain content. LLM API calls are the only external network dependency.

**False positives are minimised by design.** Low-confidence LLM findings (<50%) are framed as questions. LLM findings are never assigned Critical severity at <60% confidence.
