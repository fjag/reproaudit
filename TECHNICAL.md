# ReproAudit — Technical Specification

This document describes the architecture, data structures, pipeline stages, and extension points. For product requirements see [SPECS.md](SPECS.md).

---

## Architecture overview

```
src/reproaudit/
  cli.py                              # Click CLI entry points
  config.py                           # Config dataclass
  models/
    claims.py                         # Claim, ClaimSource
    findings.py                       # Finding, CodeLocation, RawFinding
    report.py                         # Report, DimensionSummary
  utils/
    pdf.py                            # PDF text extraction
    ast_utils.py                      # AST traversal helpers
    cache.py                          # Disk cache (hash-keyed JSON)
    import_map.py                     # import name ↔ install name mapping
    watchlist.py                      # Library watchlist for REPRO-005
  llm/
    client.py                         # Anthropic SDK wrapper
    structured.py                     # Pydantic-validated structured extraction
  pipeline/
    orchestrator.py                   # Stage coordination, state persistence
    stage1_claims.py                  # PDF parse + LLM claim extraction
    stage2_repo/
      cloner.py                       # git clone to temp directory
      file_scope.py                   # In-scope file selection
      rule_based/
        base.py                       # RepoContext, BaseCheck, dep parsers
        runner.py                     # Runs all checks
        checks/                       # One file per check group
      llm_based/
        summarizer.py                 # Per-file LLM summaries
        retriever.py                  # Keyword-scored code span retrieval
        analyzer.py                   # Claim matching + dimension LLM checks
        prompts/                      # Prompt builders (one per analysis type)
        runner.py                     # LLM analysis orchestration
    stage3_matching.py                # Dedup, severity, cross-reference → Finding
  reporting/
    markdown.py                       # Report → report.md
```

---

## Data structures

### Claims

```python
@dataclass
class ClaimSource:
    quote: str                  # verbatim excerpt from paper
    section: Optional[str]      # e.g. "3.2"
    page: Optional[int]
    ref: Optional[str]          # e.g. "Table 2"

@dataclass
class Claim:
    id: str                     # "C-001"
    type: Literal["quantitative_result", "methodological", "data_description"]
    text: str
    source: ClaimSource
    structured: Dict[str, Any]  # e.g. {"metric": "AUC", "value": 0.92}
    confirmed: bool             # user sets False in claims.yaml to exclude
```

### Findings

```python
@dataclass
class CodeLocation:
    file: str                   # relative path from repo root
    line_start: Optional[int]
    line_end: Optional[int]
    snippet: Optional[str]

@dataclass
class RawFinding:
    """Intermediate output from a single check before dedup/severity."""
    check_id: str               # e.g. "REPRO-001"
    confidence: float           # 0.0–1.0
    code_location: Optional[CodeLocation]
    evidence: Dict[str, Any]

@dataclass
class Finding:
    id: str                     # e.g. "EVAL-001"
    instance: int               # disambiguates multiple instances of same rule
    dimension: str
    severity: Literal["critical", "important", "advisory"]
    title: str
    explanation: str
    suggestion: str
    confidence: float
    source: Literal["rule_based", "llm", "combined"]
    code_location: Optional[CodeLocation]
    claim_ref: Optional[str]    # Claim.id
    suppressed: bool
```

### Report

```python
@dataclass
class DimensionSummary:
    dimension: str
    status: Literal["issues_found", "looks_good", "could_not_assess"]
    critical: int
    important: int
    advisory: int

@dataclass
class Report:
    meta: Dict[str, str]        # paper, repo_url, repo_commit, audit_date, version
    claims: List[Claim]
    findings: List[Finding]
    summary: List[DimensionSummary]
```

---

## Stage 1: Claim extraction

**Entry point:** `pipeline/stage1_claims.py::run(config, client)`

