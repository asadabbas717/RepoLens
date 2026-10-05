"""Exercise security construction and bounded subprocess lifecycle without network."""

import subprocess
from pathlib import Path
from typing import BinaryIO, cast
from unittest.mock import MagicMock

import pytest

from repolens.infrastructure.errors import GitFailed, GitTimedOut, GitUnavailable
from repolens.infrastructure.git import GitRunner, isolated_environment


def test_environment_drops_ambient_git_authentication_and_proxy_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_CONFIG_COUNT",
        "GIT_ASKPASS",
        "HTTPS_PROXY",
        "GIT_TRACE",
        "GIT_SSL_NO_VERIFY",
    ):
        monkeypatch.setenv(name, "secret")
    environment = isolated_environment("controlled-home")
    assert not any(value == "secret" for value in environment.values())
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["HOME"] == "controlled-home"


def test_git_unavailable_and_spawn_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with monkeypatch.context() as scope:
        scope.setattr("repolens.infrastructure.git.shutil.which", lambda name: None)
        with pytest.raises(GitUnavailable):
            GitRunner()
    runner = GitRunner()
    for error, expected in (
        (FileNotFoundError("secret"), GitUnavailable),
        (OSError("secret"), GitFailed),
    ):
        monkeypatch.setattr(
            "repolens.infrastructure.git.subprocess.Popen", MagicMock(side_effect=error)
        )
        with pytest.raises(expected) as failure:
            runner.run(("rev-parse", "--show-toplevel"), tmp_path, 10)
        assert "secret" not in str(failure.value)


def test_runner_builds_array_and_uses_empty_hooks_and_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.returncode = 0
    process.poll.return_value = 0
    spawn = MagicMock(return_value=process)
    monkeypatch.setattr("repolens.infrastructure.git.subprocess.Popen", spawn)
    assert GitRunner().run(("rev-parse", "--show-toplevel"), tmp_path, 10).returncode == 0
    command = spawn.call_args.args[0]
    assert Path(command[0]).is_absolute()
    assert command[-2:] == ["rev-parse", "--show-toplevel"]
    assert "shell" not in spawn.call_args.kwargs
    for option in (
        "credential.helper=",
        "core.fsmonitor=false",
        "protocol.allow=never",
        "protocol.https.allow=always",
        "http.followRedirects=false",
        "http.sslVerify=true",
        "submodule.recurse=false",
    ):
        assert option in command
    hooks = next(value.split("=", 1)[1] for value in command if value.startswith("core.hooksPath="))
    assert f"init.templateDir={hooks}" in command
    assert not Path(hooks).exists()


def test_timeout_kills_and_reaps_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.poll.return_value = None
    ticks = iter((0.0, 0.5, 2.0))
    monkeypatch.setattr("repolens.infrastructure.git.time.monotonic", lambda: next(ticks))
    process.wait.side_effect = [subprocess.TimeoutExpired("Git", 0.01), 0]
    monkeypatch.setattr(
        "repolens.infrastructure.git.subprocess.Popen", MagicMock(return_value=process)
    )
    with pytest.raises(GitTimedOut):
        GitRunner().run(("rev-parse", "--show-toplevel"), tmp_path, 1)
    process.kill.assert_called_once()
    assert process.wait.call_count == 2


@pytest.mark.parametrize("late", [False, True])
def test_output_limits_terminate_excess_and_never_retain_raw_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, late: bool
) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.returncode = 0
    process.poll.return_value = 0 if late else None

    def spawn(command: list[str], **options: object) -> MagicMock:
        stream = cast(BinaryIO, options["stderr"])

        def write_output() -> int:
            stream.write(b"secret" * 12_000)
            stream.flush()
            return 0

        if late:
            process.wait.side_effect = lambda timeout=None: write_output()
        else:
            write_output()
        return process

    monkeypatch.setattr("repolens.infrastructure.git.subprocess.Popen", spawn)
    with pytest.raises(GitFailed, match="capture limit") as failure:
        GitRunner().run(("rev-parse", "--show-toplevel"), tmp_path, 10)
    assert "secret" not in str(failure.value)
    assert process.kill.call_count == (0 if late else 1)


@pytest.mark.parametrize("timeout", [0, -1, True])
def test_timeout_must_be_positive_integer(tmp_path: Path, timeout: int) -> None:
    with pytest.raises(ValueError):
        GitRunner().run(("rev-parse", "--show-toplevel"), tmp_path, timeout)
