from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import ast

from ....models.findings import CodeLocation, RawFinding


@dataclass
class RepoContext:
    """All pre-computed data available to rule-based checks."""
    repo_root: Path
    py_files: List[Path]         # in-scope .py files
    notebook_files: List[Path]   # in-scope .ipynb files
    config_files: List[Path]     # requirements.txt, pyproject.toml, etc.
    readme_files: List[Path]
    _ast_cache: Dict[str, Optional[ast.Module]] = field(default_factory=dict, repr=False)
    _dep_cache: Optional[Dict[str, str]] = field(default=None, repr=False)

    def get_ast(self, path: Path) -> Optional[ast.Module]:
        key = str(path)
        if key not in self._ast_cache:
            from ....utils.ast_utils import get_ast
            self._ast_cache[key] = get_ast(path)
        return self._ast_cache[key]

    def get_dependencies(self) -> Dict[str, str]:
        """Return {install_name: version_spec} parsed from all dep specs."""
        if self._dep_cache is None:
            self._dep_cache = _parse_all_deps(self.config_files)
        return self._dep_cache

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.repo_root))


def _parse_all_deps(config_files: List[Path]) -> Dict[str, str]:
    deps: Dict[str, str] = {}
    for f in config_files:
        deps.update(_parse_dep_file(f))
    return deps


def _parse_dep_file(path: Path) -> Dict[str, str]:
    name = path.name.lower()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    if "requirements" in name and name.endswith(".txt"):
        return _parse_requirements_txt(text)
    if name == "pyproject.toml":
        return _parse_pyproject_toml(text)
    if name in ("setup.cfg",):
        return _parse_setup_cfg(text)
    if name in ("environment.yml", "environment.yaml", "conda.yaml", "conda.yml"):
        return _parse_conda_env(text)
    return {}


def _parse_requirements_txt(text: str) -> Dict[str, str]:
    deps = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        import re
        m = re.match(r"^([A-Za-z0-9_\-\.]+)(.*)", line)
        if m:
            deps[m.group(1).lower()] = m.group(2).strip()
    return deps


def _parse_pyproject_toml(text: str) -> Dict[str, str]:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {}
    import re
    try:
        data = tomllib.loads(text)
    except Exception:
        return {}
    deps: Dict[str, str] = {}
    for dep_str in data.get("project", {}).get("dependencies", []):
        m = re.match(r"^([A-Za-z0-9_\-\.]+)(.*)", dep_str)
        if m:
            deps[m.group(1).lower()] = m.group(2).strip()
    return deps


def _parse_setup_cfg(text: str) -> Dict[str, str]:
    import configparser, re
    cfg = configparser.ConfigParser()
    try:
        cfg.read_string(text)
    except Exception:
        return {}
    deps = {}
    raw = cfg.get("options", "install_requires", fallback="")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z0-9_\-\.]+)(.*)", line)
        if m:
            deps[m.group(1).lower()] = m.group(2).strip()
    return deps


def _parse_conda_env(text: str) -> Dict[str, str]:
    try:
        import yaml as _yaml
    except ImportError:
        return {}
    import re
    try:
        data = _yaml.safe_load(text)
    except Exception:
        return {}
    deps = {}
    for item in data.get("dependencies", []):
        if isinstance(item, str):
            m = re.match(r"^([A-Za-z0-9_\-\.]+)(.*)", item)
            if m:
                deps[m.group(1).lower()] = m.group(2).strip()
        elif isinstance(item, dict):
            for dep_str in item.get("pip", []):
                m = re.match(r"^([A-Za-z0-9_\-\.]+)(.*)", dep_str)
                if m:
                    deps[m.group(1).lower()] = m.group(2).strip()
    return deps


class BaseCheck(ABC):
    check_id: str

    @abstractmethod
    def run(self, ctx: RepoContext) -> List[RawFinding]:
        ...

    def _loc(self, path: Path, ctx: RepoContext, line_start: Optional[int] = None,
             line_end: Optional[int] = None, snippet: Optional[str] = None) -> CodeLocation:
        return CodeLocation(
            file=ctx.rel(path),
            line_start=line_start,
            line_end=line_end,
            snippet=snippet,
        )
