import unittest
import os
import json
import time
import sys
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from backend.task_manager import task_manager, TASKS_DIR, LOGS_DIR

class TestResumeDeepResearch(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.chat_id = "test_resume_chat_id"
        self.task_file = os.path.join(TASKS_DIR, f"{self.chat_id}.json")
        self.log_file = os.path.join(LOGS_DIR, f"{self.chat_id}.log")

        # Ensure directories exist
        os.makedirs(TASKS_DIR, exist_ok=True)
        os.makedirs(LOGS_DIR, exist_ok=True)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.task_file):
            os.remove(self.task_file)
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

        # Clear task manager state
        if self.chat_id in task_manager.active_queues:
            del task_manager.active_queues[self.chat_id]

    def test_resume_stream_endpoint(self):
        """Test that the /events endpoint streams data from an existing log file."""

        # 1. Simulate a running task
        task_data = {
            "chat_id": self.chat_id,
            "status": "running",
            "model": "test-model",
            "messages": []
        }
        with open(self.task_file, "w") as f:
            json.dump(task_data, f)

        # 2. Simulate some log data
        test_chunks = [
            {"type": "chunk", "data": "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n", "index": 1},
            {"type": "chunk", "data": "data: {\"choices\": [{\"delta\": {\"content\": \" world\"}}]}\n\n", "index": 2},
            # Simulate a "done" signal in the log (though in a real running task it might not be there yet)
            # For this test, we want to see if it reads the file.
            # task_manager.stream_task reads file then waits on queue.
        ]

        with open(self.log_file, "w") as f:
            for chunk in test_chunks:
                f.write(json.dumps(chunk) + "\n")

        # 3. Call the endpoint
        # We need to mock the queue waiting part of stream_task or it will hang forever
        # waiting for new chunks if the task is "running".
        # However, stream_task yields from file first.
        # Let's test that we get the file content.

        # Since stream_task blocks on the queue while status is "running",
        # we'll mark the task as "completed" right after we request it?
        # No, that's a race condition.

        # Instead, we can append a "done" chunk to the queue from a separate thread,
        # OR we can just rely on the fact that the test client might consume the stream.
        # But stream_task assumes an infinite loop for the queue.

        # Let's simply simulate that the task finishes *while* we are reading.
        # We can update the task file to "completed" after a short delay?
        # A simpler way for a unit test is to just check if we get the initial chunks.

        response = self.client.get(f'/api/chats/{self.chat_id}/events')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/event-stream')

        # We read the first few chunks. The generator won't exit, but we can verify the start.
        # Note: integration testing streaming responses can be tricky with blocking generators.
        # We will iterate manually.

        chunk_count = 0
        received_content = ""

        # To avoid hanging, we'll mark the task as completed in the file *before* iterating?
        # If we do that, stream_task might return early.
        # Let's update the task status to completed so stream_task exits the loop
        task_data["status"] = "completed"
        with open(self.task_file, "w") as f:
            json.dump(task_data, f)

        # Re-request to avoid the hang (since the first request generator is already instantiated with old state?)
        # Actually stream_task checks the file status *before* entering the queue loop?
        # No, it checks inside.

        # Let's write the test such that we verify the logic of `stream_task` directly
        # rather than the full HTTP stack to have more control, or accept that we modify files.

        # Re-instantiate the generator by calling the endpoint logic directly or just trust the client
        # will yield what's available.

        # Let's try consuming the response iterator.
        iterator = response.response

        try:
            # First chunk
            c1 = next(iterator).decode('utf-8')
            if "Hello" in c1:
                chunk_count += 1

            # Second chunk
            c2 = next(iterator).decode('utf-8')
            if "world" in c2:
                chunk_count += 1

        except StopIteration:
            pass

        self.assertGreater(chunk_count, 0, "Should have received at least one chunk from the log file")

if __name__ == '__main__':
    unittest.main()
