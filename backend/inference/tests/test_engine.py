import pytest
import threading
import time
import json
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch, MagicMock, AsyncMock
from backend.inference.engine import InferenceEngine
import multiprocessing

class MockLlamaCppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress logging

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode('utf-8'))
        
        if self.path in ['/v1/chat/completions', '/api/models/v1/chat/completions']:
            if payload.get('stream'):
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                
                chunks = [
                    {"choices": [{"delta": {"content": "<think>\nThinking..."}}]},
                    {"choices": [{"delta": {"content": "</think>\nHello "}}]},
                    {"choices": [{"delta": {"content": "World"}}]},
                    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "test_tool", "arguments": '{"a":1}'}}]}}]},
                    {"timings": {"prompt_n": 10}}
                ]
                for chunk in chunks:
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode('utf-8'))
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                resp = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "<think>\nThinking...\n</think>\nHello World",
                            "tool_calls": [{"id": "call_1", "function": {"name": "test_tool", "arguments": "{}"}}]
                        }
                    }],
                    "timings": {"prompt_n": 10}
                }
                self.wfile.write(json.dumps(resp).encode('utf-8'))
        
        elif self.path in ['/v1/embeddings', '/api/models/v1/embeddings']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            inputs = payload.get('input', [])
            if isinstance(inputs, str): inputs = [inputs]
            
            data = [{"embedding": [0.1, 0.2, 0.3]} for _ in inputs]
            resp = {"data": data}
            self.wfile.write(json.dumps(resp).encode('utf-8'))
            
        elif self.path == '/api/models/load':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        
        else:
            self.send_response(404)
            self.end_headers()

