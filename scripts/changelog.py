"""Generate changelog entries from conventional commit messages.

Usage:
    venv/bin/python scripts/changelog.py [--since REF] [--version X.Y.Z]

Prints Markdown to stdout. Release history through v4.10.0 is archived in
docs/archive/changelog-through-v4.10.0.md; BASELINE_REF is the commit that
archive ends at.
"""
import argparse
import re
import subprocess
from collections import OrderedDict

BASELINE_REF = "98df1cb"

SECTIONS = OrderedDict([
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("chore", "Chores"),
])

_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(\((?P<scope>[^)]+)\))?!?:\s*(?P<text>.+)$")


def parse_subject(subject):
    """Return (type, scope, text) for a conventional subject, else None."""
    match = _SUBJECT.match(subject.strip())
    if not match or match.group("type") not in SECTIONS:
        return None
    return match.group("type"), match.group("scope"), match.group("text")


def group_commits(subjects):
    """Group subjects by type. Non-conventional subjects go under 'other'."""
    groups = OrderedDict((key, []) for key in SECTIONS)
    groups["other"] = []
    for subject in subjects:
        parsed = parse_subject(subject)
        if parsed is None:
            groups["other"].append(subject.strip())
            continue
        commit_type, scope, text = parsed
        groups[commit_type].append(f"**{scope}:** {text}" if scope else text)
    return groups


def render(groups, version=None):
    title = f"## v{version}" if version else "## Unreleased"
    lines = [title]
    for key, entries in groups.items():
        if not entries:
            continue
        lines.append(f"### {SECTIONS.get(key, 'Other')}")
        lines.extend(f"* {entry}" for entry in entries)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def git_subjects(since):
    out = subprocess.run(
        ["git", "log", f"{since}..HEAD", "--no-merges", "--format=%s"],
        check=True, capture_output=True, text=True,
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=BASELINE_REF)
    parser.add_argument("--version")
    args = parser.parse_args()
    print(render(group_commits(git_subjects(args.since)), args.version), end="")


if __name__ == "__main__":
    main()
