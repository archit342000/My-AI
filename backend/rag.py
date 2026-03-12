import chromadb
from chromadb.utils import embedding_functions
import uuid
import os
import requests
import hashlib
import time
from backend.logger import log_event, log_llm_call
from backend import config


def _cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

class LMStudioEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_url="http://localhost:1234", model_name="text-embedding-embeddinggemma-300m", default_task="document", api_key=None):
        self.api_url = api_url
        self.model_name = model_name
        self.default_task = default_task
        self.api_key = api_key

    def __call__(self, input):
        # Standard fallback for ChromaDB internal loops
        return self._embed_with_task(input, task=self.default_task)

    def _embed_with_task(self, input, task=None):
        # Ensure base URL is clean and use /v1/embeddings
        base_url = self.api_url.rstrip("/")
        if not base_url.endswith("/v1"):
            url = f"{base_url}/v1/embeddings"
        else:
            url = f"{base_url}/embeddings"

        # Ensure input is a list of strings
        if isinstance(input, str):
            input = [input]

        processed_input = []
        for item in input:
            processed_input.append(item)

        payload = {
            "model": self.model_name,
            "input": processed_input
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif config.LM_STUDIO_API_KEY:
            headers["Authorization"] = f"Bearer {config.LM_STUDIO_API_KEY}"

        try:
            start_time = time.time()
            response = requests.post(
                url, 
                json=payload, 
                headers=headers,
                timeout=config.TIMEOUT_LLM_BLOCKING or 60
            )
            
            if response.status_code != 200:
                log_event("rag_embedding_error", {
                    "url": url,
                    "status_code": response.status_code,
                    "response": response.text[:500]
                })
            
            response.raise_for_status()
            data = response.json()

            embeddings = [item['embedding'] for item in data['data']]
            duration = time.time() - start_time
            log_llm_call(payload, f"Successfully embedded {len(embeddings)} items.", self.model_name, duration_s=duration, call_type="embedding")
            return embeddings
        except Exception as e:
            log_event("rag_embedding_exception", {
                "url": url,
                "error": str(e)
            })
            raise e

class MemoryRAG:
    COSINE_METADATA = {"hnsw:space": "cosine"}

    @staticmethod
    def _ensure_cosine_collection(client, name, embedding_fn):
        """Ensure the collection exists with cosine distance.
        If an old collection exists with a different metric (e.g. L2 from the
        Gemma era), delete and recreate it. This also clears stale embeddings
        that are incompatible with the current embedding model."""
        try:
            existing = client.get_collection(name=name)
            coll_meta = existing.metadata or {}
            if coll_meta.get("hnsw:space") != "cosine":
                log_event("rag_collection_migration", {
                    "collection": name,
                    "old_space": coll_meta.get("hnsw:space", "l2 (default)"),
                    "action": "delete_and_recreate_with_cosine"
                })
                client.delete_collection(name=name)
        except Exception:
            pass  # Collection doesn't exist yet — will be created below

        return client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
            metadata=MemoryRAG.COSINE_METADATA
        )

    def __init__(self, persist_path=config.CHROMA_PATH, api_url="http://localhost:1234", embedding_model="text-embedding-embeddinggemma-300m", api_key=None):
        self.client = chromadb.PersistentClient(path=persist_path)

        # Initialize custom embedding function
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model,
            api_key=api_key or config.LM_STUDIO_API_KEY
        )

        self.collection = self._ensure_cosine_collection(
            self.client, "memory_store", self.embedding_fn
        )

    def add_core_memory(self, text, tag):
        """Low-level: store a single text document into core memory."""
        if not text or not text.strip():
            return None

        # Generate unique ID for CRUD
        doc_id = str(uuid.uuid4())

        meta = {"timestamp": time.time(), "type": "core", "tag": tag}

        # Explicitly embed so we can correctly assign the "document" prefix
        try:
            if hasattr(self.embedding_fn, '_embed_with_task'):
                embeddings = self.embedding_fn._embed_with_task([text], task="document")
            else:
                embeddings = self.embedding_fn([text])
        except Exception as e:
            log_event("rag_add_memory_error", {"error": str(e)})
            return None

        self.collection.upsert(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
            embeddings=embeddings
        )
        return doc_id

    def update_core_memory(self, doc_id, new_text, new_tag):
        """Updates an existing memory."""
        if not new_text or not new_text.strip():
            return False

        # Verify existence
        existing = self.collection.get(ids=[doc_id])
        if not existing or not existing.get('ids'):
            return False

        meta = {"timestamp": time.time(), "type": "core", "tag": new_tag}

        try:
            if hasattr(self.embedding_fn, '_embed_with_task'):
                embeddings = self.embedding_fn._embed_with_task([new_text], task="document")
            else:
                embeddings = self.embedding_fn([new_text])
        except Exception as e:
            log_event("rag_update_memory_error", {"error": str(e)})
            return False

        self.collection.update(
            documents=[new_text],
            metadatas=[meta],
            ids=[doc_id],
            embeddings=embeddings
        )
        return True

    def delete_core_memory(self, doc_id):
        """Deletes a memory by ID."""
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            log_event("rag_delete_memory_error", {"error": str(e)})
            return False

    def get_all_core_memories_raw(self):
        """Retrieves all core memories as a raw list of dicts."""
        results = self.collection.get(where={"type": "core"})
        memories = []
        if results and results.get('documents'):
            for i in range(len(results['ids'])):
                memories.append({
                    "id": results['ids'][i],
                    "content": results['documents'][i],
                    "tag": results['metadatas'][i].get("tag", "explicit_fact"),
                    "timestamp": results['metadatas'][i].get("timestamp", 0)
                })
        return memories

    def get_all_core_memories_formatted(self):
        """Retrieves and formats core memories for system prompt injection.
        Enforces character limit and priority tags."""
        memories = self.get_all_core_memories_raw()
        if not memories:
            return ""

        # Priority mapping
        tag_priority = {
            "user_preference": 1,
            "user_profile": 2,
            "environment_global": 3,
            "explicit_fact": 4
        }

        # Sort by priority, then descending by timestamp
        memories.sort(key=lambda x: (tag_priority.get(x['tag'], 99), -x['timestamp']))

        formatted_lines = []
        total_chars = 0

        for m in memories:
            line = f"[{m['id']}] [{m['tag'].upper()}] {m['content']}"
            if total_chars + len(line) + 1 > config.MEMORY_MAX_INJECT_CHARS:
                break
            formatted_lines.append(line)
            total_chars += len(line) + 1

        return "\n".join(formatted_lines)

    def reset_memory(self):
        """Clears all stored memories."""
        try:
            self.client.delete_collection(name="memory_store")
            self.collection = self.client.get_or_create_collection(
                name="memory_store",
                embedding_function=self.embedding_fn,
                metadata=self.COSINE_METADATA
            )
            return True
        except Exception as e:
            print(f"Error resetting memory: {e}")
            return False

