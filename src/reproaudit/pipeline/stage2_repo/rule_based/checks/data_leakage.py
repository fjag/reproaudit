"""EVAL-001: preprocessing fit() before train/test split (intrafile check)."""
from __future__ import annotations
import ast
from typing import List, Optional, Set

from .....models.findings import RawFinding
from .....utils.ast_utils import find_imports
from ..base import BaseCheck, RepoContext

_TRANSFORMERS: Set[str] = {
    "StandardScaler", "MinMaxScaler", "RobustScaler", "MaxAbsScaler",
    "Normalizer", "Binarizer", "LabelEncoder", "OrdinalEncoder",
    "OneHotEncoder", "LabelBinarizer", "MultiLabelBinarizer",
    "SimpleImputer", "KNNImputer", "IterativeImputer",
    "PolynomialFeatures", "PowerTransformer", "QuantileTransformer",
    "PCA", "TruncatedSVD", "NMF", "FastICA",
    "TfidfVectorizer", "CountVectorizer", "HashingVectorizer",
    "Pipeline", "ColumnTransformer",
}

_SPLIT_FUNCS = {"train_test_split", "KFold", "StratifiedKFold", "GroupKFold",
                "TimeSeriesSplit", "RepeatedKFold"}


class DataLeakageCheck(BaseCheck):
    check_id = "EVAL-001"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for path in ctx.py_files:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            finding = _check_file(tree, path, ctx)
            if finding:
                findings.append(finding)
        return findings


def _check_file(tree: ast.Module, path, ctx) -> Optional[RawFinding]:
    """Check if a .fit() call on a transformer appears before a split call."""
    fit_lineno: Optional[int] = None
    split_lineno: Optional[int] = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Look for .fit( or .fit_transform( calls
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("fit", "fit_transform"):
                lineno = getattr(node, "lineno", 0)
                if fit_lineno is None or lineno < fit_lineno:
                    fit_lineno = lineno
            # Look for split calls
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in _SPLIT_FUNCS:
                lineno = getattr(node, "lineno", 0)
                if split_lineno is None or lineno < split_lineno:
                    split_lineno = lineno

    if fit_lineno is not None and split_lineno is not None and fit_lineno < split_lineno:
        from .....models.findings import CodeLocation
        return RawFinding(
            check_id="EVAL-001",
            confidence=0.7,
            code_location=CodeLocation(
                file=ctx.rel(path),
                line_start=fit_lineno,
                snippet=f"fit() at line {fit_lineno}, split at line {split_lineno}",
            ),
            evidence={"fit_lineno": fit_lineno, "split_lineno": split_lineno},
        )
    return None
