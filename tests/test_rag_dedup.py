from backend.rag import MemoryRAG
import shutil
import os
import requests
from unittest.mock import patch, MagicMock
import hashlib

def test_rag_deduplication():
    # Setup clean test db
    test_db_path = "./tests/test_chroma_db_dedup"
    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

    with patch('requests.post') as mock_post:
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 768}]
        }
        mock_post.return_value = mock_response

        rag = MemoryRAG(persist_path=test_db_path, api_url="http://mock", embedding_model="mock")

        text = "This is a unique memory."

        # Add twice
        print("Adding memory first time...")
        rag.add_memory(text)
        print("Adding memory second time...")
        rag.add_memory(text)

        # Check collection count
        count = rag.collection.count()
        print(f"Collection count: {count}")

        assert count == 1, f"Expected 1 document, found {count}. Deduplication failed."

        # Verify ID is hash
        expected_id = hashlib.sha256(text.encode('utf-8')).hexdigest()
        stored = rag.collection.get(ids=[expected_id])
        assert stored['ids'][0] == expected_id

        print("Deduplication Test Passed!")

    if os.path.exists(test_db_path):
        shutil.rmtree(test_db_path)

if __name__ == "__main__":
    test_rag_deduplication()
