from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Optional

import git


class ClonedRepo:
    def __init__(self, path: Path, commit_sha: str, url: str):
        self.path = path
        self.commit_sha = commit_sha
        self.url = url
        self._tmpdir: Optional[tempfile.TemporaryDirectory] = None

    def cleanup(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()


def clone_repo(url: str) -> ClonedRepo:
    """Clone a public GitHub repo to a temp directory. Returns ClonedRepo."""
    tmpdir = tempfile.TemporaryDirectory(prefix="reproaudit_")
    dest = Path(tmpdir.name) / "repo"
    try:
        repo = git.Repo.clone_from(url, str(dest), depth=1)
    except git.GitCommandError as e:
        tmpdir.cleanup()
        raise RuntimeError(f"Failed to clone {url}: {e}") from e

    sha = repo.head.commit.hexsha
    result = ClonedRepo(path=dest, commit_sha=sha, url=url)
    result._tmpdir = tmpdir
    return result
