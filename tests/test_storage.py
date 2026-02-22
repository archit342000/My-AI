from backend.storage import init_db, save_chat, add_message, get_chat, delete_chat
import os
import time

def test_storage():
    if os.path.exists("./backend/chats.db"):
        os.remove("./backend/chats.db")

    init_db()

    print("Saving chat...")
    save_chat("test-id", "Test Chat", time.time(), True)

    print("Adding messages...")
    add_message("test-id", "user", "Hello")
    add_message("test-id", "assistant", "Hi there")

    print("Retrieving chat...")
    chat = get_chat("test-id")
    print(chat)

    assert chat['id'] == "test-id"
    assert len(chat['messages']) == 2
    assert chat['messages'][0]['content'] == "Hello"

    print("Deleting chat...")
    delete_chat("test-id")
    assert get_chat("test-id") is None

    print("Test Passed!")

if __name__ == "__main__":
    test_storage()
