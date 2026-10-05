"""Real Git operations only on controlled, test-owned temporary repositories."""

import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from repolens.infrastructure.errors import AcquisitionError, InvalidSource, TraversalLimitExceeded
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.repository_source import RepositorySource, SourceKind
from repolens.infrastructure.traversal import TraversalLimits, repository_files


@pytest.fixture
def local_repo(tmp_path: Path) -> Path:
    root = tmp_path / "fixture"
    root.mkdir()
    runner = GitRunner()
    assert runner.run(("init", "--quiet"), root, 10).returncode == 0
    (root / "README.md").write_text("controlled fixture\n", encoding="utf-8")
    assert runner.run(("add", "README.md"), root, 10).returncode == 0
    assert (
        runner.run(
            (
                "-c",
                "user.name=RepoLens Test",
                "-c",
                "user.email=tests@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ),
            root,
            10,
        ).returncode
        == 0
    )
    return root


def test_local_subdirectory_resolves_root_and_preserves_working_changes(local_repo: Path) -> None:
    child = local_repo / "src"
    child.mkdir()
    (local_repo / "README.md").write_text("modified", encoding="utf-8")
    (child / "untracked.py").write_text("not imported", encoding="utf-8")
    before = (local_repo / ".git" / "index").read_bytes()
    with RepositorySource().local(child / ".." / "src") as lease:
        assert lease.root == local_repo.resolve()
        assert lease.kind == SourceKind.LOCAL
        assert lease.canonical_url is None
        assert lease.commit_sha is not None and len(lease.commit_sha) == 40
        assert set(repository_files(lease)) == {Path("README.md"), Path("src/untracked.py")}
    assert (local_repo / ".git" / "index").read_bytes() == before
    assert (local_repo / "README.md").read_text(encoding="utf-8") == "modified"
    assert local_repo.exists()
    with pytest.raises(AcquisitionError, match="closed"):
        _ = lease.root


def test_missing_file_non_git_bare_and_malformed_sources_are_rejected(tmp_path: Path) -> None:
    file = tmp_path / "file"
    file.write_text("not a directory", encoding="utf-8")
    bare = tmp_path / "bare"
    assert GitRunner().run(("init", "--bare", "--quiet", str(bare)), tmp_path, 10).returncode == 0
    malformed = tmp_path / "malformed"
    (malformed / ".git").mkdir(parents=True)
    for path in (tmp_path / "missing", file, tmp_path, bare, malformed):
        with pytest.raises(InvalidSource), RepositorySource().local(path):
            pytest.fail("invalid local source yielded")


def test_unborn_worktree_is_supported_without_claiming_commit(tmp_path: Path) -> None:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    with RepositorySource().local(tmp_path) as lease:
        assert lease.commit_sha is None


def test_linked_git_worktree_is_supported(local_repo: Path, tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    assert (
        GitRunner()
        .run(("worktree", "add", "--detach", "--quiet", str(worktree)), local_repo, 10)
        .returncode
        == 0
    )
    with RepositorySource().local(worktree) as lease:
        assert lease.root == worktree.resolve()
        assert lease.commit_sha is not None


def test_default_exclusions_size_and_virtual_environments(local_repo: Path) -> None:
    for directory in (
        ".venv",
        ".venv-bootstrap",
        "node_modules",
        "build",
        "dist",
        "__pycache__",
        ".pytest_cache",
    ):
        folder = local_repo / directory
        folder.mkdir()
        (folder / "excluded").touch()
    custom = local_repo / "custom-env"
    custom.mkdir()
    (custom / "pyvenv.cfg").touch()
    (local_repo / "oversized").write_bytes(b"x" * 100)
    (local_repo / ".gitignore").write_text("untracked.txt\n", encoding="utf-8")
    (local_repo / "untracked.txt").touch()
    with RepositorySource().local(local_repo) as lease:
        paths = set(repository_files(lease, TraversalLimits(max_file_bytes=50)))
        assert paths == {Path("README.md"), Path(".gitignore"), Path("untracked.txt")}


def test_traversal_reports_entry_and_depth_limits(local_repo: Path) -> None:
    (local_repo / "a" / "b").mkdir(parents=True)
    with RepositorySource().local(local_repo) as lease:
        with pytest.raises(TraversalLimitExceeded, match="entry"):
            tuple(repository_files(lease, TraversalLimits(max_entries=1)))
        with pytest.raises(TraversalLimitExceeded, match="depth"):
            tuple(repository_files(lease, TraversalLimits(max_depth=1)))


def test_symlink_files_and_directories_are_not_followed(local_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").touch()
    try:
        (local_repo / "escape").symlink_to(outside, target_is_directory=True)
        (local_repo / "link").symlink_to(outside / "secret")
    except OSError:
        pytest.skip("OS does not permit test-owned symlinks")
    with RepositorySource().local(local_repo) as lease:
        assert tuple(repository_files(lease)) == (Path("README.md"),)


def test_inventory_cannot_continue_after_lease_close(local_repo: Path) -> None:
    (local_repo / "another").touch()
    with RepositorySource().local(local_repo) as lease:
        files = repository_files(lease)
        next(files)
    with pytest.raises(AcquisitionError, match="closed"):
        next(files)


@pytest.mark.parametrize("value", [0, -1, True])
def test_traversal_limits_require_positive_integers(value: int) -> None:
    with pytest.raises(ValueError):
        TraversalLimits(max_entries=value)


@pytest.mark.parametrize("reparse", [False, True])
def test_link_metadata_excludes_entries_without_needing_os_symlink_privileges(
    local_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    reparse: bool,
) -> None:
    escape = local_repo / "escape"
    escape.mkdir()
    (escape / "unreachable").touch()
    original = Path.lstat

    def metadata(path: Path) -> os.stat_result:
        if path == escape:
            return cast(
                os.stat_result,
                SimpleNamespace(
                    st_mode=stat.S_IFDIR if reparse else stat.S_IFLNK,
                    st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if reparse else 0,
                ),
            )
        return original(path)

    with RepositorySource().local(local_repo) as lease:
        monkeypatch.setattr(Path, "lstat", metadata)
        assert tuple(repository_files(lease)) == (Path("README.md"),)


def test_symlinked_git_metadata_is_rejected_without_invoking_git(
    local_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda path: path == local_repo / ".git" or original(path)
    )
    with pytest.raises(InvalidSource, match="metadata"), RepositorySource().local(local_repo):
        pytest.fail("symlinked metadata yielded")


def test_inventory_access_errors_are_sanitized(
    local_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with RepositorySource().local(local_repo) as lease:

        def inaccessible(path: Path) -> os.stat_result:
            raise PermissionError("secret")

        monkeypatch.setattr(Path, "lstat", inaccessible)
        with pytest.raises(AcquisitionError, match="inaccessible"):
            tuple(repository_files(lease))


def test_inventory_rejects_directory_replaced_by_link(
    local_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with RepositorySource().local(local_repo) as lease:
        monkeypatch.setattr("repolens.infrastructure.traversal._link_or_reparse", lambda path: True)
        with pytest.raises(AcquisitionError, match="changed"):
            tuple(repository_files(lease))


def test_spaces_and_unicode_paths_resolve_without_shell_quoting(tmp_path: Path) -> None:
    root = tmp_path / "project with spaces ü"
    root.mkdir()
    assert GitRunner().run(("init", "--quiet"), root, 10).returncode == 0
    with RepositorySource().local(root) as lease:
        assert lease.root == root.resolve()