@pytest.fixture(scope="module")
def mock_server():
    server = HTTPServer(('127.0.0.1', 0), MockLlamaCppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()

@pytest.fixture
def engine(mock_server):
    # Reset singleton before test
    InferenceEngine._instance = None
    
    with patch('backend.config.AI_PROXY_URL', mock_server), \
         patch.dict('os.environ', {"AI_PROXY_URL": mock_server}):
         
         eng = InferenceEngine()
         yield eng
    
    InferenceEngine._instance = None


@pytest.fixture(autouse=True)
def mock_logger():
    with patch('backend.inference.engine.log_event'), \
         patch('backend.inference.engine.log_llm_call'), \
         patch('backend.inference.engine.log_embedding_call'):
         yield


@pytest.mark.anyio
async def test_engine_singleton(mock_server):
    InferenceEngine._instance = None
    with patch('backend.config.AI_PROXY_URL', mock_server), \
         patch.dict('os.environ', {"AI_PROXY_URL": mock_server}):
        eng1 = InferenceEngine()
        eng2 = InferenceEngine()
        assert eng1 is eng2

@pytest.mark.anyio
async def test_engine_start(engine):
    assert await engine.start() is True

@pytest.mark.anyio
async def test_engine_chat(engine):
    messages = [{"role": "user", "content": "Hi"}]
    res = await engine.chat(messages, model="test-model", chat_template_kwargs={"enable_thinking": True})
    assert res["choices"][0]["message"]["content"] == "<think>\nThinking...\n</think>\nHello World"

@pytest.mark.anyio
async def test_engine_chat_error(engine):
    with patch.object(engine, '_request', side_effect=Exception("API Error")):
        with pytest.raises(Exception, match="API Error"):
            await engine.chat([{"role": "user", "content": "Hi"}], model="test-model")

@pytest.mark.anyio
async def test_engine_stream(engine):
    messages = [{"role": "user", "content": "Hi"}]
    chunks = []
    async for chunk in engine.stream(messages, model="test-model", chat_template_kwargs={"enable_thinking": True}):
        chunks.append(chunk)
    
    assert len(chunks) == 5
    for chunk in chunks:
        assert chunk.startswith("data: ")
    # The logging block in finally happens, but we patched it out

@pytest.mark.anyio
async def test_engine_stream_error(engine):
    with patch('httpx.AsyncClient.stream', side_effect=Exception("Stream Error")):
        with pytest.raises(Exception, match="Stream Error"):
            async for _ in engine.stream([{"role": "user", "content": "Hi"}], model="test-model"):
                pass

@pytest.mark.anyio
async def test_engine_embed(engine):
    res = await engine.embed("Test input", model="test-embed")
    assert len(res) == 1
    assert res[0] == [0.1, 0.2, 0.3]
    
    res2 = await engine.embed(["Test 1", "Test 2"], model="test-embed")
    assert len(res2) == 2
    assert res2[0] == [0.1, 0.2, 0.3]
    assert res2[1] == [0.1, 0.2, 0.3]

@pytest.mark.anyio
async def test_engine_embed_error(engine):
    with patch.object(engine, '_request', side_effect=Exception("Embed Error")):
        with pytest.raises(Exception, match="Embed Error"):
            await engine.embed("Test input", model="test-embed")

def test_engine_embed_sync(engine):
    res = engine.embed_sync("Test input", model="test-embed")
    assert len(res) == 1
    assert res[0] == [0.1, 0.2, 0.3]

@pytest.mark.anyio
async def test_ensure_model_loaded(engine):
    # This will hit MockLlamaCppHandler's /api/models/load endpoint successfully
    await engine.ensure_model_loaded("test-model")
        
    # Error handling
    with patch('httpx.AsyncClient.request', side_effect=Exception("Load Error")), \
         patch('backend.inference.engine.log_event') as mock_log:
        await engine.ensure_model_loaded("test-model")
        mock_log.assert_called_with("ensure_model_loaded_error", {"error": "Load Error", "model": "test-model"})

@pytest.mark.anyio
async def test_request(engine):
    res = await engine._request("POST", f"{engine.proxy_url}/v1/chat/completions", {"stream": False}, 10.0)
    assert res.status_code == 200

def test_get_headers(engine):
    h = engine._get_headers()
    assert h["Content-Type"] == "application/json"

def test_normalize_messages(engine):
    messages = [
        {"role": "system", "content": "You are AI", "name": None},
        {"role": "user", "content": "Hello", "extra": "remove_me", "tool_calls": None},
        {"role": "event", "content": "ignored"},
        {"role": "assistant", "content": "Hi", "reasoning_content": "Thinking", "tool_calls": [{"index": 0}], "tool_call_id": None},
        {"role": "tool", "content": {"message": "Image attached", "screenshot_ref": "invalid_path", "mime_type": "image/jpeg"}},
        {"role": "tool", "content": "Pure text", "tool_call_id": "call_1"},
        {"role": "assistant", "content": "Done"}
    ]
    
    norm = engine._normalize_messages(messages)
    
    # event is skipped
    assert len(norm) == 6
    assert norm[0]["role"] == "system"
    assert "name" not in norm[0]
    assert "extra" not in norm[1]
    assert "tool_calls" not in norm[1]
    
    # Assistant reasoning woven
    assert norm[2]["role"] == "assistant"
    assert norm[2]["content"] == "Hi"
    assert norm[2]["reasoning_content"] == "Thinking"
    assert norm[2]["tool_calls"][0]["type"] == "function" # Enforced by normalization
    assert "tool_call_id" not in norm[2]
    
    # Invalid screenshot path results in fallback message
    assert norm[3]["role"] == "tool"
    assert norm[3]["content"] == "Image attached"
    
    # Pure text tool
    assert norm[4]["role"] == "tool"
    assert norm[4]["content"] == "Pure text"
    
    # Assistant no reasoning, no tools
    assert norm[5]["role"] == "assistant"
    assert norm[5]["content"] == "Done"
    assert "tool_calls" not in norm[5]

def test_normalize_messages_multimodal(engine):
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]}
    ]
    norm = engine._normalize_messages(messages)
    assert norm[0]["content"] == [{"type": "text", "text": "hello"}]
    
    # If not user, should dump JSON
    messages2 = [
        {"role": "system", "content": [{"type": "text", "text": "hello"}]}
    ]
    norm2 = engine._normalize_messages(messages2)
    assert norm2[0]["content"] == '[{"type": "text", "text": "hello"}]'

