import json
from app import chat_completions
from flask import Flask, request
from unittest.mock import patch, MagicMock

app = Flask(__name__)

def test_injection():
    # Mock request data
    mock_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]

    # Mock RAG retrieval
    with patch('app.rag.retrieve_context') as mock_retrieve:
        mock_retrieve.return_value = "Remember: User likes apples."

        # Mock requests.post to avoid actual network call
        with patch('requests.post') as mock_post:
            mock_post.return_value.iter_lines.return_value = [b"data: [DONE]"]

            with app.test_request_context(
                '/v1/chat/completions',
                method='POST',
                json={
                    "messages": mock_messages,
                    "memoryMode": True,
                    "chatId": "test"
                }
            ):
                response = chat_completions()
                try:
                    list(response.response)
                except Exception as e:
                    print("Generator error:", e)

                print("Mock Called:", mock_post.called)
                if mock_post.called:
                    args, kwargs = mock_post.call_args
                    print("KWARGS keys:", kwargs.keys())
                    if 'json' in kwargs:
                        sent_messages = kwargs['json']['messages']
                        print("Sent Messages:")
                        print(json.dumps(sent_messages, indent=2))

                        # Assertions
                        assert len(sent_messages) == 3
                        assert sent_messages[0]['content'] == "You are a helpful assistant."
                        assert sent_messages[1]['role'] == "system"
                        assert "<memory_context>" in sent_messages[1]['content']
                        assert "User likes apples" in sent_messages[1]['content']
                        assert sent_messages[2]['content'] == "Hello"

                        print("\nTest Passed: Memory injected as separate system message.")
                    else:
                        print("JSON arg not found in kwargs")

if __name__ == "__main__":
    test_injection()
