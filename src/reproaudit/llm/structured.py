from __future__ import annotations
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .client import LLMClient

T = TypeVar("T", bound=BaseModel)


def extract_structured(
    client: LLMClient,
    prompt: str,
    schema: Type[T],
    *,
    system: Optional[str] = None,
    max_tokens: int = 4096,
) -> T:
    """Force the LLM to return a structured response matching the Pydantic schema.

    Uses tool_use / function calling to enforce the schema.
    """
    tool_name = "structured_output"
    json_schema = schema.model_json_schema()

    raw = client.complete_with_tool(
        prompt,
        tool_name=tool_name,
        tool_description=f"Return structured data matching the {schema.__name__} schema.",
        input_schema=json_schema,
        max_tokens=max_tokens,
        system=system,
    )
    try:
        return schema.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"LLM output failed schema validation for {schema.__name__}: {e}") from e


# ── Shared Pydantic schemas used across pipeline stages ──────────────────────

class ExtractedClaim(BaseModel):
    type: str  # "quantitative_result" | "methodological" | "data_description"
    text: str
    section: Optional[str] = None
    page: Optional[int] = None
    ref: Optional[str] = None   # "Table 2" etc.
    quote: str
    structured: Dict[str, Any] = {}


class ClaimExtractionResult(BaseModel):
    claims: List[ExtractedClaim]


class FileSummaryResult(BaseModel):
    role: str   # e.g. "evaluation", "data_loading", "model_definition"
    summary: str
    key_symbols: List[str]  # top function/class names


class ClaimMatchResult(BaseModel):
    matches: bool
    discrepancy: Optional[str] = None
    confidence: float   # 0.0–1.0
    finding_type: Optional[str] = None  # e.g. "CLAIM-001"
    explanation: Optional[str] = None


class LLMFindingResult(BaseModel):
    found: bool
    severity: Optional[str] = None     # "critical"|"important"|"advisory"
    title: Optional[str] = None
    explanation: Optional[str] = None
    suggestion: Optional[str] = None
    confidence: float = 0.5
    file_hint: Optional[str] = None    # file where issue was found
