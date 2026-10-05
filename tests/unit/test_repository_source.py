"""URL and acquisition lifetime tests never require live GitHub."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.infrastructure.errors import AcquisitionError, GitFailed, GitTimedOut, InvalidSource
from repolens.infrastructure.git import GitOutput, GitRunner
from repolens.infrastructure.repository_source import (
    RepositorySource,
    SourceKind,
    canonical_github_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo",
        "https://github.com/owner/repo.git",
        "https://github.com/owner/repo/",
        "https://github.com/owner/repo.git/",
    ],
)
def test_repository_root_variants_normalize(url: str) -> None:
    assert canonical_github_url(url) == "https://github.com/owner/repo.git"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/o/r",
        "ssh://github.com/o/r",
        "git@github.com:o/r",
        "file:///tmp/r",
        "https://evil.com/o/r",
        "https://github.com.evil.com/o/r",
        "https://user:secret@github.com/o/r",
        "https://github.com:443/o/r",
        "https://github.com/o/r/issues",
        "https://github.com/o/r/tree/main",
        "https://github.com/o/r?secret=foo",
        "https://github.com/o/r#fragment",
        "https://github.com/o/r?",
        "https://github.com/o/r#",
        "https://github.com/o/r//",
        "https://github.com/-owner/r",
        "https://github.com/owner-/r",
        "https://github.com/o--x/r",
        "https://github.com/o/..",
        "https://github.com/o/.git",
        "https://github.com/o/-r",
        "https://github.com/o/%2e%2e",
        "https://github.com/o/r%2fother",
        "https://github.com/o/ü",
        "https://github.com/o/r\n",
        " https://github.com/o/r",
        "https://github.com/o/\\r",
        "https://[invalid/o/r",
        "https://github.com/o",
        "https://github.com//r",
    ],
)
def test_rejects_url_tricks_without_echoing_secret_input(url: str) -> None:
    with pytest.raises(InvalidSource) as failure:
        canonical_github_url(url)
    assert url not in str(failure.value)
    assert "secret" not in str(failure.value)


class SimulatedClone:
    """Copy a controlled fixture instead of making a network request."""

    def __init__(self, fixture: Path, failure: Exception | None = None, exitcode: int = 0) -> None:
        self.fixture = fixture
        self.failure = failure
        self.exitcode = exitcode
        self.workspace: Path | None = None
        self.arguments: tuple[str, ...] = ()

    def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
        if arguments[0] == "clone":
            self.workspace = cwd
            self.arguments = arguments
            assert timeout == 120
            if self.failure is not None:
                raise self.failure
            if self.exitcode == 0:
                shutil.copytree(self.fixture, arguments[-1])
            return GitOutput(self.exitcode, b"not exposed")
        return GitRunner().run(arguments, cwd, timeout)


def init_fixture(path: Path) -> None:
    path.mkdir()
    assert GitRunner().run(("init", "--quiet"), path, 10).returncode == 0


def test_remote_workspace_is_owned_and_cleaned_on_success_and_consumer_exception(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture"
    init_fixture(fixture)
    fake = SimulatedClone(fixture)
    for consumer_failure in (False, True):
        try:
            with RepositorySource(fake).github("https://github.com/owner/repo/") as lease:
                assert lease.root.is_dir()
                assert lease.kind == SourceKind.GITHUB
                assert lease.canonical_url == "https://github.com/owner/repo.git"
                assert lease.identity.name == "repo"
                if consumer_failure:
                    raise LookupError("consumer failure")
        except LookupError:
            assert consumer_failure
        assert fake.workspace is not None and not fake.workspace.exists()
        with pytest.raises(AcquisitionError, match="closed"):
            _ = lease.root
    assert fake.arguments[:5] == ("clone", "--quiet", "--depth=1", "--single-branch", "--no-tags")
    assert fake.arguments[5:7] == ("--", "https://github.com/owner/repo.git")


@pytest.mark.parametrize("error", [GitFailed("failure"), GitTimedOut("timeout"), None])
def test_clone_failure_and_timeout_clean_workspace(tmp_path: Path, error: Exception | None) -> None:
    fake = SimulatedClone(tmp_path, error, exitcode=128)
    with pytest.raises(GitFailed), RepositorySource(fake).github("https://github.com/owner/repo"):
        pytest.fail("failed clone must not yield a lease")
    assert fake.workspace is not None and not fake.workspace.exists()


class MetadataGit:
    def __init__(self, outputs: tuple[GitOutput, ...]) -> None:
        self.outputs = iter(outputs)

    def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
        assert arguments[:2] == ("-c", "protocol.https.allow=never")
        assert timeout == 10
        return next(self.outputs)


@pytest.mark.parametrize("root_output", [b"\xff", b"/nonexistent-repolens-fixture", b"\x00"])
def test_invalid_root_metadata_is_sanitized(tmp_path: Path, root_output: bytes) -> None:
    with (
        pytest.raises(GitFailed),
        RepositorySource(MetadataGit((GitOutput(0, root_output),))).local(tmp_path),
    ):
        pytest.fail("invalid root metadata yielded")


def test_inconsistent_root_and_invalid_commit_metadata_are_rejected(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    root_bytes = str(tmp_path).encode("utf-8")
    with (
        pytest.raises(GitFailed, match="inconsistent"),
        RepositorySource(MetadataGit((GitOutput(0, str(child).encode("utf-8")),))).local(tmp_path),
    ):
        pytest.fail("unrelated root yielded")
    for output in (GitOutput(128, b"secret"), GitOutput(0, b"not-a-sha")):
        with (
            pytest.raises(GitFailed),
            RepositorySource(MetadataGit((GitOutput(0, root_bytes), output))).local(tmp_path),
        ):
            pytest.fail("invalid commit metadata yielded")


def test_workspace_allocation_and_cleanup_failures_are_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "repolens.infrastructure.repository_source.TemporaryDirectory",
        MagicMock(side_effect=OSError("secret")),
    )
    with (
        pytest.raises(AcquisitionError, match="created"),
        RepositorySource().github("https://github.com/o/r"),
    ):
        pytest.fail("failed workspace yielded")
    fixture = tmp_path / "fixture"
    init_fixture(fixture)
    directory = tmp_path / "workspace"
    directory.mkdir()
    workspace = MagicMock(name="workspace")
    workspace.name = str(directory)
    workspace.cleanup.side_effect = OSError("secret")
    monkeypatch.setattr(
        "repolens.infrastructure.repository_source.TemporaryDirectory",
        MagicMock(return_value=workspace),
    )
    with (
        pytest.raises(AcquisitionError, match="cleanup"),
        RepositorySource(SimulatedClone(fixture)).github("https://github.com/o/r") as lease,
    ):
        assert lease.root.is_dir()
    workspace.cleanup.assert_called_once()


def test_consumer_oserror_is_preserved_and_workspace_still_cleaned(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    init_fixture(fixture)
    fake = SimulatedClone(fixture)
    with (
        pytest.raises(OSError, match="consumer failure"),
        RepositorySource(fake).github("https://github.com/o/r"),
    ):
        raise OSError("consumer failure")
    assert fake.workspace is not None and not fake.workspace.exists()


def test_remote_metadata_cannot_expand_inventory_beyond_clone_root(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    init_fixture(fixture)

    class EscapingMetadata(SimulatedClone):
        def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
            if arguments[0] == "clone":
                return super().run(arguments, cwd, timeout)
            if "--show-toplevel" in arguments:
                return GitOutput(0, str(cwd.parent).encode("utf-8"))
            return GitOutput(1, b"")

    fake = EscapingMetadata(fixture)
    with (
        pytest.raises(GitFailed, match="unexpected clone root"),
        RepositorySource(fake).github("https://github.com/o/r"),
    ):
        pytest.fail("escaping clone root yielded")
    assert fake.workspace is not None and not fake.workspace.exists()


@pytest.mark.parametrize("location", ["root", "subdirectory", "unrelated"])
def test_metadata_canonicalizes_short_path_alias_before_containment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    # Model Windows 8.3 resolution without depending on a volume's 8.3 policy
    # or runner username. Only the alias resolution is replaced; containment
    # uses real pathlib paths and real directories on every platform.
    root = (tmp_path / "long repository name").resolve()
    root.mkdir()
    directory = root if location == "root" else root / "child"
    directory.mkdir(exist_ok=True)
    alias = tmp_path / "LONGRE~1"
    returned = root
    if location == "unrelated":
        returned = tmp_path / "unrelated"
        returned.mkdir()
    original_resolve = type(alias).resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path == alias:
            assert strict
            return directory
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(type(alias), "resolve", resolve)
    git = MetadataGit((GitOutput(0, str(returned).encode("utf-8")), GitOutput(1, b"")))
    if location == "unrelated":
        with pytest.raises(GitFailed, match="inconsistent repository root"):
            RepositorySource(git)._metadata(alias)
    else:
        assert RepositorySource(git)._metadata(alias) == (root, None)


@pytest.mark.parametrize("inaccessible", [False, True])
def test_metadata_input_resolution_failure_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inaccessible: bool
) -> None:
    directory = tmp_path / "missing"
    if inaccessible:
        monkeypatch.setattr(type(directory), "resolve", MagicMock(side_effect=OSError("secret")))
    with pytest.raises(InvalidSource, match="missing or inaccessible") as failure:
        RepositorySource(MetadataGit(()))._metadata(directory)
    assert "secret" not in str(failure.value)
    assert failure.value.__suppress_context__


def test_disappearing_clone_destination_is_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = tmp_path / "fixture"
    init_fixture(fixture)
    fake = SimulatedClone(fixture)

    def metadata(source: RepositorySource, directory: Path) -> tuple[Path, None]:
        canonical = directory.resolve(strict=True)
        shutil.rmtree(directory)
        return canonical, None

    monkeypatch.setattr(RepositorySource, "_metadata", metadata)
    with (
        pytest.raises(GitFailed, match="destination is missing or inaccessible"),
        RepositorySource(fake).github("https://github.com/o/r"),
    ):
        pytest.fail("missing destination yielded")
    assert fake.workspace is not None and not fake.workspace.exists()
