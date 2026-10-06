"""Pinned optional Bandit over owned detached sources, never a target checkout."""

import json
import os
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from subprocess import DEVNULL, Popen, TimeoutExpired
from sys import base_prefix as PYTHON_BASE_PREFIX
from sys import executable as PYTHON_EXECUTABLE
from sys import platform as RUNTIME_PLATFORM
from tempfile import TemporaryDirectory, TemporaryFile, gettempdir
from time import monotonic

from repolens.domain.models import Severity
from repolens.domain.python_source import PythonSourceSnapshot
from repolens.domain.security import (
    BanditObservation,
    SecurityFailure,
    SecurityToolFailed,
    SecurityToolUnavailable,
)

SUPPORTED_BANDIT_VERSION = "1.9.4"
STDOUT_LIMIT = 2 * 1024 * 1024
STDERR_LIMIT = 64 * 1024
TOOL_TIMEOUT = 30


def _environment(home: Path) -> dict[str, str]:
    essentials = {"SYSTEMROOT", "WINDIR"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in essentials}
    for name in (
        "HOME",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "TMP",
        "TEMP",
        "TMPDIR",
    ):
        environment[name] = str(home)
    environment["LC_ALL"] = "C"
    if RUNTIME_PLATFORM == "linux":
        # Hosted/relocatable Python may need its own libpython search path.
        # Reconstruct from the trusted runtime; never inherit loader overrides.
        environment["LD_LIBRARY_PATH"] = str(
            (Path(PYTHON_BASE_PREFIX) / "lib").resolve(strict=True)
        )
    return environment


def _utf8_source(text: str) -> bytes:
    # Decoded snapshots may retain an original non-UTF-8 coding cookie. Change
    # only that cookie on the first two comment lines; keep source line numbers.
    lines = text.splitlines(keepends=True)
    for index in range(min(2, len(lines))):
        if not lines[index].lstrip().startswith("#"):
            if lines[index].strip():
                break  # A second-line string literal is not an encoding cookie.
            continue
        changed = re.sub(r"coding([=:]\s*)[-\w.]+", r"coding\1utf-8", lines[index], count=1)
        if changed != lines[index]:
            lines[index] = changed
            break
    return "".join(lines).encode("utf-8")


def _capture(command: list[str], cwd: Path, home: Path) -> tuple[int, bytes]:
    # File-backed streams bound RAM. Polling can overshoot disk caps between
    # checks; this is a trusted-tool boundary, not an OS resource sandbox.
    with (
        TemporaryFile(dir=home) as stdout,
        TemporaryFile(dir=home) as stderr,
        # Absolute trusted Python, fixed module/flags, no target execution.
        Popen(  # nosec B603
            command,
            cwd=cwd,
            env=_environment(home),
            stdin=DEVNULL,
            stdout=stdout,
            stderr=stderr,
            shell=False,
        ) as process,
    ):
        deadline = monotonic() + TOOL_TIMEOUT
        try:
            while True:
                if (
                    os.fstat(stdout.fileno()).st_size > STDOUT_LIMIT
                    or os.fstat(stderr.fileno()).st_size > STDERR_LIMIT
                ):
                    raise SecurityToolFailed(
                        "Security tool output exceeded its limit", SecurityFailure.OUTPUT_LIMIT
                    )
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise SecurityToolFailed(
                        "Security tool exceeded its deadline", SecurityFailure.TIMED_OUT
                    )
                try:
                    process.wait(timeout=min(remaining, 0.01))
                    break
                except TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        if (
            os.fstat(stdout.fileno()).st_size > STDOUT_LIMIT
            or os.fstat(stderr.fileno()).st_size > STDERR_LIMIT
        ):
            raise SecurityToolFailed(
                "Security tool output exceeded its limit", SecurityFailure.OUTPUT_LIMIT
            )
        stdout.seek(0)
        if os.fstat(stderr.fileno()).st_size:
            raise SecurityToolFailed(
                "Security tool emitted diagnostics; completeness is unavailable",
                SecurityFailure.DIAGNOSTICS,
            )
        return process.returncode, stdout.read(STDOUT_LIMIT)


