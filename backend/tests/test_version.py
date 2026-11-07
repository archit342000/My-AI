import json
import re
from pathlib import Path

from backend.version import VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH, get_version

ROOT = Path(__file__).resolve().parents[2]


def test_version_components_are_ints():
    assert all(isinstance(v, int) for v in (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH))


def test_get_version_string_matches_components():
    assert get_version() == f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"


def test_package_json_matches_backend_version():
    package = json.loads((ROOT / "package.json").read_text())
    assert package["version"] == get_version()


def test_package_lock_matches_backend_version():
    lock_path = ROOT / "package-lock.json"
    if not lock_path.exists():
        return
    lock = json.loads(lock_path.read_text())
    assert lock["version"] == get_version()
    assert lock["packages"][""]["version"] == get_version()


def test_readme_does_not_hardcode_a_version():
    readme = (ROOT / "README.md").read_text()
    assert not re.search(r"Current Version\*\*:\s*`v?\d", readme)
