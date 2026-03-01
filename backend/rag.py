import chromadb
from chromadb.utils import embedding_functions
import uuid
import os
import requests
import hashlib
import time
from backend.logger import log_event, log_llm_call

class LMStudioEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_url="http://localhost:1234", model_name="text-embedding-embeddinggemma-300m", default_task="document"):
        self.api_url = api_url
        self.model_name = model_name
        self.default_task = default_task

    def __call__(self, input):
        # Standard fallback for ChromaDB internal loops
        return self._embed_with_task(input, task=self.default_task)

    def _embed_with_task(self, input, task=None):
        # Ensure base URL is clean and handle /v1 suffix robustly
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

        try:
            start_time = time.time()
            response = requests.post(
                url, 
                json=payload, 
                headers={"Content-Type": "application/json"},
                timeout=60
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

    def __init__(self, persist_path="./backend/chroma_db", api_url="http://localhost:1234", embedding_model="text-embedding-embeddinggemma-300m"):
        self.client = chromadb.PersistentClient(path=persist_path)

        # Initialize custom embedding function
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model
        )

        self.collection = self._ensure_cosine_collection(
            self.client, "memory_store", self.embedding_fn
        )

    def add_memory(self, text, metadata=None):
        """Low-level: store a single text document."""
        if not text or not text.strip():
            return

        # Deduplication: Use hash of text as ID
        doc_id = hashlib.sha256(text.encode('utf-8')).hexdigest()

        # Default metadata
        meta = {"timestamp": time.time(), "type": "conversation"}
        if metadata:
            meta.update(metadata)

        # Explicitly embed so we can correctly assign the "document" prefix
        try:
            # Use our custom method to bypass Chroma's strict __call__ signature enforcement
            if hasattr(self.embedding_fn, '_embed_with_task'):
                embeddings = self.embedding_fn._embed_with_task([text], task="document")
            else:
                embeddings = self.embedding_fn([text])
        except Exception as e:
            log_event("rag_add_memory_error", {"error": str(e)})
            return

        # Use upsert to handle potential duplicates (idempotent)
        self.collection.upsert(
            documents=[text],
            metadatas=[meta],
            ids=[doc_id],
            embeddings=embeddings
        )

    # --- Noise Filtering ---
    TRIVIAL_MESSAGES = {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "whats up", "yo", "greetings", "hi there", "hello there",
        "ok", "okay", "sure", "thanks", "thank you", "cool", "yes", "no",
        "bye", "goodbye", "see you", "got it", "alright", "yep", "nope",
    }

    def _is_trivial(self, text):
        """Check if a message is too short or generic to store."""
        clean = "".join(c for c in text.strip().lower() if c.isalnum() or c.isspace())
        return clean in self.TRIVIAL_MESSAGES or len(clean) < 5

    def _chunk_text(self, text, max_chars=2200):
        """Split long text into chunks of ~600-800 tokens (~2200 chars).
        Splits on paragraph boundaries first, then sentence boundaries."""
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
                # If a single paragraph exceeds max, split on sentences
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

    def _clean_for_storage(self, text):
        """Strip tool call patterns and other artifacts from text before storing."""
        import re
        # Remove text-based tool call patterns like [search_memory(query="...")]
        text = re.sub(r'\[\w+\(.*?\)\]', '', text)
        # Remove any "Relevant Context:" blocks the model might have hallucinated
        text = re.sub(r'(?:Relevant Context|Earlier Context):.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
        # Remove reasoning blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return text.strip()

    def add_conversation_turn(self, user_text, assistant_text, chat_id=None):
        """Store a conversation turn as separate, well-structured documents.
        
        - User and assistant messages are stored separately with clear labels.
        - Trivial messages (greetings, short acks) are filtered out.
        - Tool call artifacts are stripped before storage.
        - Long assistant responses are chunked for optimal retrieval.
        """
        ts = time.time()
        base_meta = {"chat_id": chat_id, "timestamp": ts, "type": "conversation"} if chat_id else {"timestamp": ts, "type": "conversation"}

        # Clean inputs
        clean_user = self._clean_for_storage(user_text) if user_text else ""
        clean_assistant = self._clean_for_storage(assistant_text) if assistant_text else ""

        # 1. Store user message (if non-trivial)
        if clean_user and not self._is_trivial(clean_user):
            user_meta = {**base_meta, "role": "user"}
            self.add_memory(f"[USER] {clean_user}", user_meta)

        # 2. Store assistant response (chunked if long, skip if trivial)
        if clean_assistant and not self._is_trivial(clean_assistant):
            chunks = self._chunk_text(clean_assistant)
            for i, chunk in enumerate(chunks):
                chunk_meta = {**base_meta, "role": "assistant"}
                if len(chunks) > 1:
                    chunk_meta["chunk_index"] = i
                    chunk_meta["total_chunks"] = len(chunks)
                # Prefix with what the user asked for retrieval context
                context_hint = f"(User asked: \"{clean_user[:100]}\")\n" if clean_user else ""
                self.add_memory(f"[ASSISTANT] {context_hint}{chunk}", chunk_meta)


    def add_core_memory(self, text):
        """Adds a fact to the permanent Core Memory."""
        self.add_memory(text, metadata={"type": "core", "timestamp": time.time()})

    def get_core_memory(self):
        """Retrieves all core memories."""
        results = self.collection.get(where={"type": "core"})
        if results and results['documents']:
             return "\n".join(results['documents'])
        return ""

    def retrieve_context(self, query, n_results=5, where=None):
        if not query:
            return ""
        
        # 1. Imports
        import math
        import time

        # 2. Smart Filter: Ignore generic greetings & short queries
        q_lower = query.strip().lower()
        q_clean = "".join(c for c in q_lower if c.isalnum() or c.isspace())
        
        COMMON_GREETINGS = {
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening", 
            "how are you", "whats up", "yo", "greetings", "hi there", "hello there",
            "ok", "okay", "sure", "thanks", "thank you", "cool", "yes", "no"
        }
        
        if q_clean in COMMON_GREETINGS or len(q_clean) < 3:
             return ""

        # 3. Explicitly Embed Query for Re-Ranking
        try:
             # Use custom explicit entry to bypass Chroma constraints
             if hasattr(self.embedding_fn, '_embed_with_task'):
                 query_embedding = self.embedding_fn._embed_with_task([query], task="query")[0]
             else:
                 query_embedding = self.embedding_fn([query])[0]
        except Exception as e:
             # If embedding fails, return nothing
             print(f"Embedding error: {e}")
             return ""

        # 4. Fetch Large Candidate Pool
        # We fetch 5x results to re-rank semantically and chronologically
        FETCH_K = n_results * 5
        
        # We request 'embeddings' to do manual cosine similarity
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=FETCH_K,
            where=where,
            include=['documents', 'metadatas', 'embeddings'] 
        )

        if not results['documents']:
            return ""

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        embeddings = results['embeddings'][0]

        # 5. Helper: Manual Cosine Similarity
        def cosine_similarity(v1, v2):
            dot_product = sum(a * b for a, b in zip(v1, v2))
            norm_a = sum(a * a for a in v1) ** 0.5
            norm_b = sum(b * b for b in v2) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        # 6. Scoring & Re-Ranking
        scored_results = []
        current_time = time.time()
        DECAY_RATE = 0.10
        
        # Heuristic Threshold for Cosine Similarity (Range -1 to 1)
        # 1.0 = identical, 0.0 = orthogonal
        # With cosine distance metric properly set, Qwen model scores are well-
        # calibrated: >0.7 strong match, 0.5-0.7 moderate, <0.5 weak.
        MIN_SEMANTIC_SCORE = 0.50

        for doc, meta, emb in zip(documents, metadatas, embeddings):
            # A. Semantic Score (High is Good)
            sem_score = cosine_similarity(query_embedding, emb)
            print(f"[RAG DEBUG] Candidate: '{doc[:50]}...' Score: {sem_score:.3f}")
            
            if sem_score < MIN_SEMANTIC_SCORE:
                continue

            # B. Recency Penalty (Time Decay)
            # High Penalty = Bad
            timestamp = float(meta.get('timestamp', 0))
            # Handle potential non-numeric timestamp
            if timestamp == 0: 
                 try: timestamp = float(meta.get('timestamp'))
                 except: timestamp = 0

            age_seconds = current_time - timestamp
            age_hours = age_seconds / 3600
            if age_hours < 0: age_hours = 0
            
            # Decay factor increases with age (DECAY_RATE=0.10)
            # 1 hour  -> 1.07
            # 24 hour -> 1.32
            # 720 hour (1 month) -> 1.66
            time_decay = 1 + (math.log(age_hours + 1) * DECAY_RATE)
            
            # Final Score: Similarity / Decay
            # (High Sim / Low Decay) = Best
            final_score = sem_score / time_decay
            
            scored_results.append((doc, final_score))

        # Sort DESCENDING (Higher score is better)
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        # Take Top N
        final_docs = [item[0] for item in scored_results[:n_results]]
        
        if not final_docs:
            return ""

        # Simplified format for Tool Output
        # Just return the raw text chunks separated by newlines
        context = "\n\n".join(final_docs)
        return context

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

