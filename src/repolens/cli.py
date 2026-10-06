"""Argparse shell boundary and explicit product composition; no report renderer."""

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from repolens import __version__
from repolens.analyzers.ci_static import GitHubActionsAnalyzer
from repolens.analyzers.hygiene import RepositoryHygieneAnalyzer
from repolens.analyzers.python_security import PythonSecurityAnalyzer
from repolens.analyzers.python_static import PythonStaticAnalyzer
from repolens.analyzers.testing_static import TestingStaticAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.application.scoring_policy import PYTHON_STATIC_V1
from repolens.domain.report import AnalysisReport
from repolens.domain.security import BanditScan, SecurityToolFailed
from repolens.infrastructure.analysis_context import snapshot_analysis_context
from repolens.infrastructure.bandit import BanditRunner
from repolens.infrastructure.errors import AcquisitionError, InvalidSource
from repolens.infrastructure.repository_source import (
    RepositorySource,
    SourceKind,
    canonical_github_url,
)

_SCOPE = (
    "Python-first static assessment; no target code or workflows are executed. "
    "Dependency vulnerability auditing is not included in the default assessment."
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse diagnostics can echo hostile arguments and credential URLs.
        self.print_usage(sys.stderr)
        self.exit(2, "repolens: invalid arguments; use --help for accepted syntax.\n")


def _threshold(value: str) -> Decimal:
    # A small literal grammar rejects exponent notation and hidden precision.
    if re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value, flags=re.ASCII) is None:
        raise argparse.ArgumentTypeError("Expected a score from 0 to 100 with at most two decimals")
    threshold = Decimal(value)
    if not threshold.is_finite() or not 0 <= threshold <= 100:
        raise argparse.ArgumentTypeError("Expected a finite score from 0 to 100")
    return threshold


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="repolens", description=_SCOPE, allow_abbrev=False)
    parser.add_argument("--version", action="version", version=f"repolens {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser(
        "scan",
        help="assess one local Git working tree or public GitHub HTTPS repository",
        description=_SCOPE,
        epilog=f"Policy: {PYTHON_STATIC_V1.identifier}. Scores describe supported observations.",
        allow_abbrev=False,
    )
    scan.add_argument("source", metavar="SOURCE", help="local Git path or public GitHub HTTPS URL")
    scan.add_argument(
        "--fail-under",
        type=_threshold,
        metavar="SCORE",
        help="fail if the overall score is unavailable or below SCORE (0..100, up to two decimals)",
    )
    parser.epilog = f"Policy: {PYTHON_STATIC_V1.identifier}. See 'repolens scan --help'."
    return parser


@dataclass(frozen=True, slots=True)
class _Source:
    kind: SourceKind
    value: str


def _classify_source(value: str) -> _Source:
    if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise InvalidSource("Source spelling is invalid")
    if re.match(r"^[A-Za-z]:[/\\]", value):
        return _Source(SourceKind.LOCAL, value)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value.lstrip()) or re.match(
        r"^[^/\\\s]+@[^/\\\s]+:", value
    ):
        return _Source(SourceKind.GITHUB, canonical_github_url(value))
    return _Source(SourceKind.LOCAL, value)


def default_analyzer_plan(scanner: BanditScan) -> AnalyzerPlan:
    """Fixed declared capability, never trimmed according to results or input."""
    return AnalyzerPlan(
        (
            RepositoryHygieneAnalyzer(),
            PythonStaticAnalyzer(),
            TestingStaticAnalyzer(),
            PythonSecurityAnalyzer(scanner),
            GitHubActionsAnalyzer(),
        )
    )


def _scan(source: _Source) -> AnalysisReport:
    acquisition = RepositorySource()
    resource = (
        acquisition.local(Path(source.value))
        if source.kind == SourceKind.LOCAL
        else acquisition.github(source.value)
    )
    with resource as lease:
        context = snapshot_analysis_context(lease)
        plan = default_analyzer_plan(BanditRunner(origin_root=lease.root))
    # Remote workspaces are already deleted. Analyzers receive detached data only.
    results = execute_analyzers(plan, context)
    return AnalysisReport(context.repository, plan.specs, results, PYTHON_STATIC_V1)


def _status(report: AnalysisReport, threshold: Decimal | None) -> int:
    value = report.score.value
    print("Assessment: " + ("complete" if value is not None else "incomplete"))
    print(f"Policy: {report.policy.identifier}")
    print(f"Overall score: {value if value is not None else 'unavailable'}")
    print(f"Findings: {len(report.findings)} (INFO observations are retained)")
    print("Dependency vulnerability auditing: not included in the default assessment.")
    unavailable = sorted(
        identifier
        for category in report.score.categories
        for identifier in category.unavailable_analyzers
    )
    if unavailable:
        states = {result.analyzer.identifier: result.state.value for result in report.results}
        print(
            "Unavailable analyzers: "
            + ", ".join(
                f"{identifier} ({states.get(identifier, 'missing')})" for identifier in unavailable
            )
        )
    if threshold is not None:
        gate = "unavailable" if value is None else "met" if value >= threshold else "not met"
        print(f"Score gate: {gate}")
    return 1 if value is None or (threshold is not None and value < threshold) else 0


def run(argv: Sequence[str]) -> int:
    """Return scan status; argparse help/version/input exits follow normal conventions."""
    try:
        arguments = _parser().parse_args(argv)
        source = arguments.source
        threshold = arguments.fail_under
        if not isinstance(source, str) or (
            threshold is not None and not isinstance(threshold, Decimal)
        ):
            raise TypeError("Invalid parsed scan values")
        report = _scan(_classify_source(source))
        return _status(report, threshold)
    except (AcquisitionError, SecurityToolFailed):
        print("repolens: source acquisition or input processing failed safely.", file=sys.stderr)
        return 2
    except Exception:
        print("repolens: unexpected internal failure.", file=sys.stderr)
        return 3


def main() -> NoReturn:
    """Installed console entry point."""
    raise SystemExit(run(sys.argv[1:]))
