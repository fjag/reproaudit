from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple


@dataclass
class ImportInfo:
    module: str        # top-level module name, e.g. "numpy"
    alias: Optional[str]
    lineno: int
    is_from: bool


def get_ast(path: Path) -> Optional[ast.Module]:
    """Parse a Python file to AST. Returns None on syntax error."""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None


def find_calls(tree: ast.Module, func_names: Set[str]) -> List[ast.Call]:
    """Find all Call nodes where the function name is in func_names.

    Matches simple names (seed) and attribute access (np.random.seed, random.seed).
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name and any(name == fn or name.endswith(f".{fn}") for fn in func_names):
                results.append(node)
    return results


def find_calls_by_attr(tree: ast.Module, attr_chains: List[str]) -> List[Tuple[ast.Call, int]]:
    """Find calls matching dot-separated chains like 'np.random.seed'.

    Returns (call_node, lineno) tuples.
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name and name in attr_chains:
                results.append((node, getattr(node, "lineno", 0)))
    return results


def find_imports(tree: ast.Module) -> List[ImportInfo]:
    """Extract all import statements from an AST."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                results.append(ImportInfo(top, alias.asname, node.lineno, False))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                results.append(ImportInfo(top, None, node.lineno, True))
    return results


def get_all_string_literals(tree: ast.Module) -> List[Tuple[str, int]]:
    """Return all string constant values and their line numbers."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            results.append((node.value, node.lineno))
    return results


def find_class_instantiations(tree: ast.Module, class_names: Set[str]) -> List[Tuple[ast.Call, int]]:
    """Find instantiations of classes by name (simple name match)."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name:
                simple = name.split(".")[-1]
                if simple in class_names:
                    results.append((node, getattr(node, "lineno", 0)))
    return results


def _call_name(node: ast.Call) -> Optional[str]:
    """Extract the dotted name of a call's function, e.g. 'np.random.seed'."""
    parts = []
    func = node.func
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    elif isinstance(func, ast.Constant):
        return None
    else:
        return None
    return ".".join(reversed(parts))


def get_top_level_statement_order(tree: ast.Module) -> List[Tuple[ast.stmt, int]]:
    """Return (statement, lineno) for all top-level statements in order."""
    return [(stmt, getattr(stmt, "lineno", 0)) for stmt in tree.body]
