from reproaudit.models.findings import RawFinding, CodeLocation
from reproaudit.pipeline.stage3_matching import build_findings, _deduplicate


def test_deduplication_same_location():
    raw = [
        RawFinding("REPRO-001", 0.9),
        RawFinding("REPRO-001", 0.8),  # duplicate, no location
    ]
    deduped = _deduplicate(raw)
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.9


def test_deduplication_different_checks():
    raw = [
        RawFinding("REPRO-001", 0.9),
        RawFinding("EXEC-003", 0.9),
    ]
    deduped = _deduplicate(raw)
    assert len(deduped) == 2


def test_build_findings_assigns_dimension():
    raw = [RawFinding("EVAL-001", 0.9)]
    findings = build_findings(raw, claims=[], suppress=set())
    assert len(findings) == 1
    assert findings[0].dimension == "eval_integrity"
    assert findings[0].severity == "critical"


def test_suppress():
    raw = [RawFinding("REPRO-004", 0.9)]
    findings = build_findings(raw, claims=[], suppress={"REPRO-004"})
    assert len(findings) == 0
