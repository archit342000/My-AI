import pytest
from unittest.mock import patch
from backend.tools.skills_tool import get_skill_details


@pytest.fixture
def mock_db():
    with patch("backend.tools.skills_tool.db") as mock:
        yield mock


def test_get_skill_details_success(mock_db):
    mock_db.get_skill_by_name.return_value = {
        "id": "skill-123",
        "name": "git-helper",
        "description": "Helps with git commands",
        "instructions": "Run git status first.",
    }

    res = get_skill_details("git-helper", user_id="user-a")
    assert "Successfully loaded skill details for 'git-helper'" in res
    mock_db.get_skill_by_name.assert_called_once_with("git-helper", "user-a")


def test_get_skill_details_not_found(mock_db):
    mock_db.get_skill_by_name.return_value = None

    res = get_skill_details("unknown-skill", user_id="user-a")
    assert "Error: Skill 'unknown-skill' not found" in res
    mock_db.get_skill_by_name.assert_called_once_with("unknown-skill", "user-a")


def test_get_skill_details_without_an_owner_is_an_error(mock_db):
    with patch("backend.tools.skills_tool.log_event") as events:
        res = get_skill_details("git-helper")
    assert res.startswith("Error:") and "no owner" in res
    events.assert_called_once_with("tool_missing_owner", {"tool": "get_skill_details"})
    mock_db.get_skill_by_name.assert_not_called()


def test_get_skill_details_does_not_find_another_users_skill(tmp_path):
    from backend.database.init_db import init_db
    from backend.database.db_wrapper import DatabaseWrapper
    path = str(tmp_path / "s.db")
    with patch("backend.database.db_layer.DB_PATH", path), patch("backend.database.init_db.DB_PATH", path), \
         patch("backend.database.db_wrapper.DB_PATH", path):
        init_db()
        real = DatabaseWrapper()
        real.add_skill("s1", "secret-skill", "d", "i", user_id="ua")
        with patch("backend.tools.skills_tool.db", real):
            assert "Successfully loaded" in get_skill_details("secret-skill", user_id="ua")
            assert "not found" in get_skill_details("secret-skill", user_id="ub")

