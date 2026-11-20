import httpx
import json
import time
import asyncio
import multiprocessing
import os
import logging
import re
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import config
from logging_utils import log_llm_call, log_event, log_embedding_call
from parsers import get_parser_for_model, StreamInterceptor

logger = logging.getLogger(__name__)

class AsyncMPSemaphore:
    """
    A wrapper to make multiprocessing.Semaphore async-friendly.
    Enables sharing a lock across multiple OS processes (e.g. gunicorn workers)
    without blocking the asyncio event loop.
    """
    def __init__(self, sem: multiprocessing.Semaphore):
        self.sem = sem

    async def __aenter__(self):
        await asyncio.to_thread(self.sem.acquire)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.to_thread(self.sem.release)

class InferenceEngine:
    """
    Unified caller for LLM inference (chat completions) and embeddings.
    Abstracts away configuration and credentials, exposing a clean interface.
    """
    
    _instance = None
    _mp_sem = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InferenceEngine, cls).__new__(cls)
            
            if cls._mp_sem is None:
                cls._mp_sem = multiprocessing.Semaphore(config.INFERENCE_PARALLELISM)
            
            cls._instance._lock = AsyncMPSemaphore(cls._mp_sem)
            
            cls._instance.ai_url = config.AI_URL.rstrip("/") if config.AI_URL else ""
            cls._instance.ai_api_key = config.AI_API_KEY
            cls._instance.embedding_url = config.EMBEDDING_URL.rstrip("/") if config.EMBEDDING_URL else ""
            cls._instance.embedding_api_key = config.EMBEDDING_API_KEY
            
            cls._instance.timeout_llm = config.TIMEOUT_LLM_ASYNC or 120.0
            cls._instance.timeout_embedding = config.TIMEOUT_EMBEDDING
            
            log_event("inference_engine_initialized", {"parallelism": config.INFERENCE_PARALLELISM})
        return cls._instance

    def __init__(self):
        pass

    async def start(self):
        log_event("inference_engine_started", {"status": "ready"})
        return True

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        chat_id: Optional[str] = None,
        chat_template_kwargs: Optional[Dict[str, Any]] = None,
        **params
    ) -> Dict[str, Any]:
        """
        Executes a standard, blocking chat completion request with retry logic.
        """
        attempts = 0
        max_attempts = config.LLM_RETRY_COUNT

        while attempts < max_attempts:
            attempts += 1
            async with self._lock:
                await self.ensure_model_loaded(model, self.ai_url, self.ai_api_key, "llm")
                
                start_time = time.time()
                endpoint = f"{self.ai_url}/v1/chat/completions"
                
                payload = {
                    "model": model,
                    "messages": self._normalize_messages(messages, model),
                    "stream": False,
                    **params
                }
                
                if self._is_gemma4_model(model):
                    payload["tool_call_parser"] = "gemma4"
                
                if chat_template_kwargs:
                    payload["chat_template_kwargs"] = chat_template_kwargs

                try:
                    response = await self._request("POST", endpoint, self.ai_api_key, payload, self.timeout_llm)
                    data = response.json()
                    
                    msg = data.get("choices", [{}])[0].get("message", {})
                    
                    raw_content = msg.get("content", "") or ""
                    if raw_content:
                        parser_config = get_parser_for_model(model)
                        interceptor = StreamInterceptor(parser_config)
                        try:
                            c_emit, r_emit, tc_emit = interceptor.process_chunk(raw_content)
                            c_flush, r_flush, tc_flush = interceptor.flush()
                            
                            msg["content"] = c_emit + c_flush
                            msg["reasoning_content"] = r_emit + r_flush
                            
                            parsed_tc = tc_emit + tc_flush
                            if parsed_tc:
                                if "tool_calls" not in msg or not msg["tool_calls"]:
                                    msg["tool_calls"] = parsed_tc
                                else:
                                    msg["tool_calls"].extend(parsed_tc)
                        except ValueError as e:
                            if attempts < max_attempts:
                                log_event("inference_retry", {
                                    "reason": f"malformed_tool_call: {str(e)}", 
                                    "attempt": attempts, 
                                    "chat_id": chat_id,
                                })
                                await asyncio.sleep(config.LLM_RETRY_DELAY)
                                continue
                            else:
                                raise
                        
                    content = msg.get("content") or ""
                    reasoning = msg.get("reasoning_content") or ""
                    tool_calls = msg.get("tool_calls")
                    
                    if not self._is_generation_valid(content, tool_calls):
                        if attempts < max_attempts:
                            log_event("inference_retry", {
                                "reason": "invalid_generation", 
                                "attempt": attempts, 
                                "chat_id": chat_id,
                                "has_reasoning": bool(reasoning)
                            })
                            await asyncio.sleep(config.LLM_RETRY_DELAY)
                            continue

                    final_log_text = ""
                    if reasoning:
                        final_log_text += f"[Reasoning]\n{reasoning}\n[Content]\n"
                    final_log_text += content
                    
                    self._log_llm_call(
                        payload=payload, 
                        response_text=final_log_text, 
                        model=model, 
                        chat_id=chat_id, 
                        duration=time.time() - start_time, 
                        call_type="engine_blocking",
                        timings=data.get("timings"),
                        tool_calls=tool_calls
                    )
                    
                    return data
                except Exception as e:
                    if attempts < max_attempts:
                        log_event("inference_chat_retry_error", {"error": str(e), "attempt": attempts, "chat_id": chat_id})
                        await asyncio.sleep(config.LLM_RETRY_DELAY)
                        continue
                    log_event("inference_chat_error", {"error": str(e), "chat_id": chat_id})
                    raise

    async def stream(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        chat_id: Optional[str] = None,
        chat_template_kwargs: Optional[Dict[str, Any]] = None,
        **params
    ) -> AsyncGenerator[str, None]:
        """
        Executes a streaming chat completion request with retry logic.
        """
        attempts = 0
        max_attempts = config.LLM_RETRY_COUNT
        
        full_content = ""
        full_reasoning = ""
        tool_calls = {}
        sorted_tool_calls = None
        timings = None
        start_time = time.time()
        payload = {}

        while attempts < max_attempts:
            attempts += 1
            full_content = ""
            full_reasoning = ""
            tool_calls = {}
            sorted_tool_calls = None
            timings = None
            start_time = time.time()
            
            async with self._lock:
                await self.ensure_model_loaded(model, self.ai_url, self.ai_api_key, "llm")
                
                parser_config = get_parser_for_model(model)
                interceptor = StreamInterceptor(parser_config)
                
                endpoint = f"{self.ai_url}/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": self._normalize_messages(messages, model),
                    "stream": True,
                    **params
                }
                
                if self._is_gemma4_model(model):
                    payload["tool_call_parser"] = "gemma4"
                
                if chat_template_kwargs:
                    payload["chat_template_kwargs"] = chat_template_kwargs
                
                try:
                    headers = self._get_headers(self.ai_api_key)
                    timeout = httpx.Timeout(self.timeout_llm, read=config.TIMEOUT_LLM_STREAM_READ)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                            response.raise_for_status()
                            async for line in response.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                
                                if line == "data: [DONE]":
                                    c_flush, r_flush, tc_flush = interceptor.flush()
                                    if c_flush or r_flush or tc_flush:
                                        flush_chunk = {"choices": [{"delta": {}}]}
                                        if c_flush:
                                            flush_chunk["choices"][0]["delta"]["content"] = c_flush
                                            full_content += c_flush
                                        if r_flush:
                                            flush_chunk["choices"][0]["delta"]["reasoning_content"] = r_flush
                                            full_reasoning += r_flush
                                        if tc_flush:
                                            flush_chunk["choices"][0]["delta"]["tool_calls"] = tc_flush
                                            for tc in tc_flush:
                                                idx = tc.get("index", 0)
                                                tool_calls[idx] = tc
                                        yield f"data: {json.dumps(flush_chunk)}"
                                    yield "data: [DONE]"
                                    break
                                
                                try:
                                    chunk = json.loads(line[6:])
                                    if "timings" in chunk:
                                        timings = chunk["timings"]
                                        
                                    choices = chunk.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        proxy_extracted = False
                                        
                                        raw_content = delta.get("content", "")
                                        if raw_content:
                                            c_emit, r_emit, tc_emit = interceptor.process_chunk(raw_content)
                                            if "content" in delta:
                                                del delta["content"]
                                                
                                            if c_emit:
                                                delta["content"] = c_emit
                                                full_content += c_emit
                                            if r_emit:
                                                delta["reasoning_content"] = r_emit
                                                full_reasoning += r_emit
                                            if tc_emit:
                                                delta["tool_calls"] = tc_emit
                                                for tc in tc_emit:
                                                    idx = tc.get("index", 0)
                                                    tool_calls[idx] = tc
                                                proxy_extracted = True
                                                
                                        if "tool_calls" in delta:
                                            if interceptor.in_reasoning_block:
                                                del delta["tool_calls"]
                                            elif not proxy_extracted:
                                                for tc_delta in delta["tool_calls"]:
                                                    idx = tc_delta.get("index", 0)
                                                    if idx not in tool_calls:
                                                        tool_calls[idx] = tc_delta
                                                    else:
                                                        if "function" in tc_delta and "arguments" in tc_delta["function"]:
                                                            if "function" not in tool_calls[idx]: tool_calls[idx]["function"] = {"arguments": ""}
                                                            tool_calls[idx]["function"]["arguments"] += tc_delta["function"]["arguments"] or ""
                                         
                                        line = f"data: {json.dumps(chunk)}"
                                except ValueError as e:
                                    raise e
                                except Exception:
                                    pass
                                    
                                yield line
                    
                    sorted_tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())] if tool_calls else None
                    if not self._is_generation_valid(full_content, sorted_tool_calls):
                        if attempts < max_attempts:
                            log_event("inference_stream_retry", {
                                "reason": "invalid_generation", 
                                "attempt": attempts, 
                                "chat_id": chat_id
                            })
                            yield f"data: {json.dumps({'__redact__': True, 'message': 'Checking the answer again…'})}\n\n"
                            await asyncio.sleep(config.LLM_RETRY_DELAY)
                            continue
                    break

                except Exception as e:
                    if attempts < max_attempts:
                        log_event("inference_stream_retry_error", {"error": str(e), "attempt": attempts, "chat_id": chat_id})
                        yield f"data: {json.dumps({'__redact__': True, 'message': 'The model did not respond. Trying again…'})}\n\n"
                        await asyncio.sleep(config.LLM_RETRY_DELAY)
                        continue
                    log_event("inference_stream_error", {"error": str(e), "chat_id": chat_id})
                    raise
                finally:
                    if attempts >= max_attempts or self._is_generation_valid(full_content, sorted_tool_calls):
                        final_log_text = ""
                        if full_reasoning:
                            final_log_text += f"[Reasoning]\n{full_reasoning}\n[Content]\n"
                        final_log_text += full_content
                        
                        self._log_llm_call(
                            payload=payload, 
                            response_text=final_log_text, 
                            model=model, 
                            chat_id=chat_id, 
                            duration=time.time() - start_time, 
                            call_type="engine_stream",
                            timings=timings,
                            tool_calls=sorted_tool_calls
                        )

    def _salvage_json_arguments(self, args_str: str) -> Optional[str]:
        args_str = args_str.strip()
        if not args_str:
            return "{}"
            
        try:
            json.loads(args_str)
            return args_str
        except Exception:
            pass
            
        # Try python/single-quoted literals parsing first
        try:
            import ast
            parsed = ast.literal_eval(args_str)
            if isinstance(parsed, dict):
                return json.dumps(parsed)
        except Exception:
            pass
            
        # Try simple repairs
        repaired = args_str
        
        # 1. Auto-close unclosed double quote string literals
        unescaped_quotes = len(re.findall(r'(?<!\\)"', repaired))
        if unescaped_quotes % 2 == 1:
            repaired += '"'
        
        # 2. Wrap unquoted identifier keys in double quotes
        repaired = re.sub(r'(?<!["\'a-zA-Z0-9_-])([a-zA-Z0-9_-]+)(?!["\'a-zA-Z0-9_-])\s*:', r'"\1":', repaired)
        
        # 3. Remove trailing commas before closing braces/brackets
        repaired = re.sub(r',\s*(?=[\]}])', '', repaired)
        
        # 4. Auto-close unbalanced curly braces
        if repaired.startswith("{"):
            open_braces = repaired.count('{')
            close_braces = repaired.count('}')
            if open_braces > close_braces:
                repaired += "}" * (open_braces - close_braces)
                
        try:
            json.loads(repaired)
            return repaired
        except Exception:
            # Try ast.literal_eval on repaired string as a last resort
            try:
                import ast
                parsed = ast.literal_eval(repaired)
                if isinstance(parsed, dict):
                    return json.dumps(parsed)
            except Exception:
                pass
            return None

    def _is_generation_valid(self, content: str, tool_calls: Optional[List[Dict[str, Any]]]) -> bool:
        has_content = content and content.strip()
        has_tool_calls = tool_calls and len(tool_calls) > 0
        
        if not has_content and not has_tool_calls:
            return False
            
        if has_tool_calls:
            forbidden_tokens = [
                "<think>",
                "</think>",
                "<|channel>",
                "<channel|>",
                "<|tool_call>",
                "<tool_call|>",
                "<tool_call>",
                "</tool_call>"
            ]
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name") or ""
                args_str = func.get("arguments") or ""
                
                # Reject tool calls containing special thought or tool call tokens
                for token in forbidden_tokens:
                    if token in name or token in args_str:
                        return False
                
                if args_str:
                    try:
                        json.loads(args_str)
                    except json.JSONDecodeError:
                        repaired = self._salvage_json_arguments(args_str)
                        if repaired is not None:
                            func["arguments"] = repaired
                        else:
                            return False
        
        return True

    async def embed(
        self, 
        input: Union[str, List[str]], 
        model: str,
        chat_id: str = None,
        **params
    ) -> List[List[float]]:
        """
        Executes an embedding request.
        """
        async with self._lock:
            await self.ensure_model_loaded(model, self.embedding_url, self.embedding_api_key, "embedding")
            
            endpoint = f"{self.embedding_url}/v1/embeddings"
            payload = {
                "model": model,
                "input": [input] if isinstance(input, str) else input,
                **params
            }

            start_time = time.time()
            try:
                response = await self._request("POST", endpoint, self.embedding_api_key, payload, self.timeout_embedding)
                data = response.json()
                embeddings = [item["embedding"] for item in data.get("data", [])]
                
                try:
                    summary_data = {
                        "count": len(embeddings),
                        "dimensions": len(embeddings[0]) if embeddings else 0,
                        "model": model
                    }
                    log_embedding_call(
                        payload=payload,
                        response_data=summary_data,
                        model=model,
                        chat_id=chat_id,
                        duration_s=time.time() - start_time
                    )
                except Exception as e:
                    logger.warning(f"Failed to log embedding call: {e}")
                    
                return embeddings
            except Exception as e:
                log_event("inference_embed_error", {"error": str(e), "chat_id": chat_id})
                raise

    async def ensure_model_loaded(self, model_name: str, base_url: str, api_key: str, category: str):
        """
        Confirms if a model is loaded on a specific server.
        """
        if not base_url:
            return

        try:
            from lifecycle import ensure_model_loaded as lifecycle_ensure_loaded
            await lifecycle_ensure_loaded(model_name, base_url, api_key, category, timeout=self.timeout_llm)
        except Exception as e:
            log_event("ensure_model_loaded_error", {
                "error": str(e), 
                "model": model_name,
                "category": category,
                "server": base_url
            })

    async def _request(self, method: str, url: str, api_key: str, payload: dict, timeout: float) -> httpx.Response:
        headers = self._get_headers(api_key)
        async with httpx.AsyncClient(timeout=timeout) as client:
            kwargs = {"json": payload} if payload is not None else {}
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _normalize_messages(self, messages: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
        """
        Normalizes roles, tool structures, and formatting to ensure compatibility.
        """
        normalized = []
        allowed_roles = ["system", "user", "assistant", "tool"]
        
        for msg in messages:
            m = dict(msg)
            role = m.get("role")
            
            if role not in allowed_roles:
                continue
            
            content = m.get("content")
            if isinstance(content, (list, dict)):
                is_multimodal = (
                    isinstance(content, list) and 
                    len(content) > 0 and 
                    all(isinstance(item, dict) and "type" in item for item in content)
                )
                if not is_multimodal or role != "user":
                    m["content"] = json.dumps(content)

            if role == "assistant":
                tcs = m.get("tool_calls")
                if isinstance(tcs, list) and len(tcs) > 0:
                    for tc in tcs:
                        if isinstance(tc, dict): tc["type"] = "function"
                    m["tool_calls"] = tcs
                else:
                    m.pop("tool_calls", None)
                
                # Fold reasoning_content into content using model-specific tags
                reasoning = m.pop("reasoning_content", None)
                content_val = m.get("content") or ""
                if reasoning:
                    parser = get_parser_for_model(model)
                    start_tag = parser.start_tags[0] if parser.start_tags else None
                    end_tag = parser.end_tags[0] if parser.end_tags else None
                    if start_tag and end_tag:
                        m["content"] = f"{start_tag}{reasoning}{end_tag}{content_val}"
                    else:
                        m["content"] = content_val
                else:
                    m["content"] = content_val

            elif role == "tool":
                if not m.get("tool_call_id"): m["tool_call_id"] = "unknown"
                if not m.get("name"): m["name"] = "unknown"

            if m.get("content") is None: m["content"] = ""
            m = {k: v for k, v in m.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id"] and v is not None}
            normalized.append(m)
        log_event("debug_normalize", {"normalized": normalized})
        return normalized

    def _log_llm_call(self, payload: dict, response_text: str, model: str, chat_id: str, duration: float, call_type: str, timings: Optional[dict] = None, tool_calls: Optional[list] = None):
        log_llm_call(payload=payload, response_text=response_text, model=model, chat_id=chat_id, duration_s=duration, call_type=call_type, timings=timings, tool_calls=tool_calls)

    def _is_gemma4_model(self, model: str) -> bool:
        if not model:
            return False
        try:
            from loader import load_model_config
            config_data = load_model_config()
        except Exception:
            return model.lower() == "google/gemma4-26b-a4b-it"

        gemma4_name = config_data.get("general", {}).get("vision_small")
        if gemma4_name and model.lower() == gemma4_name.lower():
            return True

        return False
