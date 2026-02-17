from backend.rag import MemoryRAG
import shutil
import os
import requests
from unittest.mock import patch, MagicMock

def test_rag_mocked():
    # Setup clean test db
    test_db_path = "./tests/test_chroma_db_mock"
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

    # Mock requests.post
    with patch('requests.post') as mock_post:
        # Mock response for embedding
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mocking 384 dimensions (standard small model) or whatever Chroma expects
        # Chroma default is 384. gemma-embedding-300m might be different (e.g. 768 or 256).
        # But Chroma doesn't enforce dimension on collection creation unless specified?
        # Actually it infers from first addition.
        dummy_embedding = [0.1] * 768

        mock_response.json.return_value = {
            "data": [
                {"embedding": dummy_embedding}
            ]
        }
        mock_post.return_value = mock_response

        rag = MemoryRAG(persist_path=test_db_path, api_url="http://mock-url", embedding_model="mock-model")

        # Test Addition
        print("Adding memory (mocked)...")
        rag.add_memory("The user's name is Jules.", {"source": "test"})

        # Verify call
        mock_post.assert_called()
        args, kwargs = mock_post.call_args
        assert kwargs['json']['model'] == "mock-model"
        assert kwargs['json']['input'] == ["The user's name is Jules."]

        # Test Retrieval
        # For retrieval to work with Chroma, we need to embed the query too.
        # The mock will handle it.

        # However, since we just added dummy vectors that are identical,
        # retrieval based on similarity might be tricky if everything is identical.
        # But we just want to ensure the code path works.

        print("Retrieving context (mocked)...")
        context = rag.retrieve_context("What is the user's name?")
        print(f"Context retrieved: {context}")

        # Since the embedding for query and doc are identical (0.1, ...), distance is 0.
        # So it should retrieve it.
        assert "Jules" in context
        print("Test Passed!")

    # Cleanup
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

if __name__ == "__main__":
    test_rag_mocked()
