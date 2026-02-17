from backend.rag import MemoryRAG
import shutil
import os

def test_rag():
    # Setup clean test db
    test_db_path = "./tests/test_chroma_db"
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

    rag = MemoryRAG(persist_path=test_db_path)

    # Test Addition
    print("Adding memory...")
    rag.add_memory("The user's name is Jules.", {"source": "test"})
    rag.add_memory("The user likes python programming.", {"source": "test"})

    # Test Retrieval
    print("Retrieving context...")
    context = rag.retrieve_context("What is the user's name?")
    print(f"Context retrieved: {context}")

    assert "Jules" in context
    print("Test Passed!")

    # Cleanup
    shutil.rmtree(test_db_path)

if __name__ == "__main__":
    test_rag()
