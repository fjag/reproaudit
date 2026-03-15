"""Smoke test — verifies the package is importable."""

def test_import():
    import reproaudit  # noqa: F401
    from reproaudit.models.claims import Claim, ClaimSource
    from reproaudit.models.findings import Finding, CodeLocation, RawFinding
    from reproaudit.models.report import Report, DimensionSummary
    assert True
