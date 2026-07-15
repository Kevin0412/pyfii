#!/usr/bin/env python3
"""Write auditable pins for inclusive minimum versions in pyproject.toml."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version


def minimum_pin(dependency: str) -> str | None:
    """Return ``name==version`` for a dependency with an inclusive minimum."""
    try:
        requirement = Requirement(dependency)
    except InvalidRequirement as error:
        raise ValueError(f"invalid dependency {dependency!r}: {error}") from error

    candidates: list[Version] = []
    for specifier in requirement.specifier:
        if specifier.operator not in {">=", "~=", "==", "==="}:
            continue
        if "*" in specifier.version:
            continue
        try:
            candidates.append(Version(specifier.version))
        except InvalidVersion as error:
            raise ValueError(
                f"invalid version in dependency {dependency!r}: {specifier.version!r}"
            ) from error

    if not candidates:
        print(
            f"warning: {requirement.name} has no inclusive minimum; "
            "the resolved-project audit still covers its latest version",
            file=sys.stderr,
        )
        return None

    minimum = max(candidates)
    if not requirement.specifier.contains(minimum, prereleases=True):
        raise ValueError(
            f"cannot represent the minimum allowed version for {dependency!r}"
        )
    return f"{requirement.name}=={minimum}"


def main() -> int:
    if len(sys.argv) != 3:
        print(
            f"usage: {Path(sys.argv[0]).name} PYPROJECT OUTPUT",
            file=sys.stderr,
        )
        return 2

    pyproject_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    dependencies = pyproject.get("project", {}).get("dependencies", [])
    pins = [pin for dependency in dependencies if (pin := minimum_pin(dependency))]
    if not pins:
        raise ValueError(f"no auditable minimum dependencies in {pyproject_path}")

    output_path.write_text("\n".join(pins) + "\n", encoding="utf-8")
    print(f"wrote {len(pins)} minimum dependency pins to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
