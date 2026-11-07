from scripts.changelog import group_commits, parse_subject, render


def test_parse_subject_with_scope():
    assert parse_subject("feat(chat): add validator") == ("feat", "chat", "add validator")


def test_parse_subject_without_scope():
    assert parse_subject("fix: handle empty input") == ("fix", None, "handle empty input")


def test_parse_subject_rejects_non_conventional():
    assert parse_subject("App version update") is None
    assert parse_subject("wip: stuff") is None


def test_group_commits_buckets_other():
    groups = group_commits(["feat: a", "fix(db): b", "App version update"])
    assert groups["feat"] == ["a"]
    assert groups["fix"] == ["**db:** b"]
    assert groups["other"] == ["App version update"]


def test_render_skips_empty_sections_and_titles_version():
    out = render(group_commits(["feat: a"]), version="4.11.0")
    assert out.startswith("## v4.11.0")
    assert "### Features" in out
    assert "### Fixes" not in out
