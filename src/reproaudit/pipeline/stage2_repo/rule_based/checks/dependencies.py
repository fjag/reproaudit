"""EXEC-002: unresolvable imports
EXEC-005: no dependency specification found
"""
from __future__ import annotations
import sys
from typing import List, Set

from .....models.findings import RawFinding
from .....utils.ast_utils import find_imports
from .....utils.import_map import import_to_install
from ..base import BaseCheck, RepoContext

# Standard library top-level modules (Python 3.11+)
try:
    _STDLIB: Set[str] = set(sys.stdlib_module_names)  # type: ignore[attr-defined]
except AttributeError:
    _STDLIB = {
        "abc", "ast", "asyncio", "builtins", "collections", "contextlib",
        "copy", "csv", "dataclasses", "datetime", "enum", "functools",
        "hashlib", "io", "itertools", "json", "logging", "math", "operator",
        "os", "pathlib", "pickle", "platform", "queue", "random", "re",
        "shutil", "signal", "socket", "sqlite3", "string", "struct",
        "subprocess", "sys", "tempfile", "threading", "time", "traceback",
        "types", "typing", "unittest", "urllib", "uuid", "warnings",
        "weakref", "xml", "zipfile", "configparser", "argparse", "glob",
        "inspect", "importlib", "tomllib", "tomlib",
    }

_KNOWN_FIRST_PARTY = {"reproaudit", "src"}


class MissingDepsCheck(BaseCheck):
    check_id = "EXEC-005"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []

        if not ctx.config_files:
            findings.append(RawFinding(
                check_id="EXEC-005",
                confidence=0.99,
                evidence={"message": "No dependency specification file found (requirements.txt, pyproject.toml, etc.)"},
            ))
            return findings

        # Check for unresolvable imports
        declared = ctx.get_dependencies()  # {install_name_lower: version}
        declared_keys = set(declared.keys())

        all_imports: Set[str] = set()
        for path in ctx.py_files:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            for imp in find_imports(tree):
                all_imports.add(imp.module)

        for mod in all_imports:
            if mod in _STDLIB:
                continue
            if mod in _KNOWN_FIRST_PARTY:
                continue
            install_name = import_to_install(mod).lower()
            if install_name not in declared_keys and mod.lower() not in declared_keys:
                findings.append(RawFinding(
                    check_id="EXEC-002",
                    confidence=0.75,
                    evidence={"import_name": mod, "install_name": import_to_install(mod)},
                ))

        return findings
