import pytest
from unittest.mock import MagicMock, patch
from backend.tools.preferences import add_user_preference, edit_user_preference, delete_user_preference

@pytest.fixture
def mock_db():
    with patch('backend.tools.preferences.db') as mock:
        yield mock

def test_add_user_preference(mock_db):
    mock_db.add_preference.return_value = "id12345678"
    mock_db.get_all_preferences.return_value = [{"id": "id12345678", "tag": "personal_info", "content": "Likes cats"}]
    
    res = add_user_preference(content="Likes cats", tag="personal_info", user_id="user-a")
    
    assert "Added preference [id123456]" in res
    assert "Likes cats" in res
    mock_db.add_preference.assert_called_once_with("Likes cats", "personal_info", "user-a")
    mock_db.get_all_preferences.assert_called_once_with("user-a")

def test_edit_user_preference(mock_db):
    mock_db.update_preference.return_value = True
    mock_db.get_all_preferences.return_value = [{"id": "id1", "tag": "other", "content": "New content"}]
    
    res = edit_user_preference(id="id1", content="New content", tag="other", user_id="user-a")
    
    assert "Updated preference [id1]: OK" in res
    mock_db.update_preference.assert_called_once_with("id1", "New content", "other", "user-a")

def test_delete_user_preference(mock_db):
    mock_db.delete_preference.return_value = True
    mock_db.get_all_preferences.return_value = []
    
    res = delete_user_preference(id="id2", user_id="user-a")
    
    assert "Deleted preference [id2]: OK" in res
    mock_db.delete_preference.assert_called_once_with("id2", "user-a")

def test_edit_user_preference_not_found(mock_db):
    mock_db.update_preference.return_value = False
    mock_db.get_all_preferences.return_value = []
    
    res = edit_user_preference(user_id="user-a", id="missing", content="X", tag="other")
    assert "Updated preference [missing]: NOT FOUND" in res

def test_add_user_preference_db_error(mock_db):
    mock_db.add_preference.side_effect = Exception("DB Disk Image Malformed")
    res = add_user_preference(content="Likes cats", tag="personal_info", user_id="user-a")
    assert "Error: Failed to add user preference: DB Disk Image Malformed" in res


@pytest.mark.parametrize("call", [
    lambda: add_user_preference(content="c", tag="t"),
    lambda: edit_user_preference(id="i", content="c", tag="t"),
    lambda: delete_user_preference(id="i"),
])
def test_preference_tools_without_an_owner_return_an_error_and_touch_nothing(mock_db, call):
    with patch('backend.tools.preferences.log_event') as events:
        result = call()
    assert result.startswith("Error:") and "no owner" in result
    events.assert_called_once()
    assert events.call_args.args[0] == "tool_missing_owner"
    assert not mock_db.mock_calls  # no db access at all


def test_preference_tools_only_see_the_owners_rows_on_a_real_db(tmp_path):
    """Two users on a real (temporary) database: each tool call acts only on the given user's preferences."""
    from unittest.mock import patch as _patch
    from backend.database.init_db import init_db
    from backend.database.db_wrapper import DatabaseWrapper
    path = str(tmp_path / "t.db")
    with _patch("backend.database.db_layer.DB_PATH", path), _patch("backend.database.init_db.DB_PATH", path), \
         _patch("backend.database.db_wrapper.DB_PATH", path), _patch("backend.tools.preferences.db", DatabaseWrapper()):
        init_db()
        out_a = add_user_preference(content="A likes tea", tag="drink", user_id="ua")
        add_user_preference(content="B likes coffee", tag="drink", user_id="ub")
        assert "A likes tea" in out_a and "B likes coffee" not in out_a
        a_id = out_a.split("[")[2].split("]")[0]  # the dump lists "[<full id>] ..."
        foreign_edit = edit_user_preference(id=a_id, content="hijacked", tag="x", user_id="ub")
        foreign_delete = delete_user_preference(id=a_id, user_id="ub")
        assert "NOT FOUND" in foreign_edit and "NOT FOUND" in foreign_delete
        assert "A likes tea" not in foreign_edit and "A likes tea" not in foreign_delete  # the other user's text is never shown
        assert "A likes tea" in add_user_preference(content="more", tag="drink", user_id="ua")  # untouched

