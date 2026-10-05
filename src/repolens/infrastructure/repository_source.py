"""Validated local/public GitHub sources with explicit workspace lifetime."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from repolens.domain.models import Repository
from repolens.infrastructure.errors import AcquisitionError, GitFailed, InvalidSource
from repolens.infrastructure.git import GitExecution, GitRunner


def canonical_github_url(value: str) -> str:
    """Accept repository roots only; invalid input is never echoed in errors."""
    try:
        url = urlsplit(value)
    except ValueError:
        raise InvalidSource("Expected a public GitHub HTTPS repository URL") from None
    if (
        url.scheme != "https"
        or url.netloc != "github.com"
        or url.query
        or url.fragment
        or "?" in value
        or "#" in value
        or any(ord(character) <= 32 or ord(character) == 127 for character in value)
    ):
        raise InvalidSource("Expected a public GitHub HTTPS repository URL")
    path = url.path.removesuffix("/")
    parts = path.split("/")
    if len(parts) != 3 or parts[0] != "":
        raise InvalidSource("GitHub URL must identify a repository root")
    owner, repository = parts[1], parts[2].removesuffix(".git")
    if (
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner) is None
        or "--" in owner
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repository) is None
        or repository in {".", ".."}
        or repository.startswith("-")
    ):
        raise InvalidSource("GitHub owner or repository name is invalid")
    return f"https://github.com/{owner}/{repository}.git"


class SourceKind(StrEnum):
    LOCAL = "local"
    GITHUB = "github"


@contextmanager
def _temporary_workspace() -> Iterator[Path]:
    """Sanitize allocation/cleanup failures without intercepting consumer exceptions."""
    try:
        workspace = TemporaryDirectory(prefix="repolens-source-")
    except OSError:
        raise AcquisitionError("Temporary workspace could not be created") from None
    try:
        yield Path(workspace.name)
    finally:
        try:
            workspace.cleanup()
        except OSError:
            raise AcquisitionError("Temporary workspace cleanup failed") from None


class RepositoryLease:
    """Access root only during the owning context; raw copied paths cannot be revoked."""

    def __init__(
        self,
        root: Path,
        identity: Repository,
        kind: SourceKind,
        commit_sha: str | None,
        canonical_url: str | None = None,
    ) -> None:
        self._root = root
        self.identity = identity
        self.kind = kind
        self.commit_sha = commit_sha
        self.canonical_url = canonical_url
        self._active = True

    @property
    def root(self) -> Path:
        if not self._active:
            raise AcquisitionError("Repository lease is closed")
        return self._root

    def close(self) -> None:
        self._active = False


class RepositorySource:
    """No configuration loading, analysis orchestration or target execution."""

    def __init__(self, git: GitExecution | None = None) -> None:
        self._git = git

    @property
    def git(self) -> GitExecution:
        if self._git is None:
            self._git = GitRunner()
        return self._git

    def _metadata(self, directory: Path) -> tuple[Path, str | None]:
        output = self.git.run(
            ("-c", "protocol.https.allow=never", "rev-parse", "--show-toplevel"), directory, 10
        )
        if output.returncode:
            raise InvalidSource("Expected an accessible non-bare Git working tree")
        try:
            root = Path(output.stdout.decode("utf-8").rstrip("\r\n")).resolve(strict=True)
        except (UnicodeError, OSError, ValueError):
            raise GitFailed("Git returned invalid repository root metadata") from None
        if not root.is_dir() or not directory.is_relative_to(root):
            raise GitFailed("Git returned an inconsistent repository root")
        head = self.git.run(
            (
                "-c",
                "protocol.https.allow=never",
                "rev-parse",
                "--verify",
                "--quiet",
                "HEAD^{commit}",
            ),
            root,
            10,
        )
        if head.returncode == 1:
            return root, None
        if head.returncode:
            raise GitFailed("Git could not determine commit metadata")
        sha = head.stdout.decode("ascii", errors="replace").strip()
        if re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", sha) is None:
            raise GitFailed("Git returned invalid commit metadata")
        return root, sha

    @contextmanager
    def local(self, path: Path) -> Iterator[RepositoryLease]:
        try:
            directory = path.resolve(strict=True)
            if not directory.is_dir():
                raise InvalidSource("Local source must be a directory")
            for candidate in (directory, *directory.parents):
                marker = candidate / ".git"
                if marker.is_symlink() or marker.is_junction():
                    raise InvalidSource("Symlinked Git metadata is not supported")
                if marker.exists():
                    break
            root, sha = self._metadata(directory)
        except (OSError, RuntimeError):
            raise InvalidSource("Local source is missing or inaccessible") from None
        lease = RepositoryLease(root, Repository(root.name or "repository"), SourceKind.LOCAL, sha)
        try:
            yield lease
        finally:
            lease.close()

    @contextmanager
    def github(self, url: str) -> Iterator[RepositoryLease]:
        canonical = canonical_github_url(url)
        with _temporary_workspace() as workspace:
            root = workspace / "repository"
            result = self.git.run(
                (
                    "clone",
                    "--quiet",
                    "--depth=1",
                    "--single-branch",
                    "--no-tags",
                    "--",
                    canonical,
                    str(root),
                ),
                workspace,
                120,
            )
            if result.returncode:
                raise GitFailed("Public GitHub clone failed; check availability and access")
            resolved, sha = self._metadata(root)
            if resolved != root.resolve():
                raise GitFailed("Git returned an unexpected clone root")
            lease = RepositoryLease(
                resolved,
                Repository(canonical.split("/")[-1].removesuffix(".git")),
                SourceKind.GITHUB,
                sha,
                canonical,
            )
            try:
                yield lease
            finally:
                lease.close()