def test_reconstruct_raw_response(engine):
    # Test standard/Qwen model
    raw_standard = engine._reconstruct_raw_response(
        model="Qwen/Qwen2.5-72B-Instruct",
        content="Hello standard",
        reasoning="Standard thoughts",
        tool_calls=None
    )
    assert raw_standard == "<think>\nStandard thoughts\n</think>\nHello standard"

    # Test standard model with tool calls
    raw_standard_tc = engine._reconstruct_raw_response(
        model="Qwen/Qwen2.5-72B-Instruct",
        content="Hello tool",
        reasoning=None,
        tool_calls=[{"function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}]
    )
    assert raw_standard_tc == 'Hello tool\n<tool_call>{"name": "get_weather", "arguments": {"city": "Paris"}}</tool_call>'

    # Test Gemma model
    raw_gemma = engine._reconstruct_raw_response(
        model="Google/Gemma-2-9b-it",
        content="Hello gemma",
        reasoning="Gemma thoughts",
        tool_calls=[{"function": {"name": "get_weather", "arguments": '{"city": "Paris"}'}}]
    )
    assert raw_gemma == "<|channel>thought\nGemma thoughts\n<channel|>\nHello gemma\n<|tool_call>call:get_weather{\"city\": \"Paris\"}<tool_call|>"

@pytest.mark.anyio
async def test_chat_retry_reasoning_only(engine):
    # Mock responses: 1st is reasoning-only, 2nd is valid
    resp1 = MagicMock()
    resp1.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": "Thinking..."}}]
    }
    resp2 = MagicMock()
    resp2.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Hello", "reasoning_content": "Thinking..."}}]
    }
    
    with patch.object(engine, '_request', side_effect=[resp1, resp2]):
        with patch('backend.config.LLM_RETRY_COUNT', 3), \
             patch('backend.config.LLM_RETRY_DELAY', 0.01):
            res = await engine.chat([{"role": "user", "content": "Hi"}], model="test-model")
            assert res["choices"][0]["message"]["content"] == "Hello"
            assert engine._request.call_count == 2

@pytest.mark.anyio
async def test_chat_retry_invalid_tool_json(engine):
    # Mock responses: 1st has invalid tool JSON, 2nd is valid
    resp1 = MagicMock()
    resp1.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant", 
                "content": None, 
                "tool_calls": [{"function": {"name": "test", "arguments": 'not_json'}}] # Unsalvageable JSON
            }
        }]
    }
    resp2 = MagicMock()
    resp2.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant", 
                "content": None, 
                "tool_calls": [{"function": {"name": "test", "arguments": '{"a": 1}'}}]
            }
        }]
    }
    
    with patch.object(engine, '_request', side_effect=[resp1, resp2]):
        with patch('backend.config.LLM_RETRY_COUNT', 3), \
             patch('backend.config.LLM_RETRY_DELAY', 0.01):
            res = await engine.chat([{"role": "user", "content": "Hi"}], model="test-model")
            assert res["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'
            assert engine._request.call_count == 2

@pytest.mark.anyio
async def test_stream_retry_reasoning_only(engine):
    # Mock stream data
    # Stream 1: Only reasoning
    stream1_data = [
        'data: {"choices": [{"delta": {"reasoning_content": "Thinking..."}}]}',
        'data: [DONE]'
    ]
    # Stream 2: Valid content
    stream2_data = [
        'data: {"choices": [{"delta": {"content": "Hello"}}]}',
        'data: [DONE]'
    ]
    
    class MockStream:
        def __init__(self, data):
            self.data = data
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def aiter_lines(self):
            for line in self.data:
                yield line
        def raise_for_status(self): pass

    with patch('httpx.AsyncClient.stream', side_effect=[MockStream(stream1_data), MockStream(stream2_data)]):
        with patch('backend.config.LLM_RETRY_COUNT', 3), \
             patch('backend.config.LLM_RETRY_DELAY', 0.01):
            chunks = []
            async for chunk in engine.stream([{"role": "user", "content": "Hi"}], model="test-model"):
                chunks.append(chunk)
                
            assert any("Thinking..." in c for c in chunks)
            assert any("__redact__" in c for c in chunks)
            assert any("Hello" in c for c in chunks)
            notice = next(json.loads(c[6:])["message"] for c in chunks if "__redact__" in c)
            assert notice == "Checking the answer again…" and "..." not in notice

@pytest.mark.anyio
async def test_stream_retry_on_exception(engine):
    # Mock stream: 1st raises exception, 2nd is valid
    stream2_data = [
        'data: {"choices": [{"delta": {"content": "Recovered"}}]}',
        'data: [DONE]'
    ]
    
    class MockStream:
        def __init__(self, data):
            self.data = data
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def aiter_lines(self):
            for line in self.data:
                yield line
        def raise_for_status(self): pass

    with patch('httpx.AsyncClient.stream', side_effect=[Exception("Network Error"), MockStream(stream2_data)]):
        with patch('backend.config.LLM_RETRY_COUNT', 3), \
             patch('backend.config.LLM_RETRY_DELAY', 0.01):
            chunks = []
            async for chunk in engine.stream([{"role": "user", "content": "Hi"}], model="test-model"):
                chunks.append(chunk)
                
            assert any("__redact__" in c for c in chunks)
            assert any("Recovered" in c for c in chunks)
            notice = next(json.loads(c[6:])["message"] for c in chunks if "__redact__" in c)
            assert notice == "The model did not respond. Trying again…"  # fixed text: no exception text, no "..."
            assert "Network Error" not in notice


@pytest.mark.anyio
async def test_engine_chat_proxy_mode(engine):
    # Mock proxy-parsed response: reasoning_content is already populated and stripped
    proxy_response = MagicMock()
    proxy_response.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Hello World",
                "reasoning_content": "Thinking..."
            }
        }],
        "timings": {"prompt_n": 10}
    }
    
    with patch.object(engine, '_request', return_value=proxy_response):
        with patch.object(engine, 'proxy_url', "http://proxy-mock"):
            res = await engine.chat([{"role": "user", "content": "Hi"}], model="test-model")
            
            # Assert that client preserves reasoning_content exactly as returned by proxy without double parsing
            assert res["choices"][0]["message"]["content"] == "Hello World"
            assert res["choices"][0]["message"]["reasoning_content"] == "Thinking..."

