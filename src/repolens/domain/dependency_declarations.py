"""Parse a deliberately small exact-pin subset, without resolution or host markers."""

import re
import tomllib
from dataclasses import dataclass

from repolens.domain.dependency_manifest import DependencyManifestSnapshot

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_VERSION = (
    r"[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?"
    r"(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:[._-][a-z0-9]+)*)?"
)
_PIN = re.compile(rf"({_NAME})\s*==\s*({_VERSION})")


class UnsupportedDeclarations(Exception):
    """Declaration syntax or dependency provider is outside the static subset."""


class InvalidManifest(Exception):
    """Manifest structural parsing failed, without raw diagnostic content."""


@dataclass(frozen=True, slots=True)
class DeclaredDependency:
    name: str
    version: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or re.fullmatch(_NAME, self.name) is None
            or self.name != re.sub(r"[-_.]+", "-", self.name).lower()
            or not isinstance(self.version, str)
            or re.fullmatch(_VERSION, self.version) is None
        ):
            raise ValueError("Dependency must be a canonical name and supported exact version")


def parse_declarations(snapshot: DependencyManifestSnapshot) -> tuple[DeclaredDependency, ...]:
    declarations: list[str] = []
    for manifest in snapshot.files:
        if manifest.path == "requirements.txt":
            for line in manifest.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                declarations.append(re.split(r"\s+#", line, maxsplit=1)[0].strip())
        else:
            try:
                document = tomllib.loads(manifest.text)
            except (tomllib.TOMLDecodeError, RecursionError):
                raise InvalidManifest("Dependency manifest could not be parsed") from None
            project = document.get("project", {})
            if not isinstance(project, dict):
                raise InvalidManifest("Project metadata must be a table")
            dynamic = project.get("dynamic", [])
            dependencies = project.get("dependencies", [])
            if (
                not isinstance(dynamic, list)
                or any(not isinstance(item, str) for item in dynamic)
                or not isinstance(dependencies, list)
                or any(not isinstance(item, str) for item in dependencies)
            ):
                raise InvalidManifest("Dependency fields have invalid types")
            if "dependencies" in dynamic:
                raise UnsupportedDeclarations("Dynamic dependency declarations are unsupported")
            declarations.extend(dependencies)
    if len(declarations) > 1000:
        raise UnsupportedDeclarations("Dependency declaration count exceeded")
    packages: dict[str, DeclaredDependency] = {}
    for declaration in declarations:
        match = _PIN.fullmatch(declaration)
        if match is None:
            raise UnsupportedDeclarations(
                "Only the documented static exact-pin subset is supported"
            )
        name, version = match.groups()
        name = re.sub(r"[-_.]+", "-", name).lower()
        package = DeclaredDependency(name, version)
        if name in packages and packages[name] != package:
            raise UnsupportedDeclarations("Conflicting direct dependency declarations")
        packages[name] = package
    return tuple(packages[name] for name in sorted(packages))