1. Parse PDFs with `pdfplumber` (fallback: `pypdf`). Returns `List[PageText]` preserving page numbers.
2. Flatten to a single string with document/page markers.
3. Chunk if >320,000 characters (~80k tokens) — split on section headings.
4. LLM call per chunk using `extract_structured()` with the `ClaimExtractionResult` Pydantic schema (tool use / function calling).
5. Deduplicate by quote prefix (first 80 chars).
6. Write `claims.yaml` and persist state to `reproaudit_state.json`.
7. Exit — do not proceed to Stage 2.

**Cache key:** SHA256 of all input PDF file contents.

**claims.yaml format:**
```yaml
claims:
  - id: C-001
    type: quantitative_result
    text: "AUC of 0.92 on held-out test set"
    source:
      section: "4.1"
      page: 6
      ref: "Table 2"
      quote: "our model achieves an AUC of 0.92"
    structured:
      metric: AUC
      value: 0.92
      dataset: held-out test set
    confirmed: true
```

---

## Stage 2: Repository analysis

**Entry point:** `pipeline/orchestrator.py::run_stage2_and_3(config)`

### File scoping (`stage2_repo/file_scope.py`)

Includes: `.py`, `.ipynb`, `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `environment.yml`, `Makefile`, `README*`, `*.sh`

Excludes: `venv/`, `.venv/`, `__pycache__/`, `.git/`, `dist/`, `build/`, `docs/`, files >1 MB, vendored packages (subdirectories with their own `pyproject.toml`/`setup.py`)

### Rule-based analysis

**Interface:**
```python
class BaseCheck(ABC):
    check_id: str
    def run(self, ctx: RepoContext) -> List[RawFinding]: ...
```

`RepoContext` provides: in-scope file lists, lazy-cached ASTs (`get_ast(path)`), parsed dependency specs (`get_dependencies()`), and a `rel(path)` helper for relative paths.

**Dependency parsing** supports: `requirements.txt`, `pyproject.toml` (PEP 621), `setup.cfg`, `environment.yml`/`conda.yaml`.

**Check inventory:**

| File | Checks |
|------|--------|
| `checks/randomness.py` | REPRO-001, REPRO-002, REPRO-003 |
| `checks/data_leakage.py` | EVAL-001 |
| `checks/eval_metrics.py` | EVAL-005, EVAL-007 |
| `checks/paths.py` | EXEC-003 |
| `checks/dependencies.py` | EXEC-002, EXEC-005 |
| `checks/notebooks.py` | EXEC-004 |
| `checks/entry_points.py` | EXEC-001 |
| `checks/data_files.py` | DATA-003, DATA-005, EXEC-008 |
| `checks/sorting.py` | REPRO-004 |
| `checks/pinning.py` | REPRO-005 |
| `checks/gpu.py` | REPRO-006 |

### LLM-based analysis

Three sub-steps:

**1. File summarisation** (`llm_based/summarizer.py`)

Each in-scope `.py` file is summarised by the LLM: role in ML pipeline, key function/class names, framework usage. Cached by file content hash.

Output: `FileSummary(path, role, summary, key_symbols)`

**2. Code span retrieval** (`llm_based/retriever.py`)

For each confirmed claim:
- Extract query terms from claim text and structured fields
- Score file summaries by keyword overlap
- For top-3 files, keyword-search within file content
- Return ±20 lines around each match as `CodeSpan(file, line_start, line_end, snippet, relevance)`

**3. Analysis** (`llm_based/analyzer.py`)

- **Claim matching:** for each claim + retrieved spans, LLM determines match/discrepancy → `ClaimMatchResult`
- **Eval integrity:** targeted LLM prompt over evaluation file summaries and code spans → `LLMFindingResult`
- **Data availability:** LLM checks README + file summaries against paper data claims → `LLMFindingResult`

**Confidence rules:**
- Findings with confidence <0.5 are framed as questions in the report
- LLM findings are never assigned Critical severity at confidence <0.6

---

## Stage 3: Matching and reporting

**Entry point:** `pipeline/stage3_matching.py::build_findings(raw, claims, suppress)`

### Deduplication

Two `RawFinding`s are merged if:
- Same `check_id`
- Both have no `code_location`, OR same file and line numbers within 5 lines

On merge, the higher-confidence finding is kept; rule-based code location preferred over LLM.

### Severity assignment

Rule-based findings use the hardcoded catalogue in `_SEVERITIES`. LLM findings derive severity from response language, capped at Important if confidence <0.6.

### Cross-referencing

Each finding is linked to a `Claim` by matching the claim's structured fields (metric names, method names, hyperparameter names) against the finding's evidence dict.

### Report rendering (`reporting/markdown.py`)

Produces a Markdown file with:
- Header block (paper, repo, commit SHA, date)
- Summary table (one row per dimension)
- Findings grouped by dimension, sorted critical → important → advisory

---

## LLM client

```python
class LLMClient:
    def complete(self, prompt, *, max_tokens, system) -> str
    def complete_with_tool(self, prompt, tool_name, tool_description, input_schema, ...) -> dict
    def complete_batch(self, prompts, *, max_tokens, system) -> List[str]
