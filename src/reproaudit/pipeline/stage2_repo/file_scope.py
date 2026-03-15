from __future__ import annotations
from pathlib import Path
from typing import List, Set

_EXCLUDE_DIRS: Set[str] = {
    "venv", ".venv", "env", "__pycache__", ".git",
    "dist", "build", ".eggs", "node_modules", "docs", "doc",
    ".tox", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "htmlcov", ".ipynb_checkpoints",
}
_MAX_FILE_BYTES = 1_000_000  # 1 MB

_SOURCE_EXTENSIONS = {".py", ".ipynb"}
_CONFIG_NAMES = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "environment.yml", "environment.yaml", "conda.yaml", "conda.yml",
    "Makefile", "Pipfile",
}


def get_in_scope_files(repo_root: Path) -> List[Path]:
    """Return all files that should be analysed, excluding boilerplate."""
    results: List[Path] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path, repo_root):
            continue
        if path.stat().st_size > _MAX_FILE_BYTES:
            continue
        if (
            path.suffix in _SOURCE_EXTENSIONS
            or path.name in _CONFIG_NAMES
            or path.name.startswith("README")
            or path.suffix == ".sh"
        ):
            results.append(path)

    return sorted(results)


def _is_excluded(path: Path, root: Path) -> bool:
    """True if any component of the path relative to root is in the exclude set."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in _EXCLUDE_DIRS for part in rel.parts)


def is_vendored_package(directory: Path, repo_root: Path) -> bool:
    """True if a directory looks like a vendored package (has its own setup.py/pyproject.toml)."""
    if directory == repo_root:
        return False
    return (directory / "setup.py").exists() or (directory / "pyproject.toml").exists()
