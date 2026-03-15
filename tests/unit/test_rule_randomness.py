import ast
import textwrap
from pathlib import Path
import tempfile

from reproaudit.pipeline.stage2_repo.rule_based.base import RepoContext
from reproaudit.pipeline.stage2_repo.rule_based.checks.randomness import RandomnessCheck


def _make_context(py_code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "train.py"
        f.write_text(py_code)
        ctx = RepoContext(
            repo_root=root,
            py_files=[f],
            notebook_files=[],
            config_files=[],
            readme_files=[],
        )
        return ctx, root, f


def test_detects_missing_seed():
    code = textwrap.dedent("""
        import numpy as np
        def main():
            model = np.random.randn(10)
        if __name__ == "__main__":
            main()
    """)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "train.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = RandomnessCheck().run(ctx)
        assert any(r.check_id == "REPRO-001" for r in findings)


def test_no_finding_when_seeded():
    code = textwrap.dedent("""
        import numpy as np
        import random
        random.seed(42)
        np.random.seed(42)
        if __name__ == "__main__":
            pass
    """)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "train.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = RandomnessCheck().run(ctx)
        repro1 = [r for r in findings if r.check_id == "REPRO-001"]
        assert len(repro1) == 0
