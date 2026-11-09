"""container_check.py is run inside a built container, not here; this only guards its scenario table."""
import container_check


def test_every_evidenced_scenario_is_in_the_table():
    names = [name for name, _ in container_check.SCENARIOS]
    assert len(names) == len(set(names)) == 9
    for needle in ("languages", "uid 61001", "leftovers", "writes", "API key", "non-writable", "serialise", "forks", "installs"):
        assert any(needle in n for n in names), needle


def test_the_scenario_table_covers_every_language():
    assert set(container_check.HELLO) == {"python", "c", "cpp", "java", "javascript", "typescript", "go", "rust", "bash", "php", "sql"}
    assert all(callable(fn) for _, fn in container_check.SCENARIOS)
