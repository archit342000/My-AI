"""Allowlist validation of package specs for the runner's `/install` endpoint.

Only plain package names (with an optional version or extras) are accepted, so a caller cannot pass
options (`--index-url ...`, `-r file`), URLs or local paths to pip or npm.
"""
import re

MAX_PACKAGES = 20
MAX_PACKAGE_LENGTH = 100

# name, optional [extras], optional single version specifier
_PIP = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"(?:\[[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*\])?"
    r"(?:(?:==|!=|<=|>=|~=|<|>)[A-Za-z0-9.*+!_-]+)?",
    re.ASCII,
)
# optional @scope/, name (legacy packages such as JSONStream have capitals), optional @version-or-tag
_NPM = re.compile(
    r"(?:@[A-Za-z0-9][A-Za-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]*(?:@[A-Za-z0-9.^~<>=*+_-]+)?",
    re.ASCII,
)
_PATTERNS = {"pip": _PIP, "npm": _NPM}


def validate_packages(manager: str, packages: list[str]) -> None:
    """
    Checks every requested package spec against the allowlist for the package manager.

    Args:
        manager: `"pip"` or `"npm"`.
        packages: The requested package specs.

    Raises:
        ValueError: With a short reason naming the first rejected entry, for an unsupported manager, too
            many packages, or a spec that is empty, too long or not a plain package name.
    """
    pattern = _PATTERNS.get(manager)
    if pattern is None:
        raise ValueError(f"Unsupported package manager: {manager}")
    if len(packages) > MAX_PACKAGES:
        raise ValueError(f"Too many packages (max {MAX_PACKAGES})")
    for entry in packages:
        if len(entry) > MAX_PACKAGE_LENGTH:
            raise ValueError(f"Package name too long (max {MAX_PACKAGE_LENGTH})")
        if not entry or not pattern.fullmatch(entry):
            raise ValueError(f"Invalid package: {entry[:50]!r}")