```

`complete_with_tool` uses Anthropic tool use with `tool_choice: {type: "tool"}` to enforce structured JSON output. `extract_structured()` in `llm/structured.py` wraps this with Pydantic validation.

**Model:** `claude-sonnet-4-6` by default. Configurable via `--model` flag or `REPROAUDIT_MODEL` env var.

---

## Caching

`utils/cache.py::DiskCache` — JSON files in `reproaudit_output/analysis_cache/`, keyed by SHA256 hash (first 16 hex chars of key).

| Cache key | Content |
|-----------|---------|
| `claims:{hash_of_pdfs}` | Serialised claims list |
| `filesummary:{hash_of_file}` | FileSummary for one Python file |

Invalidated by `--no-cache` flag.

---

## Extending the tool

### Adding a new rule-based check

1. Create `src/reproaudit/pipeline/stage2_repo/rule_based/checks/mycheck.py`
2. Implement `class MyCheck(BaseCheck)` with `check_id = "XXXX-NNN"` and `run(ctx) -> List[RawFinding]`
3. Add the check to `ALL_CHECKS` in `rule_based/runner.py`
4. Add the finding ID to `_SEVERITIES`, `_TITLES`, and `_SUGGESTIONS` in `stage3_matching.py`

### Adding a new dimension

1. Add the dimension key to `DIMENSIONS_ALL` and `DIMENSION_LABELS` in `config.py`
2. Add the check ID prefix mapping to `_CHECK_TO_DIM` in `stage3_matching.py`
3. Implement checks as above
4. Add a rendering section in `reporting/markdown.py` (handled automatically if dimension key is in `DIMENSIONS_ALL`)

---

## CLI reference

```
reproaudit audit
  --paper PATH          (repeatable) PDF file path
  --repo URL            Public GitHub URL
  --output DIR          Default: ./reproaudit_output
  --model MODEL         Default: claude-sonnet-4-6
  --dimensions DIMS     Comma-separated: claim_code,eval_integrity,...
  --suppress IDS        Comma-separated finding IDs to exclude
  --no-confirm          Skip claims review, proceed immediately
  --no-cache            Disable disk cache

reproaudit resume
  --output DIR          Must match the audit run's output directory

reproaudit findings list
reproaudit findings explain <ID>
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | LLM API client |
| `click` | CLI framework |
| `pdfplumber` | PDF text extraction (primary) |
| `pypdf` | PDF text extraction (fallback) |
| `gitpython` | Repository cloning |
| `pydantic` | Structured LLM output validation |
| `ruamel.yaml` | claims.yaml read/write preserving comments |
| `rich` | Terminal output (tables, progress) |
| `packaging` | Version spec parsing for REPRO-005 |

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```

Unit tests cover: AST utilities, rule-based checks (randomness, paths, data leakage, notebooks), and Stage 3 deduplication/severity assignment.
