"""Private publication checks, never imported by RepoLens's runtime package."""

import argparse
import ast
import hashlib
import os
import re
import subprocess
import tarfile
import tomllib
import zipfile
from email.message import Message
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

NAME = "repolens-engineering"
URLS = {
    "Repository, https://github.com/asadabbas717/RepoLens",
    "Issues, https://github.com/asadabbas717/RepoLens/issues",
}


def validate_request(tag: str, sha: str) -> str:
    if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag):
        raise ValueError("A canonical release tag is required")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("An exact commit SHA is required")
    return tag[1:]


def _git_value(root: Path, ref: str) -> str:
    return (
        subprocess.check_output(["git", "rev-parse", ref], cwd=root, stderr=subprocess.DEVNULL)
        .decode("ascii")
        .strip()
    )


def validate_source(root: Path, tag: str, sha: str) -> str:
    version = validate_request(tag, sha)
    if _git_value(root, "HEAD") != sha or _git_value(root, f"refs/tags/{tag}^{{commit}}") != sha:
        raise ValueError("Tag and checked-out source must match the expected commit")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project["name"] != NAME or project["version"] != version:
        raise ValueError("Distribution name or version disagrees with the tag")
    tree = ast.parse((root / "src/repolens/__init__.py").read_text(encoding="utf-8"))
    declarations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    ]
    if (
        len(declarations) != 1
        or declarations[0] not in tree.body
        or not isinstance(declarations[0].value, ast.Constant)
        or declarations[0].value.value != version
        or any(
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__version__"
            for node in ast.walk(tree)
        )
    ):
        raise ValueError("Runtime version disagrees with the tag")
    return version


def _metadata(data: Message, version: str) -> None:
    fields = {
        "Name": NAME,
        "Version": version,
        "License-Expression": "Apache-2.0",
        "Requires-Python": ">=3.13",
        "Description-Content-Type": "text/markdown",
    }
    if any(data[key] != value for key, value in fields.items()):
        raise ValueError("Distribution metadata violates the release contract")
    if data.get_all("Requires-Dist") != ["PyYAML<7,>=6.0.3"]:
        raise ValueError("Runtime dependencies changed")
    if set(data.get_all("Project-URL") or ()) != URLS:
        raise ValueError("Public project URLs changed")
    if data.get_all("License-File") != ["LICENSE"]:
        raise ValueError("License file metadata is missing")


def validate_artifacts(root: Path, directory: Path, version: str) -> tuple[Path, Path]:
    validate_request("v" + version, "a" * 40)
    prefix = "repolens_engineering-" + version
    wheel = directory / (prefix + "-py3-none-any.whl")
    source = directory / (prefix + ".tar.gz")
    if set(directory.iterdir()) != {wheel, source}:
        raise ValueError("Exactly the expected wheel and sdist are required")
    license_bytes = (root / "LICENSE").read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        info = prefix + ".dist-info/"
        if len(names) != len(set(names)) or any(
            ".." in PurePosixPath(name).parts or not name.startswith(("repolens/", info))
            for name in names
        ):
            raise ValueError("Unexpected wheel contents")
        if any(member.file_size > 2 * 1024 * 1024 for member in archive.infolist()):
            raise ValueError("Oversized wheel member")
        _metadata(BytesParser().parsebytes(archive.read(info + "METADATA")), version)
        if archive.read(info + "licenses/LICENSE") != license_bytes:
            raise ValueError("Wheel license differs")
        if archive.read("repolens/py.typed") != b"":
            raise ValueError("Typing marker differs")
        entry = archive.read(info + "entry_points.txt").decode("utf-8")
        if entry.strip() != "[console_scripts]\nrepolens = repolens.cli:main":
            raise ValueError("Console entry point changed")
        expected = {
            "repolens/" + path.relative_to(root / "src/repolens").as_posix()
            for path in (root / "src/repolens").rglob("*.py")
        }
        if {name for name in names if name.endswith(".py")} != expected:
            raise ValueError("Wheel import namespace/source set changed")
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        forbidden = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build", ".coverage"}
        if any(
            member.issym()
            or member.islnk()
            or member.size > 2 * 1024 * 1024
            or forbidden.intersection(PurePosixPath(member.name).parts)
            or ".." in PurePosixPath(member.name).parts
            or not (member.name == prefix or member.name.startswith(prefix + "/"))
            for member in members
        ):
            raise ValueError("Unexpected sdist contents")
        for name, expected_bytes in (("LICENSE", license_bytes), ("src/repolens/py.typed", b"")):
            stream = archive.extractfile(prefix + "/" + name)
            if stream is None:
                raise ValueError("Required source file missing")
            with stream:
                if stream.read() != expected_bytes:
                    raise ValueError("Source license/typing marker differs")
        stream = archive.extractfile(prefix + "/PKG-INFO")
        if stream is None:
            raise ValueError("Source metadata missing")
        with stream:
            _metadata(BytesParser().parsebytes(stream.read()), version)
    return wheel, source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("source", "artifacts"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--directory", type=Path, default=Path("dist"))
    args = parser.parse_args()
    version = validate_source(Path.cwd(), args.tag, args.sha)
    values = {"version": version}
    if args.mode == "artifacts":
        wheel, source = validate_artifacts(Path.cwd(), args.directory, version)
        values.update(
            wheel=wheel.name,
            sdist=source.name,
            wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            sdist_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
    destination = os.environ.get("GITHUB_OUTPUT")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
    print("Publication source/artifact checks passed")


if __name__ == "__main__":
    main()
