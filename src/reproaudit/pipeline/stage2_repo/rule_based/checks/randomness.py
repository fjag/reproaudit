"""REPRO-001: no random.seed in entry points
REPRO-002: numpy/torch/tf generators not seeded
REPRO-003: sklearn estimators lack random_state
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Set

from .....models.findings import RawFinding
from .....utils.ast_utils import find_calls_by_attr, find_class_instantiations, get_ast
from ..base import BaseCheck, RepoContext

_SEED_CALLS = [
    "random.seed",
    "np.random.seed",
    "numpy.random.seed",
    "torch.manual_seed",
    "torch.cuda.manual_seed",
    "torch.cuda.manual_seed_all",
    "tf.random.set_seed",
    "tensorflow.random.set_seed",
    "random.set_seed",          # keras
]

_SKLEARN_ESTIMATORS: Set[str] = {
    "RandomForestClassifier", "RandomForestRegressor",
    "GradientBoostingClassifier", "GradientBoostingRegressor",
    "ExtraTreesClassifier", "ExtraTreesRegressor",
    "BaggingClassifier", "BaggingRegressor",
    "AdaBoostClassifier", "AdaBoostRegressor",
    "SVR", "SVC", "NuSVC", "NuSVR",
    "LogisticRegression", "LinearRegression",
    "KMeans", "MiniBatchKMeans", "DBSCAN",
    "train_test_split", "KFold", "StratifiedKFold",
    "ShuffleSplit", "StratifiedShuffleSplit",
    "MLPClassifier", "MLPRegressor",
    "DecisionTreeClassifier", "DecisionTreeRegressor",
    "SGDClassifier", "SGDRegressor",
}


def _is_entry_point(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return '__name__' in text and '__main__' in text
    except OSError:
        return False


class RandomnessCheck(BaseCheck):
    check_id = "REPRO-001"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []

        entry_points = [f for f in ctx.py_files if _is_entry_point(f)]
        if not entry_points:
            entry_points = ctx.py_files  # fall back to all files

        # Collect which seed calls are present anywhere in entry points
        found_seeds: Set[str] = set()
        for path in entry_points:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            calls = find_calls_by_attr(tree, _SEED_CALLS)
            for _, _ in calls:
                for seed in _SEED_CALLS:
                    found_seeds.add(seed.split(".")[0])  # "random", "np", "torch", "tf"

        missing: List[str] = []
        # Check if any seeding exists at all
        if not found_seeds:
            findings.append(RawFinding(
                check_id="REPRO-001",
                confidence=0.9,
                evidence={"message": "No random seed calls found in any entry-point script."},
            ))

        # Check framework-specific seeds
        frameworks_used = _detect_frameworks(ctx)
        for fw, seed_fn, repro_id in [
            ("numpy", "np.random.seed", "REPRO-002"),
            ("torch", "torch.manual_seed", "REPRO-002"),
            ("tensorflow", "tf.random.set_seed", "REPRO-002"),
        ]:
            if fw in frameworks_used and not any(
                s.startswith(seed_fn.split(".")[0]) for s in found_seeds
            ):
                findings.append(RawFinding(
                    check_id=repro_id,
                    confidence=0.85,
                    evidence={"framework": fw, "expected_seed_call": seed_fn},
                ))

        return findings


class SklearnRandomStateCheck(BaseCheck):
    check_id = "REPRO-003"

    def run(self, ctx: RepoContext) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for path in ctx.py_files:
            tree = ctx.get_ast(path)
            if tree is None:
                continue
            instances = find_class_instantiations(tree, _SKLEARN_ESTIMATORS)
            for call_node, lineno in instances:
                import ast as _ast
                kwarg_names = {kw.arg for kw in call_node.keywords}
                if "random_state" not in kwarg_names:
                    # Check if the estimator even accepts random_state
                    func_name = ""
                    if isinstance(call_node.func, _ast.Attribute):
                        func_name = call_node.func.attr
                    elif isinstance(call_node.func, _ast.Name):
                        func_name = call_node.func.id
                    if func_name in _SKLEARN_ESTIMATORS:
                        findings.append(RawFinding(
                            check_id="REPRO-003",
                            confidence=0.8,
                            code_location=self._loc(path, ctx, lineno, lineno),
                            evidence={"estimator": func_name},
                        ))
        return findings


def _detect_frameworks(ctx: RepoContext) -> Set[str]:
    frameworks: Set[str] = set()
    deps = ctx.get_dependencies()
    if "numpy" in deps or "np" in deps:
        frameworks.add("numpy")
    if "torch" in deps:
        frameworks.add("torch")
    if "tensorflow" in deps or "tensorflow-gpu" in deps:
        frameworks.add("tensorflow")
    # Also check imports
    from .....utils.ast_utils import find_imports
    for path in ctx.py_files:
        tree = ctx.get_ast(path)
        if tree is None:
            continue
        for imp in find_imports(tree):
            if imp.module in ("numpy", "np"):
                frameworks.add("numpy")
            elif imp.module == "torch":
                frameworks.add("torch")
            elif imp.module in ("tensorflow", "tf"):
                frameworks.add("tensorflow")
    return frameworks
