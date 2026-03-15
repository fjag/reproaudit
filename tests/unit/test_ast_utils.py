import ast
import textwrap
from reproaudit.utils.ast_utils import (
    get_all_string_literals,
    find_imports,
    find_calls_by_attr,
)


def _parse(src: str):
    return ast.parse(textwrap.dedent(src))


def test_string_literals():
    tree = _parse("""
        x = "/home/user/data/file.csv"
        y = "hello"
    """)
    literals = get_all_string_literals(tree)
    values = [v for v, _ in literals]
    assert "/home/user/data/file.csv" in values
    assert "hello" in values


def test_find_imports():
    tree = _parse("""
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        import torch
    """)
    imports = find_imports(tree)
    modules = {i.module for i in imports}
    assert "numpy" in modules
    assert "sklearn" in modules
    assert "torch" in modules


def test_find_calls_by_attr():
    tree = _parse("""
        import numpy as np
        np.random.seed(42)
        x = sorted(glob.glob("*.csv"))
    """)
    calls = find_calls_by_attr(tree, ["np.random.seed"])
    assert len(calls) == 1
