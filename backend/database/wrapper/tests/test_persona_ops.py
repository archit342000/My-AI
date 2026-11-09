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
    p1 = temp_db.create_persona("Test 1", "Content 1")
    assert p1["name"] == "Test 1"
    assert p1["git_mode"] == 0
    
    p2 = temp_db.create_persona("Test 2", "Content 2", is_default=1, git_mode=1)
    assert p2["is_default"] == 1
    assert p2["git_mode"] == 1
    
    # Get all
    personas = temp_db.get_all_personas()
    assert len(personas) == 2
    assert personas[0]["git_mode"] == 1 or personas[1]["git_mode"] == 1
    
    # Get default
    default = temp_db.get_default_persona()
    assert default["id"] == p2["id"]
    assert default["git_mode"] == 1
    
    # Update
    success = temp_db.update_persona(p1["id"], "Updated Test 1", "Updated Content", is_default=1, git_mode=1)
    assert success
    
    # Check default swapped
    default = temp_db.get_default_persona()
    assert default["id"] == p1["id"]
    assert default["git_mode"] == 1
    
    # Delete
    success = temp_db.delete_persona(p2["id"])
    assert success
    assert len(temp_db.get_all_personas()) == 1

def test_persona_agent_toggles(temp_db):
    # Create with toggles
    p = temp_db.create_persona("Agent Persona", "Prompt context", is_default=0, research_mode=0, file_system_mode=1, browsing_mode=1, git_mode=1)
    assert p["research_mode"] == 0
    assert p["file_system_mode"] == 1
    assert p["browsing_mode"] == 1
    assert p["git_mode"] == 1

    # Fetch and check
    fetched = temp_db.get_persona(p["id"])
    assert fetched["research_mode"] == 0
    assert fetched["file_system_mode"] == 1
    assert fetched["browsing_mode"] == 1
    assert fetched["git_mode"] == 1

    # Update toggles
    success = temp_db.update_persona(p["id"], "Agent Persona", "Prompt context", is_default=0, research_mode=0, file_system_mode=0, browsing_mode=1, git_mode=0)
    assert success
    fetched = temp_db.get_persona(p["id"])
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 1
    assert fetched["git_mode"] == 0

def test_persona_agent_constraints(temp_db):
    # Enforce research_mode overrides other agents on creation (but NOT git_mode which is independent)
    p = temp_db.create_persona("Research Only", "Context", is_default=0, research_mode=1, file_system_mode=1, browsing_mode=1, git_mode=1)
    assert p["research_mode"] == 1
    assert p["file_system_mode"] == 0
    assert p["browsing_mode"] == 0
    assert p["git_mode"] == 1

    # Fetch and check
    fetched = temp_db.get_persona(p["id"])
    assert fetched["research_mode"] == 1
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 0
    assert fetched["git_mode"] == 1

    # Enforce on update
    success = temp_db.update_persona(p["id"], "Research Only", "Context", is_default=0, research_mode=1, file_system_mode=1, browsing_mode=1, git_mode=0)
    assert success
    fetched = temp_db.get_persona(p["id"])
    assert fetched["research_mode"] == 1
    assert fetched["file_system_mode"] == 0
    assert fetched["browsing_mode"] == 0
    assert fetched["git_mode"] == 0


def test_persona_name_exists(temp_db):
    p1 = temp_db.create_persona("Dup Persona", "c1")
    p2 = temp_db.create_persona("Other Persona", "c2")
    assert temp_db.persona_name_exists("Dup Persona") is True
    assert temp_db.persona_name_exists("  dup PERSONA ") is True  # case and surrounding spaces
    assert temp_db.persona_name_exists("Unrelated") is False
    assert temp_db.persona_name_exists("Dup Persona", exclude_id=p1["id"]) is False  # its own name
    assert temp_db.persona_name_exists("Dup Persona", exclude_id=p2["id"]) is True
