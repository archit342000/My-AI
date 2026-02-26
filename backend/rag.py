import chromadb
from chromadb.utils import embedding_functions
import uuid
import os
import requests
import hashlib
import time
from backend.logger import log_event, log_llm_call

class LMStudioEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_url="http://localhost:1234", model_name="text-embedding-jina-embeddings-v5-text-small-retrieval", default_task="document"):
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
        is_jina = "jina" in self.model_name.lower()
        
        for item in input:
            if is_jina:
                current_task = task or self.default_task
                prefix = "Query: " if current_task == "query" else "Document: "
                # Avoid double prefixing
                if item.startswith("Query: ") or item.startswith("Document: ") or item.startswith("retrieval."):
                    processed_input.append(item)
                else:
                    processed_input.append(f"{prefix}{item}")
            else:
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
                timeout=10
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
    def __init__(self, persist_path="./backend/chroma_db", api_url="http://localhost:1234", embedding_model="text-embedding-jina-embeddings-v5-text-small-retrieval"):
        self.client = chromadb.PersistentClient(path=persist_path)

        # Initialize custom embedding function
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model
        )

        self.collection = self.client.get_or_create_collection(
            name="memory_store",
            embedding_function=self.embedding_fn
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

    def _chunk_text(self, text, max_chars=2500):
        """Split long text into chunks of ~600 tokens (~2500 chars).
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
        DECAY_RATE = 0.05
        
        # Heuristic Threshold for Cosine Similarity (Range -1 to 1)
        # 1.0 = identical, 0.0 = orthogonal
        # For Jina v5, embeddings tend to express un-relatedness very close to 0
        MIN_SEMANTIC_SCORE = 0.35 # Increased for Jina v5 to filter better

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
            
            # Decay factor increases with age
            # 1 hour -> 1.03
            # 24 hour -> 1.16
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
                embedding_function=self.embedding_fn
            )
            return True
        except Exception as e:
            print(f"Error resetting memory: {e}")
            return False

class DeepResearchRAG:
    """Ephemeral per-chat storage for Deep Research passes."""
    def __init__(self, persist_path="./backend/chroma_db", api_url="http://localhost:1234", embedding_model="text-embedding-jina-embeddings-v5-text-small-retrieval"):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embedding_fn = LMStudioEmbeddingFunction(
            api_url=api_url,
            model_name=embedding_model
        )
        self.collection = self.client.get_or_create_collection(
            name="deep_research_store",
            embedding_function=self.embedding_fn
        )

    def store_chunk(self, chat_id, step_index, url, chunk_text):
        if not chunk_text or len(chunk_text.strip()) < 10:
            return False, 0
            
        # Clean data for EMBEDDING & DEDUP ONLY (not for storage)
        import re
        # Remove markdown URLs [text](url) but keep the text
        clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', chunk_text)
        # Remove raw http/https links
        clean_text = re.sub(r'https?://\S+', '', clean_text)
        # Remove any other common noisy artifacts
        clean_text = clean_text.strip()
        
        if len(clean_text) < 10:
            return False, 0

        # Unique ID based on content to prevent absolute duplicates
        doc_id = hashlib.sha256((chat_id + url + clean_text[:50]).encode('utf-8')).hexdigest()
        
        # Deduplication check against this chat's existing store
        try:
            if hasattr(self.embedding_fn, '_embed_with_task'):
                query_embedding = self.embedding_fn._embed_with_task([clean_text], task="document")[0]
            else:
                query_embedding = self.embedding_fn([clean_text])[0]
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=1,
                where={"chat_id": chat_id},
                include=['embeddings']
            )
            
            if results and results.get('embeddings') and len(results['embeddings'][0]) > 0:
                emb = results['embeddings'][0][0]
                def cosine_similarity(v1, v2):
                    dot_product = sum(a * b for a, b in zip(v1, v2))
                    norm_a = sum(a * a for a in v1) ** 0.5
                    norm_b = sum(b * b for b in v2) ** 0.5
                    if norm_a == 0 or norm_b == 0: return 0.0
                    return dot_product / (norm_a * norm_b)
                
                sim = cosine_similarity(query_embedding, emb)
                # Lenient deduplication threshold: > 85% means structurally identical (boilerplate)
                if sim > 0.85:
                    return False, 0 # dropped
        except Exception as e:
            print(f"[DeepResearchRAG] Deduplication error: {e}")
            return False, 0

        # Store ORIGINAL text (with URLs intact for citation), use clean_text only for embedding
        original_text = chunk_text.strip()

        meta = {
            "chat_id": chat_id,
            "step_index": step_index,
            "url": url,
            "timestamp": time.time()
        }
        
        try:
            # Pass our manually computed embedding to bypass Chroma's internal embedding 
            # attempt, which would otherwise crash on the huge original_text
            self.collection.upsert(
                documents=[original_text],
                metadatas=[meta],
                ids=[doc_id],
                embeddings=[query_embedding]
            )
            # Approximate token count for budgeting - after cleaning
            return True, len(original_text) // 4
        except Exception as e:
            print(f"[DeepResearchRAG] Store error: {e}")
            return False, 0
            
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
