import json, tempfile
from pathlib import Path
from reproaudit.pipeline.stage2_repo.rule_based.base import RepoContext
from reproaudit.pipeline.stage2_repo.rule_based.checks.notebooks import NotebookOrderCheck


def _make_nb(execution_counts):
    cells = [
        {"cell_type": "code", "execution_count": c, "source": [], "outputs": []}
        for c in execution_counts
    ]
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": cells}


def test_detects_out_of_order():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        nb_path = root / "analysis.ipynb"
        nb_path.write_text(json.dumps(_make_nb([1, 3, 2, 4])))
        ctx = RepoContext(root, [], [nb_path], [], [])
        findings = NotebookOrderCheck().run(ctx)
        assert any(r.check_id == "EXEC-004" for r in findings)


def test_no_finding_for_ordered():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        nb_path = root / "analysis.ipynb"
        nb_path.write_text(json.dumps(_make_nb([1, 2, 3, 4])))
        ctx = RepoContext(root, [], [nb_path], [], [])
        findings = NotebookOrderCheck().run(ctx)
        assert not findings
