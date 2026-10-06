"""Local documentation links must resolve without a network or Markdown framework."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = tuple(sorted((*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"))))


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_local_documentation_link_destinations_exist(document: Path) -> None:
    text = re.sub(r"```.*?```", "", document.read_text(encoding="utf-8"), flags=re.DOTALL)
    for match in re.finditer(r"\]\(([^\s)]+)\)", text):
        destination = match[1].strip("<>")
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = (document.parent / unquote(parsed.path)).resolve()
        assert target.is_relative_to(ROOT), f"Documentation link escapes repository: {destination}"
        assert target.is_file(), f"Missing documentation destination: {destination}"
