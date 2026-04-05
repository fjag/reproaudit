from __future__ import annotations
from pathlib import Path
from typing import List

from ....models.findings import RawFinding
from ....utils.logging import get_logger
from .base import BaseCheck, RepoContext

logger = get_logger(__name__)
from .checks.randomness import RandomnessCheck, SklearnRandomStateCheck
from .checks.paths import HardcodedPathsCheck
from .checks.dependencies import MissingDepsCheck
from .checks.notebooks import NotebookOrderCheck
from .checks.entry_points import EntryPointCheck
from .checks.data_files import DataFilesCheck
from .checks.eval_metrics import EvalMetricsCheck
from .checks.sorting import SortingCheck
from .checks.pinning import PinningCheck
from .checks.gpu import GPUDeterminismCheck
from .checks.data_leakage import DataLeakageCheck
from ..file_scope import get_in_scope_files

ALL_CHECKS: List[BaseCheck] = [
    RandomnessCheck(),
    SklearnRandomStateCheck(),
    HardcodedPathsCheck(),
    MissingDepsCheck(),
    NotebookOrderCheck(),
    EntryPointCheck(),
    DataFilesCheck(),
    EvalMetricsCheck(),
    SortingCheck(),
    PinningCheck(),
    GPUDeterminismCheck(),
    DataLeakageCheck(),
]

_CONFIG_NAMES = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "environment.yml", "environment.yaml", "conda.yaml", "conda.yml",
    "Makefile", "Pipfile",
}


def build_context(repo_root: Path) -> RepoContext:
    all_files = get_in_scope_files(repo_root)
    py_files = [f for f in all_files if f.suffix == ".py"]
    notebook_files = [f for f in all_files if f.suffix == ".ipynb"]
    config_files = [f for f in all_files if f.name in _CONFIG_NAMES]
    readme_files = [f for f in all_files if f.name.startswith("README")]
    return RepoContext(
        repo_root=repo_root,
        py_files=py_files,
        notebook_files=notebook_files,
        config_files=config_files,
        readme_files=readme_files,
    )


def run_all_checks(ctx: RepoContext) -> List[RawFinding]:
    findings: List[RawFinding] = []
    for check in ALL_CHECKS:
        try:
            logger.debug("Running check %s", check.check_id)
            results = check.run(ctx)
            findings.extend(results)
            logger.debug("Check %s found %d findings", check.check_id, len(results))
        except Exception as e:
            logger.warning("Check %s failed: %s", check.check_id, e)
    return findings
