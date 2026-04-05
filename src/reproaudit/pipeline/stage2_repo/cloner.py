from __future__ import annotations
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import git


def validate_repo_url(url: str) -> None:
    """Validate that the URL is a safe git repository URL.

    Raises ValueError if the URL is invalid or potentially unsafe.
    """
    parsed = urlparse(url)

    # Only allow https and git protocols
    if parsed.scheme not in ("https", "git", "ssh"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only https://, git://, and ssh:// URLs are allowed."
        )

    # Basic URL structure validation
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: missing host in '{url}'")

    # Block localhost and private IPs to prevent SSRF
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0") or hostname.startswith("192.168.") or hostname.startswith("10."):
        raise ValueError(f"Invalid URL: private/local addresses are not allowed: '{hostname}'")

    # Validate it looks like a git URL (has a path component)
    if not parsed.path or parsed.path == "/":
        raise ValueError(f"Invalid URL: no repository path specified in '{url}'")


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
    validate_repo_url(url)

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
