"""Vendor schema, detached analyzer states and process/resource regression tests."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.python_security import PythonSecurityAnalyzer
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    FileInventory,
    Repository,
    Severity,
)
from repolens.domain.python_source import PythonSourceFile, PythonSourceSnapshot
from repolens.domain.security import (
    BanditObservation,
    SecurityFailure,
    SecurityToolFailed,
    SecurityToolUnavailable,
)
from repolens.infrastructure import bandit as boundary


def snapshot() -> PythonSourceSnapshot:
    return PythonSourceSnapshot((PythonSourceFile("test_api.py", "password='source-secret'\n"),))


def document() -> dict[str, object]:
    return {"errors": [], "metrics": {os.path.join(".", "test_api.py"): {}}, "results": []}


def row() -> dict[str, object]:
    return {
        "filename": os.path.join(".", "test_api.py"),
        "issue_severity": "LOW",
        "issue_confidence": "HIGH",
        "test_id": "B105",
        "line_number": 1,
        "col_offset": 9,
        "code": "source-secret",
        "issue_text": "source-secret",
    }


def normalize(data: dict[str, object], code: int = 0) -> tuple[BanditObservation, ...]:
    return boundary._normalize(code, json.dumps(data).encode(), snapshot())


def test_clean_and_findings_exit_contract() -> None:
    assert normalize(document()) == ()
    data = document()
    data["results"] = [row()]
    (issue,) = normalize(data, 1)
    assert issue == BanditObservation("B105", Severity.LOW, "test_api.py", 1, 9)
    assert "source-secret" not in repr(issue)


@pytest.mark.parametrize(
    "field,value",
    [
        ("filename", "/tmp/test_api.py"),
        ("filename", "../test_api.py"),
        ("filename", "test_api.py"),
        ("filename", "C:/secret.py"),
        ("filename", os.path.join(".", "unknown.py")),
        ("filename", []),
        ("issue_severity", "CRITICAL"),
        ("issue_severity", "low"),
        ("issue_confidence", "UNKNOWN"),
        ("test_id", "B105-secret"),
        ("line_number", True),
        ("line_number", 0),
        ("line_number", 2),
        ("col_offset", -1),
        ("col_offset", 999),
        ("col_offset", False),
    ],
)
def test_invalid_vendor_issue_is_rejected(field: str, value: object) -> None:
    issue = row()
    issue[field] = value
    data = document()
    data["results"] = [issue]
    with pytest.raises(SecurityToolFailed, match="validated") as error:
        normalize(data, 1)
    assert "source-secret" not in str(error.value)


@pytest.mark.parametrize("raw", [b"secret", b"[]", b"null", b"{}", b"{", b"\xff"])
def test_malformed_document(raw: bytes) -> None:
    with pytest.raises(SecurityToolFailed):
        boundary._normalize(0, raw, snapshot())


@pytest.mark.parametrize(
    "field,value",
    [
        ("errors", [{"reason": "secret"}]),
        ("results", {}),
        ("metrics", {}),
        ("metrics", []),
        ("results", ["secret"]),
    ],
)
def test_wrong_schema(field: str, value: object) -> None:
    data = document()
    data[field] = value
    with pytest.raises(SecurityToolFailed):
        normalize(data)


@pytest.mark.parametrize("code,findings", [(0, True), (1, False), (2, False), (-1, False)])
def test_inconsistent_exit_status(code: int, findings: bool) -> None:
    data = document()
    data["results"] = [row()] if findings else []
    with pytest.raises(SecurityToolFailed):
        normalize(data, code)


def test_duplicate_findings_rejected_and_order_canonicalized() -> None:
    data = document()
    data["results"] = [row(), row()]
    with pytest.raises(SecurityToolFailed):
        normalize(data, 1)
    second = row()
    second["test_id"] = "B101"
    second["issue_severity"] = "HIGH"
    data["results"] = [row(), second]
    first = normalize(data, 1)
    data["results"] = [second, row()]
    assert normalize(data, 1) == first
    assert first[0].rule == "B101" and first[0].severity == Severity.HIGH


def test_oversized_normalizer_input() -> None:
    with pytest.raises(SecurityToolFailed):
        boundary._normalize(0, b"x" * (boundary.STDOUT_LIMIT + 1), snapshot())


@pytest.mark.parametrize(
    "field,value",
    [
        ("rule", "bad"),
        ("path", "../secret"),
        ("severity", Severity.CRITICAL),
        ("line", True),
        ("column", -1),
    ],
)
def test_observation_constructor_invariants(field: str, value: object) -> None:
    from collections.abc import Callable
    from typing import cast

    with pytest.raises(ValueError):
        cast(Callable[..., object], replace)(
            BanditObservation("B105", Severity.LOW, "test_api.py", 1, 9), **{field: value}
        )


def context() -> AnalysisContext:
    return AnalysisContext(Repository("fixture"), FileInventory(("test_api.py",)), snapshot())


def test_analyzer_findings_never_expose_vendor_source() -> None:
    scanner = MagicMock()
    scanner.scan.return_value = (BanditObservation("B105", Severity.LOW, "test_api.py", 1, 9),)
    analyzer = PythonSecurityAnalyzer(scanner)
    result = analyzer.analyze(context())
    assert result.state == AnalyzerState.COMPLETED
    assert result.findings[0].rule_id == "BANDIT-B105"
    assert result.findings[0].identifier == (
        "python-security:BANDIT-B105:"
        "b65e8add063b02f119b34283ee1fce137cc7d09169f60ca2f69bfb284ce68df9"
    )
    assert result == analyzer.analyze(context())
    assert "source-secret" not in repr(result)
    assert "source-secret" not in repr(context())


@pytest.mark.parametrize(
    "error,state",
    [
        (SecurityToolUnavailable("secret"), AnalyzerState.UNSUPPORTED),
        (SecurityToolFailed("secret"), AnalyzerState.FAILED),
    ],
)
def test_tool_errors_have_honest_states(error: Exception, state: AnalyzerState) -> None:
    scanner = MagicMock()
    scanner.scan.side_effect = error
    result = PythonSecurityAnalyzer(scanner).analyze(context())
    assert result.state == state and not result.findings and "secret" not in repr(result)


def test_missing_empty_and_stub_data() -> None:
    scanner = MagicMock()
    analyzer = PythonSecurityAnalyzer(scanner)
    assert analyzer.analyze(AnalysisContext(Repository("x"))).state == AnalyzerState.FAILED
    for sources in (
        PythonSourceSnapshot(()),
        PythonSourceSnapshot((PythonSourceFile("test.pyi", "pass"),)),
    ):
        ctx = AnalysisContext(
            Repository("x"), FileInventory(f.path for f in sources.files), sources
        )
        assert analyzer.analyze(ctx).state == AnalyzerState.NOT_APPLICABLE
    scanner.scan.assert_not_called()


@pytest.mark.parametrize("text", ["def secret(:", "x=t'secret'", "\x00"])
def test_unsupported_grammar_does_not_invoke_tool(text: str) -> None:
    scanner = MagicMock()
    ctx = AnalysisContext(
        Repository("x"),
        FileInventory(("test.py",)),
        PythonSourceSnapshot((PythonSourceFile("test.py", text),)),
    )
    assert PythonSecurityAnalyzer(scanner).analyze(ctx).state == AnalyzerState.UNSUPPORTED
    scanner.scan.assert_not_called()


@pytest.mark.parametrize("error", [MemoryError, RecursionError])
def test_parser_resource_failure(error: type[Exception], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "repolens.analyzers.python_security.parse_source", MagicMock(side_effect=error("secret"))
    )
    assert PythonSecurityAnalyzer(MagicMock()).analyze(context()).state == AnalyzerState.FAILED


def test_environment_filters_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GITHUB_TOKEN",
        "PIP_INDEX_URL",
        "HTTPS_PROXY",
        "PYTHONPATH",
        "PYTHONHOME",
        "PATH",
        "BANDIT_CONFIG",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
    ):
        monkeypatch.setenv(name, "secret-credential")
    environment = boundary._environment(tmp_path)
    assert "secret-credential" not in repr(environment)
    assert environment["HOME"] == str(tmp_path) and environment["TEMP"] == str(tmp_path)


@pytest.mark.parametrize("installed", [None, "0.0"])
def test_tool_unavailable(installed: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    if installed is None:
        mock = MagicMock(side_effect=PackageNotFoundError("secret"))
    else:
        mock = MagicMock(return_value=installed)
    monkeypatch.setattr(boundary, "version", mock)
    with pytest.raises(SecurityToolUnavailable) as error:
        boundary.BanditRunner(origin_root=None).scan(snapshot())
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("cleanup", [False, True])
def test_workspace_resource_failure_is_sanitized(
    cleanup: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Workspace:
        def __enter__(self) -> str:
            if not cleanup:
                raise OSError("secret-path")
            return str(tmp_path)

        def __exit__(self, *args: object) -> None:
            raise OSError("secret-path")

    factory = (
        MagicMock(side_effect=OSError("secret-path"))
        if not cleanup
        else MagicMock(return_value=Workspace())
    )
    monkeypatch.setattr(boundary, "TemporaryDirectory", factory)
    data = json.dumps(document()).encode()
    monkeypatch.setattr(boundary, "_capture", lambda *args: (0, data))
    with pytest.raises(SecurityToolFailed) as error:
        boundary.BanditRunner(origin_root=None).scan(snapshot())
    assert "secret-path" not in str(error.value)


def test_owned_materialization_command_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    roots: list[Path] = []

    def capture(command: list[str], cwd: Path, home: Path) -> tuple[int, bytes]:
        roots.append(cwd.parent)
        assert Path(command[0]).is_absolute()
        assert command[1:7] == ["-I", "-B", "-X", "utf8", "-m", "bandit"]
        assert command[0] == str(Path(sys.executable).parent.resolve() / Path(sys.executable).name)
        assert "--ignore-nosec" in command and "--ini" in command
        assert (cwd / "test_api.py").read_text() == "password='source-secret'\n"
        assert home.parent == cwd.parent
        assert not (cwd / "pyproject.toml").exists()
        assert not (cwd / "api.pyi").exists()
        return 0, json.dumps(document()).encode()

    monkeypatch.setattr(boundary, "_capture", capture)
    data = PythonSourceSnapshot((*snapshot().files, PythonSourceFile("api.pyi", "pass")))
    assert boundary.BanditRunner(origin_root=None).scan(data) == ()
    assert roots and all(not root.exists() for root in roots)


@pytest.mark.parametrize("cookie", ["latin-1", "ascii", "utf-8"])
def test_detached_encoding_cookie(cookie: str) -> None:
    raw = boundary._utf8_source(f"# coding: {cookie}\nx='é'\n")
    assert raw.decode("utf-8") == "# coding: utf-8\nx='é'\n"


def test_process_contract_uses_arrays_no_shell_and_reaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.returncode = 0
    process.poll.return_value = 0
    factory = MagicMock(return_value=process)
    monkeypatch.setattr(boundary, "Popen", factory)
    assert boundary._capture([sys.executable, "-I"], tmp_path, tmp_path) == (0, b"")
    kwargs = factory.call_args.kwargs
    assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["cwd"] == tmp_path and kwargs["env"] == boundary._environment(tmp_path)
    assert isinstance(factory.call_args.args[0], list)
    process.wait.assert_called()


@pytest.mark.parametrize(
    "script,reason",
    [
        ("import time; time.sleep(10)", "deadline"),
        ("import sys; sys.stdout.write('x'*10000)", "limit"),
        ("import sys; sys.stderr.write('x'*10000)", "limit"),
        ("import sys; sys.stderr.write('secret-diagnostic')", "diagnostics"),
    ],
)
def test_real_trusted_child_timeout_and_stream_caps(
    script: str, reason: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary, "TOOL_TIMEOUT", 1)
    monkeypatch.setattr(boundary, "STDOUT_LIMIT", 100)
    monkeypatch.setattr(boundary, "STDERR_LIMIT", 100)
    with pytest.raises(SecurityToolFailed, match=reason) as error:
        boundary._capture([sys.executable, "-I", "-c", script], tmp_path, tmp_path)
    assert "secret-diagnostic" not in str(error.value)


@pytest.mark.parametrize(
    "severity,expected",
    [("LOW", Severity.LOW), ("MEDIUM", Severity.MEDIUM), ("HIGH", Severity.HIGH)],
)
def test_explicit_severity_mapping(severity: str, expected: Severity) -> None:
    issue = row()
    issue["issue_severity"] = severity
    data = document()
    data["results"] = [issue]
    assert normalize(data, 1)[0].severity == expected


@pytest.mark.parametrize("cleanup", [False, True])
def test_capture_file_allocation_cleanup_sanitized(
    cleanup: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager
    from tempfile import TemporaryFile
    from typing import BinaryIO, cast

    @contextmanager
    def capture_file(*, dir: Path) -> Iterator[BinaryIO]:
        if not cleanup:
            raise OSError("secret-resource-path")
        with TemporaryFile(dir=dir) as stream:
            yield cast(BinaryIO, stream)
        raise OSError("secret-resource-path")

    monkeypatch.setattr(boundary, "TemporaryFile", capture_file)
    process = MagicMock()
    process.__enter__.return_value = process
    process.returncode = 0
    process.poll.return_value = 0
    monkeypatch.setattr(boundary, "Popen", MagicMock(return_value=process))
    with pytest.raises(SecurityToolFailed) as error:
        boundary.BanditRunner(origin_root=None).scan(snapshot())
    assert "secret-resource-path" not in str(error.value)


@pytest.mark.parametrize("target", ["version", "Popen"])
def test_metadata_and_start_os_failures_sanitized(
    target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary, target, MagicMock(side_effect=OSError("secret-os-path")))
    with pytest.raises(SecurityToolFailed) as error:
        boundary.BanditRunner(origin_root=None).scan(snapshot())
    assert "secret-os-path" not in str(error.value)


def test_missing_runtime_file_sanitized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(boundary, "PYTHON_EXECUTABLE", str(tmp_path / "missing-python"))
    with pytest.raises(SecurityToolFailed) as error:
        boundary.BanditRunner(origin_root=None).scan(snapshot())
    assert str(tmp_path) not in str(error.value)


def test_relative_runtime_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boundary, "PYTHON_EXECUTABLE", "python")
    with pytest.raises(SecurityToolUnavailable):
        boundary.BanditRunner(origin_root=None).scan(snapshot())


def test_timeout_always_kills_and_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.poll.return_value = None
    monkeypatch.setattr(boundary, "Popen", MagicMock(return_value=process))
    monkeypatch.setattr(boundary, "monotonic", MagicMock(side_effect=(0.0, 100.0)))
    with pytest.raises(SecurityToolFailed, match="deadline"):
        boundary._capture([sys.executable, "-I"], tmp_path, tmp_path)
    process.kill.assert_called_once()
    process.wait.assert_called_once_with()


def test_post_exit_size_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    process = MagicMock()
    process.__enter__.return_value = process
    process.poll.return_value = 0
    process.returncode = 0

    def start(*args: object, **kwargs: object) -> MagicMock:
        from typing import BinaryIO, cast

        output = cast(BinaryIO, kwargs["stdout"])

        def wait(**options: object) -> int:
            output.write(b"x" * 1000)
            output.flush()
            return 0

        process.wait.side_effect = wait
        return process

    monkeypatch.setattr(boundary, "Popen", start)
    monkeypatch.setattr(boundary, "STDOUT_LIMIT", 100)
    with pytest.raises(SecurityToolFailed, match="limit"):
        boundary._capture([sys.executable], tmp_path, tmp_path)


@pytest.mark.parametrize(
    "text,expected",
    [
        ('"""\n# coding: latin-1\n"""', '"""\n# coding: latin-1\n"""'),
        ("x=1\n# coding: latin-1", "x=1\n# coding: latin-1"),
        ("\n# coding: latin-1\nx=1", "\n# coding: utf-8\nx=1"),
        ("#!/usr/bin/python\n# coding: latin-1\nx=1", "#!/usr/bin/python\n# coding: utf-8\nx=1"),
        ("# coding: utf-8\nx=1", "# coding: utf-8\nx=1"),
    ],
)
def test_encoding_cookie_never_rewrites_source_literals(text: str, expected: str) -> None:
    assert boundary._utf8_source(text).decode("utf-8") == expected


