from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ....llm.client import LLMClient
from ....llm.structured import FileSummaryResult, extract_structured
from ....utils.cache import DiskCache, hash_file
from ....utils.logging import get_logger
from .prompts import file_summary as _fp

logger = get_logger(__name__)

# Maximum parallel LLM requests (to avoid rate limiting)
_MAX_PARALLEL_WORKERS = 4


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
    parallel: bool = True,
) -> List[FileSummary]:
    """Summarize Python files using LLM.

    Args:
        py_files: List of Python file paths to summarize.
        repo_root: Root path of the repository.
        client: LLM client for API calls.
        cache: Disk cache for storing results.
        parallel: If True, process uncached files in parallel.

    Returns:
        List of FileSummary objects in the same order as input files.
    """
    # First pass: collect cached results and identify uncached files
    results: Dict[int, FileSummary] = {}
    uncached: List[Tuple[int, Path, str]] = []  # (index, path, rel_path)

    for i, path in enumerate(py_files):
        rel = str(path.relative_to(repo_root))
        cache_key = f"filesummary:{hash_file(path)}"
        cached = cache.get(cache_key)
        if cached:
            results[i] = FileSummary(**cached)
            logger.debug("Cache hit for %s", rel)
        else:
            uncached.append((i, path, rel))

    if not uncached:
        logger.info("All %d files found in cache", len(py_files))
        return [results[i] for i in range(len(py_files))]

    logger.info("Summarizing %d files (%d cached)", len(uncached), len(results))

    if parallel and len(uncached) > 1:
        # Process uncached files in parallel
        _summarize_parallel(uncached, repo_root, client, cache, results)
    else:
        # Process sequentially
        for idx, path, rel in uncached:
            results[idx] = _summarize_single(path, rel, client, cache)

    return [results[i] for i in range(len(py_files))]


def _summarize_single(
    path: Path,
    rel: str,
    client: LLMClient,
    cache: DiskCache,
) -> FileSummary:
    """Summarize a single file."""
    try:
        logger.debug("Summarizing file: %s", rel)
        code = path.read_text(encoding="utf-8", errors="replace")
        prompt = _fp.build(rel, code)
        result = extract_structured(client, prompt, FileSummaryResult, system=_fp.SYSTEM)
        fs = FileSummary(path=rel, role=result.role, summary=result.summary, key_symbols=result.key_symbols)

        # Cache the result
        cache_key = f"filesummary:{hash_file(path)}"
        cache.set(cache_key, {"path": fs.path, "role": fs.role, "summary": fs.summary, "key_symbols": fs.key_symbols})

        logger.debug("Summarized %s: role=%s", rel, fs.role)
        return fs
    except (RuntimeError, ValueError, OSError, IOError) as e:
        logger.warning("File summary failed for %s: %s", rel, e)
        return FileSummary(path=rel, role="unknown", summary="(summary failed)", key_symbols=[])


def _summarize_parallel(
    uncached: List[Tuple[int, Path, str]],
    repo_root: Path,
    client: LLMClient,
    cache: DiskCache,
    results: Dict[int, FileSummary],
) -> None:
    """Process multiple files in parallel using ThreadPoolExecutor."""

    def process_file(item: Tuple[int, Path, str]) -> Tuple[int, FileSummary]:
        idx, path, rel = item
        return idx, _summarize_single(path, rel, client, cache)

    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_WORKERS) as executor:
        futures = {executor.submit(process_file, item): item[0] for item in uncached}

        for future in as_completed(futures):
            idx = futures[future]
            try:
                result_idx, summary = future.result()
                results[result_idx] = summary
            except Exception as e:
                # Get the rel path for logging
                rel = next((item[2] for item in uncached if item[0] == idx), "unknown")
                logger.warning("Parallel summary failed for %s: %s", rel, e)
                results[idx] = FileSummary(path=rel, role="unknown", summary="(summary failed)", key_symbols=[])