def _normalize(
    returncode: int, raw: bytes, snapshot: PythonSourceSnapshot
) -> tuple[BanditObservation, ...]:
    if len(raw) > STDOUT_LIMIT:
        raise SecurityToolFailed(
            "Security tool output exceeded its limit", SecurityFailure.OUTPUT_LIMIT
        )
    if returncode not in {0, 1}:
        raise SecurityToolFailed("Security tool did not complete successfully")
    try:
        document = json.loads(raw)
        # Only exact spellings generated by native os.path.join('.', relative)
        # are accepted. Absolute/traversing/unknown vendor paths never map.
        paths = {
            os.path.join(".", *source.path.split("/")): source
            for source in snapshot.files
            if source.path.endswith(".py")
        }
        if (
            not isinstance(document, dict)
            or document.get("errors") != []
            or not isinstance(document.get("results"), list)
            or not isinstance(document.get("metrics"), dict)
        ):
            raise ValueError("Invalid scanner document")
        if not set(paths).issubset(document["metrics"]):
            raise ValueError("Scanner omitted selected source files")
        rows = document["results"]
        if bool(rows) != bool(returncode) or len(rows) > 10_000:
            raise ValueError("Inconsistent scanner exit status")
        observations: list[BanditObservation] = []
        seen: set[tuple[str, str, int, int]] = set()
        severities = {"LOW": Severity.LOW, "MEDIUM": Severity.MEDIUM, "HIGH": Severity.HIGH}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid scanner issue")
            source = paths[row["filename"]]
            severity = severities[row["issue_severity"]]
            if row["issue_confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
                raise ValueError("Unknown scanner confidence")
            issue = BanditObservation(
                row["test_id"], severity, source.path, row["line_number"], row["col_offset"]
            )
            lines = source.text.splitlines()
            if issue.line > len(lines) or issue.column > len(lines[issue.line - 1].encode("utf-8")):
                raise ValueError("Scanner location is outside source")
            key = (issue.rule, issue.path, issue.line, issue.column)
            if key in seen:
                raise ValueError("Duplicate scanner issue")
            seen.add(key)
            observations.append(issue)
        return tuple(
            sorted(
                observations, key=lambda issue: (issue.rule, issue.path, issue.line, issue.column)
            )
        )
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise SecurityToolFailed(
            "Security tool output could not be validated", SecurityFailure.INVALID_OUTPUT
        ) from None


class BanditRunner:
    def __init__(self, *, origin_root: Path | None) -> None:
        # Infrastructure composition supplies an acquired canonical root, or
        # explicitly None for synthetic in-memory data with no target tree.
        # This metadata is only an exclusion guard, never an input to Bandit.
        try:
            self._origin_root = (
                origin_root.resolve(strict=True) if origin_root is not None else None
            )
        except (OSError, RuntimeError):
            raise SecurityToolFailed("Security source origin could not be validated") from None

    def scan(self, snapshot: PythonSourceSnapshot) -> tuple[BanditObservation, ...]:
        try:
            if version("bandit") != SUPPORTED_BANDIT_VERSION:
                raise SecurityToolUnavailable("Supported Bandit version is unavailable")
        except PackageNotFoundError:
            raise SecurityToolUnavailable("Supported Bandit version is unavailable") from None
        except OSError:
            raise SecurityToolFailed("Security tool metadata could not be inspected") from None
        try:
            storage = Path(gettempdir()).resolve(strict=True)
            if self._origin_root is not None and storage.is_relative_to(self._origin_root):
                raise SecurityToolFailed("Security temporary storage overlaps the source origin")
            launch = Path(PYTHON_EXECUTABLE)
            if not launch.is_absolute() or not launch.resolve(strict=True).is_file():
                raise SecurityToolUnavailable("Trusted Python executable is unavailable")
            # Resolve the parent but retain the venv executable entry: resolving
            # a POSIX venv's python symlink itself would lose the venv identity.
            executable = str(launch.parent.resolve(strict=True) / launch.name)
            with TemporaryDirectory(prefix="repolens-bandit-", dir=storage) as temporary:
                workspace = Path(temporary)
                home = workspace / "home"
                home.mkdir()
                sources = workspace / "sources"
                sources.mkdir()
                config = workspace / "controls.toml"
                config.write_text("[tool.bandit]\n", encoding="utf-8")
                ini = workspace / "controls.ini"
                ini.write_text("[bandit]\n", encoding="utf-8")
                for source in snapshot.files:
                    if source.path.endswith(".py"):
                        path = sources.joinpath(*source.path.split("/"))
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open("xb") as stream:
                            stream.write(_utf8_source(source.text))
                command = [
                    executable,
                    "-I",
                    "-B",
                    "-X",
                    "utf8",
                    "-m",
                    "bandit",
                    "-c",
                    str(config),
                    "--ini",
                    str(ini),
                    "-r",
                    ".",
                    "-x",
                    "",
                    "--ignore-nosec",
                    "--severity-level",
                    "all",
                    "--confidence-level",
                    "all",
                    "-f",
                    "json",
                    "-q",
                    "-n",
                    "0",
                ]
                status, raw = _capture(command, sources, home)
                return _normalize(status, raw, snapshot)
        except FileNotFoundError:
            raise SecurityToolFailed(
                "Security tool resource or executable became unavailable"
            ) from None
        except (OSError, ValueError, RuntimeError):
            raise SecurityToolFailed(
                "Security tool execution or workspace handling failed"
            ) from None
