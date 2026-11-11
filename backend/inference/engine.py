import httpx
import json
import time
import asyncio
import os
import logging
import re
from typing import List, Dict, Any, Optional, AsyncGenerator, Union
from functools import lru_cache
from backend import config
from backend.logging import log_llm_call, log_event, log_embedding_call, error_detail
from backend.utils import merge_tool_call_deltas

logger = logging.getLogger(__name__)

class InferenceEngine:
    """
    Client-side forwarder wrapper for LLM inference and embeddings.
    Always routes requests directly to the standalone proxy.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InferenceEngine, cls).__new__(cls)
            
            cls._instance.timeout_llm = config.TIMEOUT_LLM_ASYNC or 120.0
            cls._instance.timeout_embedding = config.TIMEOUT_EMBEDDING
            
            log_event("client_inference_engine_initialized", {
                "proxy_url": cls._instance.proxy_url,
                "mode": "proxy"
            })
        return cls._instance

    @property
    def proxy_url(self) -> str:
        if hasattr(self, "_proxy_url_override"):
            return self._proxy_url_override
        return config.AI_PROXY_URL.rstrip("/")

    @proxy_url.setter
    def proxy_url(self, value: str):
        self._proxy_url_override = value

    @proxy_url.deleter
    def proxy_url(self):
        if hasattr(self, "_proxy_url_override"):
            del self._proxy_url_override

    def __init__(self):
        pass

    async def start(self):
        log_event("client_inference_engine_started", {"status": "ready"})
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
        Runs local compression, applies client-side retries, and forwards blocking completions to the proxy.
        """
        if chat_id and not params.get("skip_compression"):
            from backend.inference.compression import check_and_trigger_compression
            params_copy = params.copy()
            params_copy.pop("skip_compression", None)
            params_copy.pop("max_tokens", None)
            messages = await check_and_trigger_compression(
                chat_id=chat_id,
                messages=messages,
                model=model,
                max_tokens=params.get("max_tokens"),
                **params_copy
            )
        else:
            params = params.copy()
            params.pop("skip_compression", None)

        attempts = 0
        max_attempts = config.LLM_RETRY_COUNT

        while attempts < max_attempts:
            attempts += 1
            start_time = time.time()
            
            endpoint = f"{self.proxy_url}/api/models/v1/chat/completions"

            payload = {
                "model": model,
                "messages": self._normalize_messages(messages),
                "stream": False,
                **params
            }
            
            if self._is_gemma4_model(model):
                payload["tool_call_parser"] = "gemma4"
            
            if chat_template_kwargs:
                payload["chat_template_kwargs"] = chat_template_kwargs

            try:
                response = await self._request("POST", endpoint, payload, self.timeout_llm)
                data = response.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                
                content = msg.get("content") or ""
                tool_calls = msg.get("tool_calls")
                
                is_valid, repaired_tcs = self._is_generation_valid(content, tool_calls)
                if not is_valid:
                    if attempts < max_attempts:
                        log_event("inference_retry", {
                            "reason": "invalid_generation", 
                            "attempt": attempts, 
                            "chat_id": chat_id
                        })
                        await asyncio.sleep(config.LLM_RETRY_DELAY)
                        continue
                else:
                    if repaired_tcs is not None:
                        tool_calls = repaired_tcs
                        msg["tool_calls"] = repaired_tcs

                reasoning = msg.get("reasoning_content") or ""
                final_log_text = ""
                if reasoning:
                    final_log_text += f"[Reasoning]\n{reasoning}\n[Content]\n"
                final_log_text += content
                
                raw_text = self._reconstruct_raw_response(model, content, reasoning, tool_calls)
                
                self._log_llm_call(
                    payload=payload, 
                    response_text=final_log_text, 
                    model=model, 
                    chat_id=chat_id, 
                    duration=time.time() - start_time, 
                    call_type="engine_blocking",
                    timings=data.get("timings"),
                    tool_calls=tool_calls,
                    parsed_response=content,
                    raw_response=raw_text
                )
                
                return data
            except Exception as e:
                if attempts < max_attempts:
                    log_event("inference_chat_retry_error", {"error": error_detail(e), "attempt": attempts, "chat_id": chat_id})
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
        Runs local compression, applies client-side retries/redaction, and streams completions from the proxy.
        """
        if chat_id and not params.get("skip_compression"):
            from backend.inference.compression import check_and_trigger_compression
            params_copy = params.copy()
            params_copy.pop("skip_compression", None)
            params_copy.pop("max_tokens", None)
            messages = await check_and_trigger_compression(
                chat_id=chat_id,
                messages=messages,
                model=model,
                max_tokens=params.get("max_tokens"),
                **params_copy
            )
        else:
            params = params.copy()
            params.pop("skip_compression", None)

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
            raw_chunks = []
            tool_calls = {}
            sorted_tool_calls = None
            timings = None
            start_time = time.time()
            
            endpoint = f"{self.proxy_url}/api/models/v1/chat/completions"

            payload = {
                "model": model,
                "messages": self._normalize_messages(messages),
                "stream": True,
                **params
            }
            
            if self._is_gemma4_model(model):
                payload["tool_call_parser"] = "gemma4"
            
            if chat_template_kwargs:
                payload["chat_template_kwargs"] = chat_template_kwargs

            try:
                headers = self._get_headers()
                timeout = httpx.Timeout(self.timeout_llm, read=config.TIMEOUT_LLM_STREAM_READ)
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            if line == "data: [DONE]":
                                break
                            try:
                                chunk = json.loads(line[6:])
                                raw_chunks.append(chunk)
                                if "timings" in chunk:
                                    timings = chunk["timings"]
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    if "content" in delta and delta["content"] is not None:
                                        full_content += delta["content"]
                                    if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                                        full_reasoning += delta["reasoning_content"]
                                    if "tool_calls" in delta and delta["tool_calls"] is not None:
                                        for tc_delta in delta["tool_calls"]:
                                            idx = tc_delta.get("index", 0)
                                            if idx not in tool_calls:
                                                tool_calls[idx] = tc_delta.copy()
                                            else:
                                                merge_tool_call_deltas(tool_calls[idx], tc_delta)
                            except Exception as parse_err:
                                logger.debug("Failed to parse SSE line: %s, error: %s", line, parse_err, exc_info=True)
                            yield line
                
                sorted_tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())] if tool_calls else None
                is_valid, repaired_tcs = self._is_generation_valid(full_content, sorted_tool_calls)
                if not is_valid:
                    if attempts < max_attempts:
                        log_event("inference_stream_retry", {
                            "reason": "invalid_generation", 
                            "attempt": attempts, 
                            "chat_id": chat_id
                        })
                        yield f"data: {json.dumps({'__redact__': True, 'message': 'Checking the answer again…'})}\n\n"
                        await asyncio.sleep(config.LLM_RETRY_DELAY)
                        continue
                else:
                    if repaired_tcs is not None:
                        sorted_tool_calls = repaired_tcs
                break

            except Exception as e:
                if attempts < max_attempts:
                    log_event("inference_stream_retry_error", {"error": error_detail(e), "attempt": attempts, "chat_id": chat_id})
                    yield f"data: {json.dumps({'__redact__': True, 'message': 'The model did not respond. Trying again…'})}\n\n"
                    await asyncio.sleep(config.LLM_RETRY_DELAY)
                    continue
                log_event("inference_stream_error", {"error": error_detail(e), "chat_id": chat_id})
                raise
            finally:
                is_valid, repaired_tcs = self._is_generation_valid(full_content, sorted_tool_calls)
                if attempts >= max_attempts or is_valid:
                    if is_valid and repaired_tcs is not None:
                        sorted_tool_calls = repaired_tcs
                    final_log_text = ""
                    if full_reasoning:
                        final_log_text += f"[Reasoning]\n{full_reasoning}\n[Content]\n"
                    final_log_text += full_content
                    
                    raw_text = self._reconstruct_raw_response(model, full_content, full_reasoning, sorted_tool_calls)
                    
                    self._log_llm_call(
                        payload=payload, 
                        response_text=final_log_text, 
                        model=model, 
                        chat_id=chat_id, 
                        duration=time.time() - start_time, 
                        call_type="engine_stream",
                        timings=timings,
                        tool_calls=sorted_tool_calls,
                        parsed_response=full_content,
                        raw_response=raw_text
                    )

    async def embed(self, input: Union[str, List[str]], model: str, chat_id: Optional[str] = None, **params) -> List[List[float]]:
        """
        Forwards embedding generation requests to the proxy.
        """
        endpoint = f"{self.proxy_url}/api/models/v1/embeddings"

        payload = {
            "model": model,
            "input": [input] if isinstance(input, str) else input,
            "chat_id": chat_id,
            **params
        }

        start_time = time.time()
        try:
            response = await self._request("POST", endpoint, payload, self.timeout_embedding)
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

    def embed_sync(self, *args, **kwargs) -> List[List[float]]:
        """
        Synchronous wrapper for embed().
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.embed(*args, **kwargs))

    async def ensure_model_loaded(self, model_name: str):
        """
        Forwards the model load check to the proxy.
        """
        endpoint = f"{self.proxy_url}/api/models/load"
        payload = {"model": model_name}
        try:
            await self._request("POST", endpoint, payload, self.timeout_llm)
        except Exception as e:
            log_event("ensure_model_loaded_error", {
                "error": str(e), 
                "model": model_name
            })

    async def _request(self, method: str, url: str, payload: dict, timeout: float) -> httpx.Response:
        headers = self._get_headers()
        async with httpx.AsyncClient(timeout=timeout) as client:
            kwargs = {"json": payload} if payload is not None else {}
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        return headers

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

    def _is_generation_valid(self, content: str, tool_calls: Optional[List[Dict[str, Any]]]) -> tuple[bool, Optional[List[Dict[str, Any]]]]:
        has_content = content and content.strip()
        has_tool_calls = tool_calls and len(tool_calls) > 0
        
        if not has_content and not has_tool_calls:
            return False, tool_calls
            
        repaired_tool_calls = None
        if has_tool_calls:
            import copy
            repaired_tool_calls = copy.deepcopy(tool_calls)
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
            for tc in repaired_tool_calls:
                func = tc.get("function", {})
                name = func.get("name") or ""
                args_str = func.get("arguments") or ""
                
                # Reject tool calls containing special thought or tool call tokens
                for token in forbidden_tokens:
                    if token in name or token in args_str:
                        return False, tool_calls
                
                if args_str:
                    try:
                        json.loads(args_str)
                    except Exception:
                        repaired = self._salvage_json_arguments(args_str)
                        if repaired is not None:
                            func["arguments"] = repaired
                        else:
                            return False, tool_calls
        return True, repaired_tool_calls

    def _normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        allowed_roles = ["system", "user", "assistant", "tool"]
        
        for msg in messages:
            m = dict(msg)
            role = m.get("role")
            
            if role not in allowed_roles:
                continue
            
            content = m.get("content")
            
            # Special handling for screenshot references in tool results
            if role == "tool" and isinstance(content, dict) and "screenshot_ref" in content:
                ref_path = content.get("screenshot_ref")
                mime_type = content.get("mime_type", "image/jpeg")
                
                m["content"] = content.get("message", "Screenshot captured.")
                if not m.get("tool_call_id"): m["tool_call_id"] = "unknown"
                if not m.get("name"): m["name"] = "unknown"
                
                normalized.append({k: v for k, v in m.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id"]})
                
                if ref_path and os.path.exists(ref_path):
                    try:
                        import base64
                        with open(ref_path, "rb") as f:
                            b64_data = base64.b64encode(f.read()).decode("utf-8")
                        
                        normalized.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Visual context from the browser screenshot taken in the previous step:"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
                                }
                            ]
                        })
                    except Exception as e:
                        logger.error(f"Failed to load screenshot for synthetic user msg: {e}")
                
                continue

            elif isinstance(content, (list, dict)):
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
            elif role == "tool":
                if not m.get("tool_call_id"): m["tool_call_id"] = "unknown"
                if not m.get("name"): m["name"] = "unknown"

            if m.get("content") is None: m["content"] = ""
            m = {k: v for k, v in m.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id", "reasoning_content"] and v is not None}
            normalized.append(m)
        return normalized

    def _log_llm_call(self, payload: dict, response_text: str, model: str, chat_id: str, duration: float, call_type: str, timings: Optional[dict] = None, tool_calls: Optional[list] = None, parsed_response: Optional[str] = None, raw_response: Optional[Any] = None):
        try:
            log_llm_call(payload=payload, response_text=response_text, model=model, chat_id=chat_id, duration_s=duration, call_type=call_type, timings=timings, tool_calls=tool_calls, parsed_response=parsed_response, raw_response=raw_response)
        except Exception as e:
            logger.warning(f"Failed to log LLM call: {e}")

    def _reconstruct_raw_response(self, model: str, content: str, reasoning: Optional[str], tool_calls: Optional[list]) -> str:
        try:
            raw_text = ""
            model_lower = (model or "").lower()
            is_gemma = "gemma" in model_lower
            
            if reasoning:
                if is_gemma:
                    raw_text += f"<|channel>thought\n{reasoning}\n<channel|>\n"
                else:
                    raw_text += f"<think>\n{reasoning}\n</think>\n"
            
            raw_text += content or ""
            
            if tool_calls:
                if is_gemma:
                    for tc in tool_calls:
                        try:
                            fn = tc.get("function", {})
                            name = fn.get("name", "")
                            args = fn.get("arguments", "{}")
                            raw_text += f"\n<|tool_call>call:{name}{args}<tool_call|>"
                        except Exception:
                            pass
                else:
                    # Standard tool call formatting (e.g. standard JSON or function block)
                    for tc in tool_calls:
                        try:
                            fn = tc.get("function", {})
                            name = fn.get("name", "")
                            args = fn.get("arguments", "{}")
                            raw_text += f"\n<tool_call>{{\"name\": \"{name}\", \"arguments\": {args}}}</tool_call>"
                        except Exception:
                            pass
            return raw_text
        except Exception as e:
            logger.warning(f"Error reconstructing raw response: {e}")
            fallback = ""
            if reasoning:
                fallback += f"<think>\n{reasoning}\n</think>\n"
            fallback += content or ""
            if tool_calls:
                fallback += f"\n[Tool Calls: {tool_calls}]"
            return fallback

    @lru_cache(maxsize=128)
    def _is_gemma4_model(self, model: str) -> bool:
        if not model:
            return False
        try:
            from backend.models import load_model_config
            config_data = load_model_config()
        except Exception:
            return model.lower() == "google/gemma4-26b-a4b-it"

        gemma4_name = config_data.get("general", {}).get("vision_small")
        if gemma4_name and model.lower() == gemma4_name.lower():
            return True

        return False
