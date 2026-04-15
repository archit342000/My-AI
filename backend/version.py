"""Semantic versioning constant for the application.

This module provides programmatic access to the application version
following Semantic Versioning 2.0.0 (https://semver.org/).
"""

# Application version - see CHANGELOG.md for version history
VERSION = "3.1.0"
VERSION_MAJOR = 3
VERSION_MINOR = 1
VERSION_PATCH = 0


def get_version() -> str:
    """Return the full version string with v prefix.

    Returns:
        str: Version string in format "vMAJOR.MINOR.PATCH"
    """
    return f"v{VERSION}"


def get_version_tuple() -> tuple[int, int, int]:
    """Return version as a tuple of integers.

    Returns:
        tuple: (MAJOR, MINOR, PATCH) as integers
    """
    return (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)
