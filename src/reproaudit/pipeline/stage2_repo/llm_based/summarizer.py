from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from ....llm.client import LLMClient
from ....llm.structured import FileSummaryResult, extract_structured
from ....utils.cache import DiskCache, hash_file
from .prompts import file_summary as _fp


@dataclass
class FileSummary:
    path: str   # relative path
    role: str
    summary: str
    key_symbols: List[str]


def summarize_files(
    py_files: List[Path],
    repo_root: Path,
    client: LLMClient,
    cache: DiskCache,
) -> List[FileSummary]:
    results: List[FileSummary] = []
    for path in py_files:
        rel = str(path.relative_to(repo_root))
        cache_key = f"filesummary:{hash_file(path)}"
        cached = cache.get(cache_key)
        if cached:
            results.append(FileSummary(**cached))
            continue
        try:
            code = path.read_text(encoding="utf-8", errors="replace")
            prompt = _fp.build(rel, code)
            result = extract_structured(client, prompt, FileSummaryResult, system=_fp.SYSTEM)
            fs = FileSummary(path=rel, role=result.role, summary=result.summary, key_symbols=result.key_symbols)
            cache.set(cache_key, {"path": fs.path, "role": fs.role, "summary": fs.summary, "key_symbols": fs.key_symbols})
            results.append(fs)
        except Exception as e:
            import warnings
            warnings.warn(f"File summary failed for {rel}: {e}")
            results.append(FileSummary(path=rel, role="unknown", summary="(summary failed)", key_symbols=[]))
    return results