def test_linux_loader_path_comes_only_from_trusted_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "trusted-python"
    (prefix / "lib").mkdir(parents=True)
    monkeypatch.setattr(boundary, "RUNTIME_PLATFORM", "linux")
    monkeypatch.setattr(boundary, "PYTHON_BASE_PREFIX", str(prefix))
    monkeypatch.setenv("LD_LIBRARY_PATH", "secret-ambient-path")
    monkeypatch.setenv("LD_PRELOAD", "secret-ambient-library")
    environment = boundary._environment(tmp_path)
    assert environment["LD_LIBRARY_PATH"] == str((prefix / "lib").resolve())
    assert "LD_PRELOAD" not in environment
    assert "secret-ambient" not in repr(environment)


@pytest.mark.parametrize("kind", list(SecurityFailure))
def test_failure_reason_is_structured_not_raw_message(kind: SecurityFailure) -> None:
    scanner = MagicMock()
    scanner.scan.side_effect = SecurityToolFailed("secret-diagnostic", kind)
    result = PythonSecurityAnalyzer(scanner).analyze(context())
    assert result.state == AnalyzerState.FAILED
    assert "secret-diagnostic" not in repr(result)
    assert result.reason is not None


def test_origin_guard_rejects_temporary_storage_inside_target_before_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = tmp_path / "target-temp"
    storage.mkdir()
    monkeypatch.setattr(boundary, "gettempdir", lambda: str(storage))
    allocate = MagicMock(side_effect=AssertionError("No target tree mutation"))
    monkeypatch.setattr(boundary, "TemporaryDirectory", allocate)
    runner = boundary.BanditRunner(origin_root=tmp_path)
    with pytest.raises(SecurityToolFailed, match="overlaps") as error:
        runner.scan(snapshot())
    allocate.assert_not_called()
    assert str(tmp_path) not in str(error.value)


def test_origin_metadata_does_not_require_live_source_after_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    runner = boundary.BanditRunner(origin_root=origin)
    origin.rmdir()
    monkeypatch.setattr(boundary, "_capture", lambda *args: (0, json.dumps(document()).encode()))
    assert runner.scan(snapshot()) == ()


def test_origin_validation_failure_is_sanitized(tmp_path: Path) -> None:
    with pytest.raises(SecurityToolFailed) as error:
        boundary.BanditRunner(origin_root=tmp_path / "secret-missing-origin")
    assert "secret-missing-origin" not in str(error.value)
