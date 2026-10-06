"""Owned inert source data, materialized only in temporary Git repositories."""

from pathlib import Path

from repolens.infrastructure.git import GitRunner

_WORKFLOW = (
    "on: push\npermissions: read-all\njobs:\n  checks:\n"
    "    runs-on: ubuntu-latest\n    steps:\n"
    "      - uses: fixture-owner/inert-action@" + "a" * 40 + "\n"
    "      - run: touch workflow-executed\n"
)
_MARKER = "from pathlib import Path\nPath(__file__).with_name('{name}-executed').touch()\n"

CASES: dict[str, dict[str, str]] = {
    "clean-python": {
        ".gitignore": "*.pyc\n",
        "app.py": "def add(left: int, right: int) -> int:\n    return left + right\n",
        "tests/test_app.py": "def test_add():\n    pass\n",
        ".github/workflows/check.yml": _WORKFLOW,
    },
    "poor-python": {
        "app.py": _MARKER.format(name="application")
        + "from unknown_module import *\ntry:\n    pass\nexcept:\n    pass\n"
        + "password = 'inert-example-only'\n",
        "setup.py": _MARKER.format(name="setup"),
        "checks.py": _MARKER.format(name="test"),
        "repolens.toml": "not valid configuration [\n",
        ".github/workflows/check.yml": _WORKFLOW.replace("read-all", "write-all").replace(
            "a" * 40, "v1"
        ),
    },
    "non-python": {
        ".gitignore": "generated/\n",
        "index.html": "<!doctype html><title>Inert owned fixture</title>\n",
        "app.js": "// Static fixture; never executed.\n",
        ".github/workflows/check.yml": _WORKFLOW,
    },
}

CONFIGURATION = (
    'schema_version = 1\n[scan]\nexclude = ["setup.py", "checks.py"]\n'
    '[rules]\ndisable = ["PY002", "CI003", "BANDIT-B105"]\n'
    '[gate]\nfail_under = "99"\nfail_on_severity = "medium"\n'
)


def materialize(parent: Path, case: str) -> Path:
    """No nested Git data is committed; the caller owns the new fixture root."""
    root = parent / case
    root.mkdir()
    for name, text in CASES[case].items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    if GitRunner().run(("init", "--quiet"), root, 10).returncode:
        raise RuntimeError("Owned fixture Git initialization failed")
    return root