class ResearchRAG:
    """Ephemeral per-chat storage for Research passes."""
    def __init__(self, persist_path=config.CHROMA_PATH, api_url="http://localhost:1234", embedding_model="text-embedding-embeddinggemma-300m", dedup_threshold=config.RAG_DEDUP_THRESHOLD, api_key=None):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model,
            api_key=api_key or config.LM_STUDIO_API_KEY
        )
        self.dedup_threshold = dedup_threshold
        self.collection = MemoryRAG._ensure_cosine_collection(
            self.client, "research_store", self.embedding_fn
        )

    def _chunk_text(self, text, max_chars=config.RAG_CHUNK_MAX_CHARS):
        """Split text into smaller chunks for more granular deduplication (~600 tokens)."""
        if len(text) <= max_chars:
            return [text]
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_chars:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(para) > max_chars:
                    sentences = para.replace('. ', '.\n').split('\n')
                    current_chunk = ""
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 <= max_chars:
                            current_chunk += (" " if current_chunk else "") + sent
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sent
                else:
                    current_chunk = para
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks if chunks else [text]

    def store_chunk(self, chat_id, step_index, url, full_text, published_date=None):
        if not full_text or len(full_text.strip()) < 10:
            return False, 0
            
        import re
        import hashlib
        import time

        # Split full_text into smaller chunks for granular deduplication
        text_chunks = self._chunk_text(full_text)
        total_tokens = 0
        any_success = False

        for i, chunk_text in enumerate(text_chunks):
            # Clean data for EMBEDDING & DEDUP ONLY (not for storage)
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', chunk_text)
            clean_text = re.sub(r'https?://\S+', '', clean_text)
            clean_text = clean_text.strip()
            
            if len(clean_text) < 10:
                continue

            # Unique ID based on full content to prevent absolute duplicates
            doc_id = hashlib.sha256((chat_id + url + clean_text).encode('utf-8')).hexdigest()
            
            # Deduplication check
            try:
                # 1. First check if this exact hash already exists (Fast path)
                existing = self.collection.get(ids=[doc_id])
                if existing and existing.get('ids'):
                    continue

                # 2. Embedding-based similarity check
                if hasattr(self.embedding_fn, '_embed_with_task'):
                    query_embedding = self.embedding_fn._embed_with_task([clean_text], task="document")[0]
                else:
                    query_embedding = self.embedding_fn([clean_text])[0]
                
                # Fetch up to 3 nearest neighbors from the current chat
                count = self.collection.count()
                n = min(3, count) if count > 0 else 0

                is_duplicate = False
                if n > 0:
                    results = self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=n,
                        where={"chat_id": chat_id},
                        include=['embeddings']
                    )
                    
                    if results and results.get('embeddings') and len(results['embeddings'][0]) > 0:
                        for emb in results['embeddings'][0]:
                            sim = _cosine_similarity(query_embedding, emb)
                            if sim > self.dedup_threshold:
                                is_duplicate = True
                                break
                
                if not is_duplicate:
                    meta = {
                        "chat_id": chat_id,
                        "step_index": step_index,
                        "url": url,
                        "timestamp": time.time(),
                        "published_date": published_date or ""
                    }
                    self.collection.upsert(
                        documents=[chunk_text.strip()],
                        metadatas=[meta],
                        ids=[doc_id],
                        embeddings=[query_embedding]
                    )
                    total_tokens += len(chunk_text) // 4
                    any_success = True
                    
            except Exception as e:
                # Minimal logging for background errors
                print(f"[ResearchRAG] Store error: {e}")
                continue

        return any_success, total_tokens
            
    def get_all_chunks(self, chat_id, limit=config.RAG_RETRIEVAL_LIMIT):
        """Retrieve all stored chunks for a session, capped at a safe limit."""
        try:
            results = self.collection.get(
                where={"chat_id": chat_id},
                limit=limit
            )
            if not results or not results.get('documents'):
                return []
            
            chunks = []
            for doc, meta in zip(results['documents'], results['metadatas']):
                chunks.append({
                    "text": doc,
                    "url": meta.get("url", ""),
                    "step_index": meta.get("step_index", 0),
                    "timestamp": meta.get("timestamp", 0)
                })
            
            # Sort by step_index then timestamp for logical narrative flow
            chunks.sort(key=lambda x: (x['step_index'], x['timestamp']))
            return chunks
        except Exception as e:
            print(f"[ResearchRAG] Retrieval error: {e}")
            return []

    def get_step_chunks(self, chat_id, step_index):
        """Retrieve all stored chunks for a specific step.
        Used for post-step verification and debugging."""
        try:
            results = self.collection.get(
                where={"$and": [{"chat_id": chat_id}, {"step_index": step_index}]}
            )
            if not results or not results.get('documents'):
                return []
            
            chunks = []
            for doc, meta in zip(results['documents'], results['metadatas']):
                chunks.append({
                    "text": doc,
                    "url": meta.get("url", ""),
                    "step_index": meta.get("step_index", 0)
                })
            return chunks
        except Exception as e:
            print(f"[ResearchRAG] Step retrieval error: {e}")
            return []

    def retrieve_for_report(self, chat_id, queries, max_tokens=config.RESEARCH_MAX_TOKENS_RAG_CONTEXT):
        """Multi-query semantic retrieval with dynamic per-query token budgeting.
        
        Args:
            chat_id: The research session ID
            queries: List of {"query": str, "step_filter": int|None}
                     step_filter=None means global retrieval (no step scope)
            max_tokens: Total token budget across all queries
        
        Returns:
            List of {"text": str, "url": str, "step_index": int} chunks,
            deduplicated and capped at token budget.
        """
        if not queries:
            return self.get_all_chunks(chat_id)

        per_query_budget = max_tokens // len(queries)
        all_chunks = []
        seen_doc_ids = set()  # For deduplication across queries
        total_tokens = 0

        for q_info in queries:
            query_text = q_info["query"]
            step_filter = q_info.get("step_filter")

            try:
                # Embed using "query" task for retrieval
                if hasattr(self.embedding_fn, '_embed_with_task'):
                    query_emb = self.embedding_fn._embed_with_task([query_text], task="query")[0]
                else:
                    query_emb = self.embedding_fn([query_text])[0]

                # Build where clause: always filter by chat_id, optionally by step
                if step_filter is not None:
                    where_clause = {"$and": [
                        {"chat_id": chat_id},
                        {"step_index": step_filter}
                    ]}
                else:
                    where_clause = {"chat_id": chat_id}

                # Retrieve candidates (generous limit, ChromaDB ranks by distance)
                results = self.collection.query(
                    query_embeddings=[query_emb],
                    n_results=200,
                    where=where_clause,
                    include=["documents", "metadatas", "embeddings"]
                )

                if not results or not results.get('documents') or not results['documents'][0]:
                    continue

                # Accumulate within per-query budget, skip already-seen chunks
                query_tokens = 0
                for doc, meta, emb in zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['embeddings'][0]
                ):
                    # Dedup: use content hash
                    doc_hash = hash(doc[:200] + doc[-200:] if len(doc) > 400 else doc)
                    if doc_hash in seen_doc_ids:
                        continue

                    chunk_tokens = len(doc) // 4
                    if query_tokens + chunk_tokens > per_query_budget:
                        break
                    if total_tokens + chunk_tokens > max_tokens:
                        return all_chunks  # Global budget exhausted

                    # Compute relevance score for potential future sorting
                    relevance = _cosine_similarity(query_emb, emb)
                    
                    all_chunks.append({
                        "text": doc,
                        "url": meta.get("url", ""),
                        "step_index": meta.get("step_index", 0),
                        "relevance": relevance,
                        "timestamp": meta.get("timestamp", 0),
                        "published_date": meta.get("published_date", "")
                    })
                    seen_doc_ids.add(doc_hash)
                    query_tokens += chunk_tokens
                    total_tokens += chunk_tokens

            except Exception as e:
                print(f"[ResearchRAG] Retrieval error for query '{query_text[:50]}': {e}")
                continue

        # Sort by relevance descending for optimal reporter context ordering
        all_chunks.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return all_chunks

    def cleanup_chat(self, chat_id):
        """Delete all stored chunks for a given chat_id to prevent unbounded growth."""
        try:
            results = self.collection.get(where={"chat_id": chat_id})
            if results and results.get('ids'):
                self.collection.delete(ids=results['ids'])
                print(f"[ResearchRAG] Cleaned up {len(results['ids'])} chunks for chat {chat_id}")
                return True
        except Exception as e:
            print(f"[ResearchRAG] Cleanup error: {e}")
        return False
