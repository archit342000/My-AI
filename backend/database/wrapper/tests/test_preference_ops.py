import os
import pytest
import tempfile
import shutil
from unittest.mock import patch
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_chats.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        yield wrapper
    shutil.rmtree(tmp_dir)

def test_preference_ops(temp_db):
    db = temp_db
    pref_id = db.add_preference(
        content="AI tone should be professional",
        tag="style", user_id="u1")
    assert pref_id is not None
    
    prefs = db.get_all_preferences(user_id="u1")
    assert len(prefs) > 0
    assert any(p['id'] == pref_id and p['tag'] == "style" for p in prefs)
    
    db.delete_preference(pref_id, user_id="u1")
    assert not any(p['id'] == pref_id for p in db.get_all_preferences(user_id="u1"))

    # Test update_preference
    pref_id_2 = db.add_preference("Test content", "test_tag", user_id="u1")
    res = db.update_preference(pref_id_2, "Updated content", "updated_tag", user_id="u1")
    assert res is True
    prefs = db.get_all_preferences(user_id="u1")
    updated_pref = next((p for p in prefs if p['id'] == pref_id_2), None)
    assert updated_pref is not None
    assert updated_pref['content'] == "Updated content"
    assert updated_pref['tag'] == "updated_tag"

    # Test clear_preferences
    db.add_preference("Another", "another_tag", user_id="u1")
    assert len(db.get_all_preferences(user_id="u1")) >= 2
    res = db.clear_preferences(user_id="u1")
    assert res > 0
    assert len(db.get_all_preferences(user_id="u1")) == 0


def test_preferences_are_per_user(temp_db):
    db = temp_db
    ia = db.add_preference("A likes tea", "drink", user_id="pa")
    ib = db.add_preference("B likes coffee", "drink", user_id="pb")
    assert [p["id"] for p in db.get_all_preferences("pa")] == [ia]
    assert [p["id"] for p in db.get_all_preferences("pb")] == [ib]
    # a foreign id is "not found": nothing is changed
    assert db.update_preference(ia, "stolen", "x", user_id="pb") is False
    assert db.delete_preference(ia, user_id="pb") is False
    assert db.get_all_preferences("pa")[0]["content"] == "A likes tea"
    # clearing one user's preferences leaves the other's
    assert db.clear_preferences("pa") == 1
    assert db.get_all_preferences("pa") == []
    assert [p["id"] for p in db.get_all_preferences("pb")] == [ib]


def test_preferences_refuse_an_empty_user_id(temp_db):
    for call in (lambda: temp_db.get_all_preferences(""), lambda: temp_db.add_preference("c", "t", user_id=""),
                 lambda: temp_db.update_preference("i", "c", "t", user_id=None), lambda: temp_db.delete_preference("i", user_id=""),
                 lambda: temp_db.clear_preferences("")):
        with pytest.raises(ValueError):
            call()