class DeepResearchRAG:
    """Ephemeral per-chat storage for Deep Research passes."""
    def __init__(self, persist_path="./backend/chroma_db", api_url="http://localhost:1234", embedding_model="text-embedding-embeddinggemma-300m"):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model
        )
        self.collection = MemoryRAG._ensure_cosine_collection(
            self.client, "deep_research_store", self.embedding_fn
        )

    def _chunk_text(self, text, max_chars=2200):
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

    def store_chunk(self, chat_id, step_index, url, full_text):
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
                        def cosine_similarity(v1, v2):
                            dot_product = sum(a * b for a, b in zip(v1, v2))
                            norm_a = sum(a * a for a in v1) ** 0.5
                            norm_b = sum(b * b for b in v2) ** 0.5
                            if norm_a == 0 or norm_b == 0: return 0.0
                            return dot_product / (norm_a * norm_b)
                        
                        for emb in results['embeddings'][0]:
                            sim = cosine_similarity(query_embedding, emb)
                            # 0.92 is solid for 2000-char chunks; catches boilerplate/copies
                            if sim > 0.92:
                                is_duplicate = True
                                break
                
                if not is_duplicate:
                    meta = {
                        "chat_id": chat_id,
                        "step_index": step_index,
                        "url": url,
                        "timestamp": time.time()
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
                print(f"[DeepResearchRAG] Store error: {e}")
                continue

        return any_success, total_tokens
            
    def get_all_chunks(self, chat_id):
        try:
            results = self.collection.get(where={"chat_id": chat_id})
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
            print(f"[DeepResearchRAG] Retreival error: {e}")
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
            print(f"[DeepResearchRAG] Step retrieval error: {e}")
            return []

    def retrieve_for_report(self, chat_id, queries, max_tokens=400000):
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

        def cosine_similarity(v1, v2):
            dot_product = sum(a * b for a, b in zip(v1, v2))
            norm_a = sum(a * a for a in v1) ** 0.5
            norm_b = sum(b * b for b in v2) ** 0.5
            if norm_a == 0 or norm_b == 0: return 0.0
            return dot_product / (norm_a * norm_b)

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
                    n_results=100,
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
                    relevance = cosine_similarity(query_emb, emb)
                    
                    all_chunks.append({
                        "text": doc,
                        "url": meta.get("url", ""),
                        "step_index": meta.get("step_index", 0),
                        "relevance": relevance
                    })
                    seen_doc_ids.add(doc_hash)
                    query_tokens += chunk_tokens
                    total_tokens += chunk_tokens

            except Exception as e:
                print(f"[DeepResearchRAG] Retrieval error for query '{query_text[:50]}': {e}")
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
                print(f"[DeepResearchRAG] Cleaned up {len(results['ids'])} chunks for chat {chat_id}")
                return True
        except Exception as e:
            print(f"[DeepResearchRAG] Cleanup error: {e}")
        return False
