import textwrap, tempfile
from pathlib import Path
from reproaudit.pipeline.stage2_repo.rule_based.base import RepoContext
from reproaudit.pipeline.stage2_repo.rule_based.checks.data_leakage import DataLeakageCheck


def test_detects_fit_before_split():
    code = textwrap.dedent("""
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_train, X_test = train_test_split(X_scaled)
    """)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "pipeline.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = DataLeakageCheck().run(ctx)
        assert any(r.check_id == "EVAL-001" for r in findings)


def test_no_finding_for_correct_order():
    code = textwrap.dedent("""
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        X_train, X_test = train_test_split(X)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    """)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = root / "pipeline.py"
        f.write_text(code)
        ctx = RepoContext(root, [f], [], [], [])
        findings = DataLeakageCheck().run(ctx)
        assert not findings
