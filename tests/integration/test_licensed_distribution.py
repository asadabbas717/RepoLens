"""Build trusted RepoLens source in a fresh tree; inspect actual licensing artifacts."""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path


def test_clean_build_includes_canonical_license_without_runtime_contract_changes(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[2]
    source = tmp_path / "trusted-repolens"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copyfile(project / name, source / name)
    shutil.copytree(
        project / "src/repolens",
        source / "src/repolens",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    output = tmp_path / "artifacts"
    # Only this project's trusted setuptools build; never a scanned target build.
    result = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output)],
        cwd=source,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    canonical = (project / "LICENSE").read_bytes()
    project_urls = {
        "Repository, https://github.com/asadabbas717/RepoLens",
        "Issues, https://github.com/asadabbas717/RepoLens/issues",
    }
    prefix = "repolens-0.1.0.dev0"
    with zipfile.ZipFile(output / f"{prefix}-py3-none-any.whl") as wheel:
        info = f"{prefix}.dist-info/"
        assert wheel.read(info + "licenses/LICENSE") == canonical
        data = BytesParser().parsebytes(wheel.read(info + "METADATA"))
        assert data["License-Expression"] == "Apache-2.0"
        assert data.get_all("License-File") == ["LICENSE"]
        assert set(data.get_all("Project-URL") or ()) == project_urls
        assert data["Version"] == "0.1.0.dev0"
        assert data.get_all("Requires-Dist") == ["PyYAML<7,>=6.0.3"]
        assert data["Requires-Python"] == ">=3.13"
        assert wheel.read("repolens/py.typed") == b""
        assert b"repolens = repolens.cli:main" in wheel.read(info + "entry_points.txt")
        assert all(name.startswith(("repolens/", info)) for name in wheel.namelist())
    with tarfile.open(output / f"{prefix}.tar.gz") as archive:
        stream = archive.extractfile(f"{prefix}/LICENSE")
        assert stream is not None
        with stream:
            assert stream.read() == canonical
        metadata_stream = archive.extractfile(f"{prefix}/PKG-INFO")
        assert metadata_stream is not None
        with metadata_stream:
            source_metadata = BytesParser().parsebytes(metadata_stream.read())
            assert source_metadata["License-Expression"] == "Apache-2.0"
            assert set(source_metadata.get_all("Project-URL") or ()) == project_urls
