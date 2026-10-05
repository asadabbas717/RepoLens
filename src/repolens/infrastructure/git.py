"""One Git execution boundary with isolated configuration and bounded capture."""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Protocol

from repolens.infrastructure.errors import GitFailed, GitTimedOut, GitUnavailable


@dataclass(frozen=True, slots=True)
class GitOutput:
    returncode: int
    stdout: bytes


class GitExecution(Protocol):
    """Narrow seam for deterministic, network-free acquisition tests."""

    def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput: ...


def isolated_environment(home: str) -> dict[str, str]:
    """Allow OS essentials, not ambient Git/askpass/proxy/credential overrides."""
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "LC_ALL": "C",
            "HOME": home,
            "USERPROFILE": home,
            "XDG_CONFIG_HOME": home,
        }
    )
    return environment


class GitRunner:
    """Run only application-built Git argument arrays; never target scripts."""

    OUTPUT_LIMIT = 65_536

    def __init__(self) -> None:
        executable = shutil.which("git")
        if executable is None:
            raise GitUnavailable("Git is not installed or not available on PATH")
        self._executable = str(Path(executable).resolve())

    def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
        if type(timeout) is not int or timeout < 1:
            raise ValueError("Git timeout must be a positive integer")
        try:
            with TemporaryDirectory(prefix="repolens-git-") as controls:
                command = [
                    self._executable,
                    "-c",
                    f"core.hooksPath={controls}",
                    "-c",
                    f"init.templateDir={controls}",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "credential.helper=",
                    "-c",
                    "protocol.allow=never",
                    "-c",
                    "protocol.https.allow=always",
                    "-c",
                    "http.followRedirects=false",
                    "-c",
                    "http.sslVerify=true",
                    "-c",
                    "submodule.recurse=false",
                    "-c",
                    "core.protectNTFS=true",
                    "-c",
                    "core.protectHFS=true",
                    *arguments,
                ]
                try:
                    return self._capture(command, cwd, timeout, controls)
                except FileNotFoundError:
                    raise GitUnavailable("Git executable could not be started") from None
                except OSError:
                    raise GitFailed("Git execution or capture failed") from None
        except OSError:
            raise GitFailed("Git temporary controls could not be created or cleaned up") from None

    def _capture(self, command: list[str], cwd: Path, timeout: int, home: str) -> GitOutput:
        # File-backed capture prevents arbitrary subprocess output consuming RAM.
        # Absolute trusted Git binary; commands are built by our source layer.
        with (
            TemporaryFile() as stdout,
            TemporaryFile() as stderr,
            subprocess.Popen(  # nosec B603
                command,
                cwd=cwd,
                env=isolated_environment(home),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
            ) as process,
        ):
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if any(
                        os.fstat(stream.fileno()).st_size > self.OUTPUT_LIMIT
                        for stream in (stdout, stderr)
                    ):
                        raise GitFailed("Git output exceeded the capture limit")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise GitTimedOut("Git operation exceeded its deadline")
                    try:
                        process.wait(timeout=min(remaining, 0.01))
                        break
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            if any(
                os.fstat(stream.fileno()).st_size > self.OUTPUT_LIMIT for stream in (stdout, stderr)
            ):
                raise GitFailed("Git output exceeded the capture limit")
            stdout.seek(0)
            return GitOutput(process.returncode, stdout.read(self.OUTPUT_LIMIT))