@pytest.mark.anyio
async def test_engine_stream_proxy_mode(engine):
    from unittest.mock import AsyncMock
    # Mock proxy-parsed stream responses
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        lines = [
            'data: {"choices": [{"delta": {"reasoning_content": "Thinking..."}}]}',
            'data: {"choices": [{"delta": {"content": "Hello World"}}]}',
            'data: [DONE]'
        ]
        for line in lines:
            yield line
            
    mock_resp.aiter_lines = mock_aiter_lines
    
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock()
    
    with patch('httpx.AsyncClient.stream', return_value=mock_context):
        with patch.object(engine, 'proxy_url', "http://proxy-mock"):
            chunks = []
            async for chunk in engine.stream([{"role": "user", "content": "Hi"}], model="test-model"):
                chunks.append(chunk)
                
            assert len(chunks) == 2
            assert "reasoning_content" in chunks[0]
            assert "content" in chunks[1]

def test_log_llm_call_exception_resilience(engine):
    # Mock log_llm_call to raise an exception
    with patch('backend.inference.engine.log_llm_call', side_effect=Exception("Database lock error")), \
         patch('backend.inference.engine.logger.warning') as mock_warn:
         
         # Call _log_llm_call: it should handle exception and log warning
         engine._log_llm_call(
             payload={},
             response_text="Hello",
             model="test",
             chat_id="chat_1",
             duration=1.0,
             call_type="test"
         )
         
         mock_warn.assert_called_once()
         assert "Failed to log LLM call" in mock_warn.call_args[0][0]

def test_salvage_json_arguments(engine):
    # Test valid JSON passes through unchanged
    assert engine._salvage_json_arguments('{"a": 1}') == '{"a": 1}'
    assert engine._salvage_json_arguments('{}') == '{}'
    
    # Test unquoted keys are repaired
    assert engine._salvage_json_arguments('{a: 1}') == '{"a": 1}'
    assert engine._salvage_json_arguments('{a: "hello", b: 2}') == '{"a": "hello", "b": 2}'
    
    # Test trailing commas in dicts/arrays are stripped
    assert engine._salvage_json_arguments('{"a": 1,}') == '{"a": 1}'
    assert engine._salvage_json_arguments('[1, 2, ]') == '[1, 2]'
    
    # Test auto-closing unbalanced curly braces
    assert engine._salvage_json_arguments('{"a": 1') == '{"a": 1}'
    assert engine._salvage_json_arguments('{"a": {"b": 2') == '{"a": {"b": 2}}'
    
    # Test single-quoted / Python dictionary parsing
    assert json.loads(engine._salvage_json_arguments("{'a': 1, 'b': 'val'}")) == {"a": 1, "b": "val"}
    
    # Test unclosed double quotes inside string values
    assert json.loads(engine._salvage_json_arguments('{"a": "hello')) == {"a": "hello"}
    assert json.loads(engine._salvage_json_arguments('{"a": "hello", "b": "val')) == {"a": "hello", "b": "val"}
    
    # Test invalid formatting that cannot be saved returns None
    assert engine._salvage_json_arguments('not_json') is None

