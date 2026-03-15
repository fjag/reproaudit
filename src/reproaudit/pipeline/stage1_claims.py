from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML

from ..config import Config
from ..llm.client import LLMClient
from ..llm.structured import ClaimExtractionResult, ExtractedClaim, extract_structured
from ..models.claims import Claim, ClaimSource
from ..utils.cache import DiskCache, hash_files
from ..utils.pdf import extract_pdf_text, pages_to_text


_SYSTEM = """\
You are a scientific paper analysis assistant specializing in machine learning and computational biology.
Your task is to extract structured claims from research papers to support reproducibility auditing.
Be precise: only extract claims that are explicitly stated in the paper text.
Do not infer or hallucinate values. Quote the paper verbatim whenever possible.
"""

_PROMPT_TMPL = """\
Extract all verifiable claims from the following research paper text.

Focus on three types of claims:

1. **quantitative_result** — Reported numeric results: metric values (AUC, F1, accuracy, RMSE, p-value, etc.),
   dataset statistics, sample sizes, train/test split ratios. Include the table or figure reference if present.

2. **methodological** — Descriptions of methods: model architecture, algorithm choices, hyperparameter values
   (learning rate, batch size, epochs, number of layers, regularization, etc.), preprocessing steps,
   evaluation protocol, cross-validation strategy.

3. **data_description** — Data sources, dataset names, sample sizes, cohort descriptions, inclusion/exclusion
   criteria, data access information.

For each claim, include:
- The exact verbatim quote from the paper
- The section and page number where it appears (if determinable from the text)
- Any figure/table reference (e.g. "Table 2", "Figure 3")
- A structured dict with key fields (e.g. {{"metric": "AUC", "value": 0.92, "dataset": "test set"}})

--- PAPER TEXT ---
{text}
--- END PAPER TEXT ---

Extract all claims now.
"""

# Approximate token count (4 chars ≈ 1 token)
_MAX_CHARS = 320_000  # ~80k tokens


def run(config: Config, client: LLMClient) -> List[Claim]:
    """Stage 1: Extract claims from PDFs and write claims.yaml.

    Returns the list of extracted claims. Also writes claims.yaml to output_dir.
    If claims.yaml already exists (user edited it), loads from there instead.
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # If claims.yaml already exists, load from it (resume path)
    if config.claims_path.exists():
        return _load_claims_yaml(config.claims_path)

    # Check cache
    cache = DiskCache(config.cache_dir)
    cache_key = f"claims:{hash_files(config.paper_paths)}"

    if not config.no_cache and cache.has(cache_key):
        raw = cache.get(cache_key)
        claims = _deserialize_claims(raw)
        _write_claims_yaml(config.claims_path, claims)
        return claims

    # Parse PDFs
    pages = extract_pdf_text(config.paper_paths)
    full_text = pages_to_text(pages)

    # Chunk if too long
    chunks = _chunk_text(full_text, _MAX_CHARS)
    all_extracted: List[ExtractedClaim] = []

    for i, chunk in enumerate(chunks):
        prompt = _PROMPT_TMPL.format(text=chunk)
        try:
            result = extract_structured(
                client,
                prompt,
                ClaimExtractionResult,
                system=_SYSTEM,
                max_tokens=8192,
            )
            all_extracted.extend(result.claims)
        except Exception as e:
            # Degrade gracefully: skip chunk, note failure
            import warnings
            warnings.warn(f"Claim extraction failed on chunk {i+1}/{len(chunks)}: {e}")

    # Deduplicate by quote similarity
    all_extracted = _deduplicate(all_extracted)

    # Convert to domain models
    claims = _to_claims(all_extracted)

    # Cache and write
    cache.set(cache_key, _serialize_claims(claims))
    _write_claims_yaml(config.claims_path, claims)

    return claims


def _chunk_text(text: str, max_chars: int) -> List[str]:
    """Split text into chunks at section boundaries if possible."""
    if len(text) <= max_chars:
        return [text]

    # Try to split on section headings (numbered or all-caps lines)
    section_pattern = re.compile(r"\n(?=\d+[\.\s]+[A-Z]|\n[A-Z]{4,})")
    parts = section_pattern.split(text)

    chunks: List[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) > max_chars:
            if current:
                chunks.append(current)
            current = part
        else:
            current += part
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _deduplicate(extracted: List[ExtractedClaim]) -> List[ExtractedClaim]:
    """Remove near-duplicate claims (same quote prefix)."""
    seen: set[str] = set()
    result: List[ExtractedClaim] = []
    for claim in extracted:
        key = claim.quote[:80].lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(claim)
    return result


def _to_claims(extracted: List[ExtractedClaim]) -> List[Claim]:
    claims = []
    for i, e in enumerate(extracted, start=1):
        claim_id = f"C-{i:03d}"
        source = ClaimSource(
            quote=e.quote,
            section=e.section,
            page=e.page,
            ref=e.ref,
        )
        claim_type = e.type if e.type in (
            "quantitative_result", "methodological", "data_description"
        ) else "methodological"
        claims.append(Claim(
            id=claim_id,
            type=claim_type,
            text=e.text,
            source=source,
            structured=e.structured,
            confirmed=True,
        ))
    return claims


# ── YAML serialisation ────────────────────────────────────────────────────────

def _write_claims_yaml(path: Path, claims: List[Claim]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True

    data = {
        "claims": [
            {
                "id": c.id,
                "type": c.type,
                "text": c.text,
                "source": {
                    "section": c.source.section,
                    "page": c.source.page,
                    "ref": c.source.ref,
                    "quote": c.source.quote,
                },
                "structured": c.structured,
                "confirmed": c.confirmed,
            }
            for c in claims
        ]
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


def _load_claims_yaml(path: Path) -> List[Claim]:
    yaml = YAML()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    claims = []
    for item in data.get("claims", []):
        src = item.get("source", {})
        source = ClaimSource(
            quote=src.get("quote", ""),
            section=src.get("section"),
            page=src.get("page"),
            ref=src.get("ref"),
        )
        claims.append(Claim(
            id=item["id"],
            type=item.get("type", "methodological"),
            text=item.get("text", ""),
            source=source,
            structured=dict(item.get("structured") or {}),
            confirmed=item.get("confirmed", True),
        ))
    return claims


def _serialize_claims(claims: List[Claim]) -> list:
    return [
        {
            "id": c.id, "type": c.type, "text": c.text,
            "source": {
                "quote": c.source.quote, "section": c.source.section,
                "page": c.source.page, "ref": c.source.ref,
            },
            "structured": c.structured, "confirmed": c.confirmed,
        }
        for c in claims
    ]


def _deserialize_claims(raw: list) -> List[Claim]:
    claims = []
    for item in raw:
        src = item.get("source", {})
        claims.append(Claim(
            id=item["id"], type=item["type"], text=item["text"],
            source=ClaimSource(
                quote=src.get("quote", ""), section=src.get("section"),
                page=src.get("page"), ref=src.get("ref"),
            ),
            structured=item.get("structured", {}),
            confirmed=item.get("confirmed", True),
        ))
    return claims
