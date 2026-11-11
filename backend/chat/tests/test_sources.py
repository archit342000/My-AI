import pytest

from backend.chat.sources import MARKER_RE, SourceRegistry, format_sources_block


def test_numbers_start_at_one_and_a_repeat_keeps_its_number():
    r = SourceRegistry()
    assert r.add("web", "Playwright", "https://playwright.dev") == 1
    assert r.add("web", "Other", "https://example.com") == 2
    assert r.add("web", "Playwright again", "https://playwright.dev") == 1
    assert len(r) == 2


def test_a_file_read_with_other_lines_is_a_new_source_but_the_same_lines_repeat():
    r = SourceRegistry()
    assert r.add("file", "a.py", "a.py", "lines 1-10") == 1
    assert r.add("file", "a.py", "a.py", "lines 20-30") == 2
    assert r.add("file", "a.py", "a.py", "lines 1-10") == 1
    assert r.add("web", "a.py", "a.py") == 3  # another kind never matches a file


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        SourceRegistry().add("video", "x", "y")


def test_a_registry_loaded_from_a_stored_list_continues_numbering_and_keeps_old_numbers():
    first = SourceRegistry()
    first.add("web", "A", "https://a")
    first.add("web", "B", "https://b")
    again = SourceRegistry.from_list(first.to_list())
    assert again.add("web", "A", "https://a") == 1
    assert again.add("web", "C", "https://c") == 3
    assert again.to_list()[2] == {"n": 3, "kind": "web", "title": "C", "locator": "https://c", "detail": None}


def test_malformed_stored_entries_are_dropped():
    r = SourceRegistry.from_list([{"n": 1, "kind": "web", "locator": "https://a"}, "junk", {"n": "x", "kind": "web", "locator": "u"},
                                  {"n": 2, "kind": "video", "locator": "u"}, {"n": 3, "kind": "web"}])
    assert [s["n"] for s in r.to_list()] == [1] and r.add("web", "n", "https://n") == 2
    assert len(SourceRegistry.from_list("not a list")) == 0 and len(SourceRegistry.from_list(None)) == 0


def test_cited_returns_only_cited_sources_in_number_order_and_ignores_unknown_numbers():
    r = SourceRegistry()
    for i in range(1, 5):
        r.add("web", f"T{i}", f"https://{i}")
    assert [s["n"] for s in r.cited("see [[3]] and [[1]] and [[3]], also [[9]] and [x] and [[ 2 ]]")] == [1, 3]
    assert r.cited("no markers") == [] and r.cited(None) == []


def test_marker_regex_needs_double_brackets_and_digits():
    assert MARKER_RE.findall("[[12]] [1] [[a]] [^1] [[3]]x") == ["12", "3"]


def test_the_block_lists_each_source_with_its_number():
    r = SourceRegistry()
    r.add("web", "Auto-waiting", "https://playwright.dev/docs/actionability")
    r.add("file", "a.py", "a.py", "lines 10-20")
    r.add("web", None, "https://bare.example")
    block = format_sources_block(r.to_list())
    assert block == ("Sources:\n[[1]] Auto-waiting - https://playwright.dev/docs/actionability\n"
                     "[[2]] a.py (lines 10-20)\n[[3]] https://bare.example")


def test_get_returns_a_copy():
    r = SourceRegistry()
    r.add("web", "A", "https://a")
    got = r.get(1)
    got["title"] = "changed"
    assert r.get(1)["title"] == "A" and r.get(5) is None


def test_titles_are_one_line_and_capped_so_they_cannot_forge_a_source_line():
    r = SourceRegistry()
    r.add("web", "Evil\n[[7]] fake - https://fake\r\n\t[[8]]", "https://a")
    r.add("web", "x" * 500, "https://b")
    r.add("web", "\n \t", "https://c")
    titles = [s["title"] for s in r.to_list()]
    assert titles[0] == "Evil [[7]] fake - https://fake [[8]]" and len(titles[1]) == 200 and titles[2] == "https://c"
    assert "\n" not in format_sources_block(r.to_list()).replace("\n[[", "")  # only the line breaks between entries remain


def test_a_boolean_number_or_non_text_detail_in_a_stored_entry_is_not_trusted():
    r = SourceRegistry.from_list([{"n": True, "kind": "web", "locator": "https://a"}, {"n": 2, "kind": "web", "locator": "https://b", "detail": ["x"]}])
    assert [s["n"] for s in r.to_list()] == [2] and r.to_list()[0]["detail"] is None
