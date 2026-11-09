import pytest
from backend.database.wrapper.persona_ops import PersonaOperations
from backend.database.init_db import init_db

class TestDatabaseWrapper(PersonaOperations):
    pass

@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("backend.database.db_layer.DB_PATH", str(db_path))
    init_db()
    db = TestDatabaseWrapper()
    return db

def test_persona_crud(temp_db):
    # Create
    p1 = temp_db.create_persona("Test 1", "Content 1", user_id="u1")
    assert p1["name"] == "Test 1"
    assert p1["git_mode"] == 0
    
    p2 = temp_db.create_persona("Test 2", "Content 2", is_default=1, git_mode=1, user_id="u1")
    assert p2["is_default"] == 1
    assert p2["git_mode"] == 1
    
    # Get all
    personas = temp_db.get_all_personas(user_id="u1")
    assert len(personas) == 2
    assert personas[0]["git_mode"] == 1 or personas[1]["git_mode"] == 1
    
    # Get default
    default = temp_db.get_default_persona(user_id="u1")
    assert default["id"] == p2["id"]
    assert default["git_mode"] == 1
    
    # Update
    success = temp_db.update_persona(p1["id"], "Updated Test 1", "Updated Content", is_default=1, git_mode=1, user_id="u1")
    assert success
    
    # Check default swapped
    default = temp_db.get_default_persona(user_id="u1")
    assert default["id"] == p1["id"]
    assert default["git_mode"] == 1
    
    # Delete
    success = temp_db.delete_persona(p2["id"], user_id="u1")
    assert success
    assert len(temp_db.get_all_personas(user_id="u1")) == 1

def test_persona_agent_toggles(temp_db):
    # Create with toggles
    p = temp_db.create_persona("Agent Persona", "Prompt context", is_default=0, research_mode=0, file_system_mode=1, browsing_mode=1, git_mode=1, user_id="u1")
    assert p["research_mode"] == 0
    assert p["file_system_mode"] == 1
    assert p["browsing_mode"] == 1
    assert p["git_mode"] == 1

    # Fetch and check
    fetched = temp_db.get_persona(p["id"], user_id="u1")
    assert fetched["research_mode"] == 0
    assert fetched["file_system_mode"] == 1
    assert fetched["browsing_mode"] == 1
    assert fetched["git_mode"] == 1

    # Update toggles
    success = temp_db.update_persona(p["id"], "Agent Persona", "Prompt context", is_default=0, research_mode=0, file_system_mode=0, browsing_mode=1, git_mode=0, user_id="u1")
    assert success
    fetched = temp_db.get_persona(p["id"], user_id="u1")
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 1
    assert fetched["git_mode"] == 0

def test_persona_agent_constraints(temp_db):
    # Enforce research_mode overrides other agents on creation (but NOT git_mode which is independent)
    p = temp_db.create_persona("Research Only", "Context", is_default=0, research_mode=1, file_system_mode=1, browsing_mode=1, git_mode=1, user_id="u1")
    assert p["research_mode"] == 1
    assert p["file_system_mode"] == 0
    assert p["browsing_mode"] == 0
    assert p["git_mode"] == 1

    # Fetch and check
    fetched = temp_db.get_persona(p["id"], user_id="u1")
    assert fetched["research_mode"] == 1
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 0
    assert fetched["git_mode"] == 1

    # Enforce on update
    success = temp_db.update_persona(p["id"], "Research Only", "Context", is_default=0, research_mode=1, file_system_mode=1, browsing_mode=1, git_mode=0, user_id="u1")
    assert success
    fetched = temp_db.get_persona(p["id"], user_id="u1")
    assert fetched["research_mode"] == 1
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 0
    assert fetched["git_mode"] == 0


def test_persona_name_exists(temp_db):
    p1 = temp_db.create_persona("Dup Persona", "c1", user_id="u1")
    p2 = temp_db.create_persona("Other Persona", "c2", user_id="u1")
    assert temp_db.persona_name_exists("Dup Persona", user_id="u1") is True
    assert temp_db.persona_name_exists("  dup PERSONA ", user_id="u1") is True  # case and surrounding spaces
    assert temp_db.persona_name_exists("Unrelated", user_id="u1") is False
    assert temp_db.persona_name_exists("Dup Persona", exclude_id=p1["id"], user_id="u1") is False  # its own name
    assert temp_db.persona_name_exists("Dup Persona", exclude_id=p2["id"], user_id="u1") is True


def test_default_persona_is_per_user(temp_db):
    a1 = temp_db.create_persona("A default", "c", user_id="ua", is_default=1)
    b1 = temp_db.create_persona("B default", "c", user_id="ub", is_default=1)
    assert temp_db.get_default_persona("ua")["id"] == a1["id"]
    assert temp_db.get_default_persona("ub")["id"] == b1["id"]  # ub's default did not clear ua's
    a2 = temp_db.create_persona("A second", "c", user_id="ua", is_default=1)
    assert temp_db.get_default_persona("ua")["id"] == a2["id"]
    assert temp_db.get_default_persona("ub")["id"] == b1["id"]


def test_personas_are_isolated_between_users(temp_db):
    pa = temp_db.create_persona("Shared name", "A content", user_id="ua")
    temp_db.create_persona("Shared name", "B content", user_id="ub")  # two users may use one name
    assert [p["id"] for p in temp_db.get_all_personas("ua")] == [pa["id"]]
    assert temp_db.get_persona(pa["id"], "ub") is None
    assert temp_db.persona_name_exists("shared NAME", "ua") is True
    assert temp_db.persona_name_exists("Only A", "ub") is False
    assert temp_db.persona_name_exists("Shared name", "ua", exclude_id=pa["id"]) is False


def test_foreign_persona_cannot_be_updated_or_deleted_and_keeps_defaults(temp_db):
    pa = temp_db.create_persona("A", "c", user_id="ua", is_default=1)
    pb = temp_db.create_persona("B", "c", user_id="ub", is_default=1)
    # ub tries to update ua's default persona and make it their default: nothing changes, including ub's own default
    assert temp_db.update_persona(pa["id"], "hijacked", "x", user_id="ub", is_default=1) is False
    assert temp_db.delete_persona(pa["id"], user_id="ub") is False
    assert temp_db.get_persona(pa["id"], "ua")["name"] == "A"
    assert temp_db.get_default_persona("ua")["id"] == pa["id"]
    assert temp_db.get_default_persona("ub")["id"] == pb["id"]


def test_personas_refuse_an_empty_user_id(temp_db):
    for call in (lambda: temp_db.get_all_personas(""), lambda: temp_db.get_persona("x", ""), lambda: temp_db.get_default_persona(None),
                 lambda: temp_db.persona_name_exists("x", ""), lambda: temp_db.create_persona("n", "c", user_id=""),
                 lambda: temp_db.update_persona("i", "n", "c", user_id=""), lambda: temp_db.delete_persona("i", user_id="")):
        with pytest.raises(ValueError):
            call()

