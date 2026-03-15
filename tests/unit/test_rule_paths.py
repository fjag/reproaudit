import textwrap, tempfile
from pathlib import Path
from reproaudit.pipeline.stage2_repo.rule_based.base import RepoContext
from reproaudit.pipeline.stage2_repo.rule_based.checks.paths import HardcodedPathsCheck


def test_detects_hardcoded_path():
    code = 'data_path = "/home/alice/research/data/train.csv"'
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "load.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = HardcodedPathsCheck().run(ctx)
        assert any(r.check_id == "EXEC-003" for r in findings)


def test_no_finding_for_relative_path():
    code = 'data_path = "data/train.csv"'
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "load.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = HardcodedPathsCheck().run(ctx)
        assert not findings
