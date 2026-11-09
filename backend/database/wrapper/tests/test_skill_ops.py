import os
import pytest
import tempfile
import shutil
import time
from unittest.mock import patch
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_skills.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        yield wrapper
    shutil.rmtree(tmp_dir)

def test_skill_ops(temp_db):
    db = temp_db

    # 1. Test adding a skill
    success = db.add_skill(
        skill_id="skill_1",
        name="write-poem",
        description="Writes amazing short poems",
        instructions="Write a poem of exactly 4 lines.",
        user_id="u1"
    )
    assert success is True

    # 2. Test fetching the skill by ID
    skill = db.get_skill("skill_1", "u1")
    assert skill is not None
    assert skill["id"] == "skill_1"
    assert skill["name"] == "write-poem"
    assert skill["description"] == "Writes amazing short poems"
    assert skill["instructions"] == "Write a poem of exactly 4 lines."
    assert isinstance(skill["timestamp"], float)

    # 3. Test fetching the skill by name
    skill_by_name = db.get_skill_by_name("write-poem", "u1")
    assert skill_by_name is not None
    assert skill_by_name["id"] == "skill_1"

    # 4. Test updating/replacing a skill
    success_update = db.add_skill(
        skill_id="skill_1",
        name="write-poem",
        description="Writes amazing short poems (updated)",
        instructions="Write a poem of exactly 5 lines.",
        user_id="u1"
    )
    assert success_update is True
    updated_skill = db.get_skill("skill_1", "u1")
    assert updated_skill["description"] == "Writes amazing short poems (updated)"
    assert updated_skill["instructions"] == "Write a poem of exactly 5 lines."

    # 5. Test listing multiple skills
    time.sleep(0.01)  # small pause to ensure chronological timestamp separation
    success_2 = db.add_skill(
        skill_id="skill_2",
        name="code-refactor",
        description="Refactors python scripts",
        instructions="Make python code follow pep8.",
        user_id="u1"
    )
    assert success_2 is True

    skills = db.get_all_skills("u1")
    assert len(skills) == 2
    # Ordered by timestamp desc, so newest (skill_2) is first
    assert skills[0]["id"] == "skill_2"
    assert skills[1]["id"] == "skill_1"

    # 6. Test deleting a skill
    success_del = db.delete_skill("skill_1", "u1")
    assert success_del is True

    deleted_skill = db.get_skill("skill_1", "u1")
    assert deleted_skill is None

    skills_after_del = db.get_all_skills("u1")
    assert len(skills_after_del) == 1
    assert skills_after_del[0]["id"] == "skill_2"

    # 7. Test fetching non-existent skill yields None
    assert db.get_skill("non_existent", "u1") is None
    assert db.get_skill_by_name("non_existent", "u1") is None

    # 8. Deleting a non-existent skill returns False (it does not crash)
    assert db.delete_skill("non_existent", "u1") is False

    # 9. Test strict UNIQUE name constraint enforcement
    # Trying to insert another skill with a DIFFERENT ID but duplicate NAME must raise sqlite3.IntegrityError
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.add_skill(
            skill_id="skill_3",
            name="code-refactor",  # duplicate of skill_2's name!
            description="another desc",
            instructions="another instructions",
            user_id="u1"
        )



def test_same_skill_name_for_two_users_and_isolation(temp_db):
    import sqlite3
    db = temp_db
    assert db.add_skill("a1", "shared-name", "A's", "A instructions", user_id="ua") is True
    assert db.add_skill("b1", "shared-name", "B's", "B instructions", user_id="ub") is True  # same name, other user
    with pytest.raises(sqlite3.IntegrityError):  # but not twice for one user
        db.add_skill("a2", "shared-name", "dup", "dup", user_id="ua")
    assert db.get_skill_by_name("shared-name", "ua")["id"] == "a1"
    assert db.get_skill_by_name("shared-name", "ub")["id"] == "b1"
    assert [s["id"] for s in db.get_all_skills("ua")] == ["a1"]
    assert db.get_skill("a1", "ub") is None


def test_foreign_skill_id_cannot_be_overwritten_or_deleted(temp_db):
    db = temp_db
    db.add_skill("own1", "owned-by-c", "mine", "mine", user_id="uc")
    assert db.add_skill("own1", "taken-over", "stolen", "stolen", user_id="ud") is False  # upsert onto a foreign id
    assert db.delete_skill("own1", "ud") is False
    skill = db.get_skill("own1", "uc")
    assert (skill["name"], skill["description"]) == ("owned-by-c", "mine")
    assert db.delete_skill("own1", "uc") is True


def test_an_empty_user_id_is_refused(temp_db):
    for call in (lambda: temp_db.get_all_skills(""), lambda: temp_db.get_skill("x", ""), lambda: temp_db.get_skill_by_name("x", None),
                 lambda: temp_db.delete_skill("x", ""), lambda: temp_db.add_skill("x", "n", "d", "i", user_id="")):
        with pytest.raises(ValueError):
            call()