def test_is_generation_valid(engine):
    # Valid content
    is_valid, _ = engine._is_generation_valid("Hello world", None)
    assert is_valid
    
    # Invalid empty content
    is_valid, _ = engine._is_generation_valid("", None)
    assert not is_valid
    is_valid, _ = engine._is_generation_valid("   ", None)
    assert not is_valid

    # Valid tool calls
    valid_tc = [{"function": {"name": "test_tool", "arguments": '{"test": 123}'}}]
    is_valid, repaired = engine._is_generation_valid("", valid_tc)
    assert is_valid
    assert repaired == valid_tc

    # Invalid tool calls (JSON decode error)
    invalid_tc = [{"function": {"name": "test_tool", "arguments": "{invalid json}"}}]
    is_valid, _ = engine._is_generation_valid("", invalid_tc)
    assert not is_valid

    # Tool call with thought token in name
    is_valid, _ = engine._is_generation_valid("", [{"function": {"name": "test_<think>_tool", "arguments": '{"test": 123}'}}])
    assert not is_valid
    
    # Tool call with thought token in arguments
    is_valid, _ = engine._is_generation_valid("", [{"function": {"name": "test_tool", "arguments": '{"test": "<think>some thought</think>"}'}}])
    assert not is_valid
    
    # Tool call with tool call token in arguments
    is_valid, _ = engine._is_generation_valid("", [{"function": {"name": "test_tool", "arguments": '{"test": "<|tool_call>call:other_tool{}<tool_call|>"}'}}])
    assert not is_valid

    # Test JSON repair and purity
    repairable_tc = [{"function": {"name": "test_tool", "arguments": '{"arg": "val'}}]
    is_valid, repaired = engine._is_generation_valid("", repairable_tc)
    assert is_valid
    assert repaired is not None
    assert repaired[0]["function"]["arguments"] == '{"arg": "val"}'
    assert repairable_tc[0]["function"]["arguments"] == '{"arg": "val'  # check purity (no mutation)


@pytest.mark.anyio
async def test_engine_chat_gemma4_tool_call_parser(engine):
    with patch.object(engine, '_request') as mock_request:
        mock_request.return_value = MagicMock(status_code=200)
        mock_request.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello",
                }
            }]
        }
        await engine.chat([{"role": "user", "content": "Hi"}], model="Google/Gemma4-26B-A4B-it")
        mock_request.assert_called_once()
        _, _, payload, _ = mock_request.call_args[0]
        assert payload.get("tool_call_parser") == "gemma4"


@pytest.mark.anyio
async def test_engine_stream_gemma4_tool_call_parser(engine):
    mock_context = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
        yield 'data: [DONE]'
        
    mock_resp.aiter_lines = mock_aiter_lines
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock()
    
    with patch('httpx.AsyncClient.stream', return_value=mock_context) as mock_stream:
        messages = [{"role": "user", "content": "Hi"}]
        async for _ in engine.stream(messages, model="Google/Gemma4-26B-A4B-it"):
            pass
        mock_stream.assert_called_once()
        kwargs = mock_stream.call_args[1]
        assert kwargs.get("json", {}).get("tool_call_parser") == "gemma4"


def test_is_gemma4_model(engine):
    # Matches specific name in config
    assert engine._is_gemma4_model("Google/Gemma4-26B-A4B-it")
    assert engine._is_gemma4_model("google/gemma4-26b-a4b-it")
    
    # Non-matching (fallbacks and tokenizer names are now rejected)
    assert not engine._is_gemma4_model("google/gemma-4-26B-A4B-it")
    assert not engine._is_gemma4_model("gemma-4")
    assert not engine._is_gemma4_model("gemma4")
    assert not engine._is_gemma4_model("qwen2.5-instruct")
    assert not engine._is_gemma4_model("")
    assert not engine._is_gemma4_model(None)


@pytest.mark.anyio
async def test_stream_none_values(engine):
    mock_context = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    
    async def mock_aiter_lines():
        # First chunk has content/reasoning_content/tool_calls as None
        yield 'data: {"choices": [{"delta": {"content": null, "reasoning_content": null, "tool_calls": null}}]}'
        # Second chunk has valid content
        yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
        yield 'data: [DONE]'
        
    mock_resp.aiter_lines = mock_aiter_lines
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock()
    
    with patch('httpx.AsyncClient.stream', return_value=mock_context) as mock_stream:
        messages = [{"role": "user", "content": "Hi"}]
        chunks = []
        async for chunk in engine.stream(messages, model="test-model"):
            chunks.append(chunk)
        
        mock_stream.assert_called_once()
        assert any("Hello" in c for c in chunks)





