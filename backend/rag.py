import chromadb
import json
from chromadb.utils import embedding_functions
import uuid
import os
import requests
import hashlib
import time
import math
import logging
import re
from backend.logger import log_event, log_llm_call
from backend import config
from backend.model_loader import get_embedding_model
from backend.token_counter import count_tokens, split_text_by_tokens, truncate_text_by_tokens


def _cosine_similarity(v1, v2):
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


# =============================================================================
# RAG Manager - Centralized RAG Infrastructure
# =============================================================================

class RAGManager:
    """
    Centralized RAG manager that provides shared infrastructure for all RAG types.

    This singleton-like manager handles:
    - ChromaDB client initialization
    - Embedding function configuration
    - Collection management with cosine distance
    - Shared utility methods (chunking, token validation)
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Block direct instantiation of RAGManager.

        RAGManager must be accessed via RAGProvider.get_manager().
        Direct instantiation is forbidden to ensure proper singleton enforcement.
        """
        raise RuntimeError(
            "RAGManager must be accessed via RAGProvider.get_manager(). "
            "Never instantiate RAGManager directly."
        )

    def __init__(self, *args, **kwargs):
        """Block direct initialization.

        This is a safety net - __new__ should have already blocked instantiation.
        """
        raise RuntimeError(
            "RAGManager must be accessed via RAGProvider.get_manager(). "
            "Never instantiate RAGManager directly."
        )

        print("Initializing RAG System...")
        start_time = time.time()

        # Configurable API settings
        self.persist_path = persist_path or config.CHROMA_PATH
        self.api_url = api_url or config.EMBEDDING_URL
        self.embedding_model = embedding_model or config.EMBEDDING_MODEL if hasattr(config, 'EMBEDDING_MODEL') else get_embedding_model()
        self.api_key = api_key or config.EMBEDDING_API_KEY

        os.makedirs(self.persist_path, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=self.persist_path)

        # Initialize embedding function FIRST (needed for dimension detection)
        self.embedding_fn = AIEmbeddingFunction(
            api_url=self.api_url,
            model_name=self.embedding_model,
            api_key=self.api_key
        )

        # Get embedding dimension AFTER embedding_fn is initialized
        self.embedding_dimension = self._get_embedding_dimension()

        # In-memory cache for query embeddings — same query text = same embedding,
        # so we embed each unique query text only once per RAGManager lifetime.
        self._query_embedding_cache: dict = {}

        self._initialized = True
        log_event("rag_manager_initialized", {
            "persist_path": self.persist_path,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension
        })

    def _get_embedding_dimension(self) -> int:
        """Get the embedding dimension by making a test call."""
        try:
            test_text = ["test"]
            embeddings = self.embedding_fn(test_text)
            return len(embeddings[0])
        except Exception as e:
            log_event("rag_embedding_dimension_error", {"error": str(e)})
            # Default to common dimensions if test fails
            return 384  # embeddinggemma-300m default

    def _drop_collection(self, name: str) -> bool:
        """Drop a collection by name."""
        try:
            self.client.delete_collection(name=name)
            log_event("rag_collection_dropped", {"collection": name})
            return True
        except Exception as e:
            log_event("rag_drop_collection_error", {"error": str(e), "collection": name})
            return False

    def _get_collection_dimension(self, collection_name: str) -> int:
        """Get the embedding dimension of an existing collection by sampling."""
        try:
            coll = self.client.get_collection(name=collection_name)
            # Get a small sample to check embedding dimension
            sample = coll.get(limit=1, include=["embeddings"])
            if sample and sample.get('embeddings'):
                for emb in sample['embeddings']:
                    if emb and len(emb) > 0:
                        return len(emb)
            # Collection exists but has no embeddings - return -1 to force reset
            return -1
        except Exception as e:
            log_event("rag_collection_dimension_error", {
                "error": str(e),
                "collection": collection_name
            })
        return 0

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None
        cls._initialized = False

    @classmethod
    def drop_all_collections(cls, persist_path=None):
        """Drop all RAG collections. Use when changing embedding models.

        Args:
            persist_path: Path to ChromaDB data directory
        """
        import chromadb
        client = chromadb.PersistentClient(path=persist_path or config.CHROMA_PATH)

        for coll_name in ["file_store", "research_store"]:
            try:
                client.delete_collection(name=coll_name)
                log_event("rag_collection_reset", {"collection": coll_name, "action": "dropped"})
            except Exception as e:
                log_event("rag_collection_reset_error", {"collection": coll_name, "error": str(e)})

    # -------------------------------------------------------------------------
    # Collection Management
    # -------------------------------------------------------------------------

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get or create a collection with L2 (Euclidean) distance."""
        return self._ensure_l2_collection(name)

    def _ensure_l2_collection(self, name: str) -> chromadb.Collection:
        """Ensure the collection exists with L2 (Euclidean) distance.

        If an old collection exists with cosine distance, migrate the data
        to a new L2-based collection since BM25 only works with L2.

        If an old collection exists with a different metric,
        migrate the data to a new L2-based collection.

        If an old collection exists with a different embedding dimension,
        drop and recreate the collection.
        """
        try:
            existing = self.client.get_collection(name=name)
            coll_meta = existing.metadata or {}

            # Check if embedding model has changed since collection was created
            stored_model = coll_meta.get("embedding_model")
            if stored_model and stored_model != self.embedding_model:
                log_event("rag_model_change_detected", {
                    "collection": name,
                    "stored_model": stored_model,
                    "current_model": self.embedding_model
                })
                self._drop_collection(name)
                existing = None  # Force recreation below
        except (ValueError, Exception):
            existing = None

        # If collection doesn't exist, create it with proper metadata
        if existing is None:
            return self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={
                    "hnsw:space": "l2",
                    "embedding_model": self.embedding_model,
                    "embedding_dimension": self.embedding_dimension
                }
            )

        # FIRST check embedding dimension mismatch (before hnsw:space checks)
        # This is the critical check that fixes "Collection expecting embedding with dimension of 768, got 384"
        expected_dim = self._get_embedding_dimension()
        actual_dim = self._get_collection_dimension(name)

        if actual_dim > 0 and actual_dim != expected_dim:
            log_event("rag_embedding_dimension_mismatch", {
                "collection": name,
                "expected_dimension": expected_dim,
                "actual_dimension": actual_dim
            })
            # Drop and recreate collection with correct dimension
            self._drop_collection(name)
            return self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_fn,
                metadata={
                    "hnsw:space": "l2",
                    "embedding_model": self.embedding_model,
                    "embedding_dimension": self.embedding_dimension
                }
            )

        coll_meta = existing.metadata or {}
        if coll_meta.get("hnsw:space") == "cosine":
            # Migrate cosine collections to L2 - BM25 requires L2 distance
            return self._migrate_collection_to_l2(existing)

        # Migration needed for other non-L2 metrics
        if coll_meta.get("hnsw:space") != "l2":
            return self._migrate_collection_to_l2(existing)

        return existing

    def _ensure_l2_collections(self, name: str) -> tuple:
        """Create and return vector and BM25 collections for hybrid search.

        Creates two separate collections:
        - {name}_vector: stores documents with our custom 768-dim embeddings
        - {name}_bm25: stores documents with ChromaDB's default 384-dim all-MiniLM

        If an old single collection exists (e.g., "file_store" without "_vector" suffix),
        migrates its data to the new dual collection setup.

        Returns: (vector_collection, bm25_collection)
        """
        # Check if old single collection exists and needs migration
        try:
            old_coll = self.client.get_collection(name=name)
            if old_coll.count() > 0:
                log_event("rag_dual_collection_migration_detected", {
                    "collection": name,
                    "count": old_coll.count()
                })
                self._migrate_to_dual_collections(name)
        except Exception:
            # No old collection exists, that's fine
            pass

        # Vector collection with our embedding function (768-dim)
        vector_coll = self.client.get_or_create_collection(
            name=f"{name}_vector",
            embedding_function=self.embedding_fn,
            metadata={
                "hnsw:space": "l2",
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension
            }
        )

        # BM25 collection with ChromaDB's default embedding (all-MiniLM, 384-dim)
        # No explicit embedding_fn - ChromaDB uses its built-in all-MiniLM
        bm25_coll = self.client.get_or_create_collection(
            name=f"{name}_bm25",
            metadata={"hnsw:space": "l2"}  # No embedding_fn - uses all-MiniLM default
        )

        return vector_coll, bm25_coll

    def _migrate_to_dual_collections(self, name: str):
        """Migrate existing single collection to dual collection setup.

        Args:
            name: Name of the old collection (e.g., "file_store")
        """
        try:
            old_coll = self.client.get_collection(name=name)
            old_count = old_coll.count()

            if old_count == 0:
                # No data to migrate, just drop
                self.client.delete_collection(name=name)
                log_event("rag_dual_collection_migration", {
                    "collection": name,
                    "action": "dropped_empty"
                })
                return

            # Get all data from old collection
            old_data = old_coll.get(include=["documents", "metadatas", "embeddings"])
            docs = old_data.get('documents', [])
            metas = old_data.get('metadatas', [])
            ids = old_data.get('ids', [])
            embeddings = old_data.get('embeddings', [])

            log_event("rag_dual_collection_migration_start", {
                "collection": name,
                "migrated_count": len(ids)
            })

            # Drop old collection
            self.client.delete_collection(name=name)

            # Create new dual collections
            vector_coll, bm25_coll = self._ensure_l2_collections(name)

            # Re-store to both collections
            if embeddings and len(embeddings) > 0:
                # We have embeddings - use them for vector collection
                vector_coll.upsert(documents=docs, metadatas=metas, ids=ids, embeddings=embeddings)
            else:
                # No embeddings - re-embed using our embedding function
                new_embeddings = self.embed_texts(docs, task="document")
                vector_coll.upsert(documents=docs, metadatas=metas, ids=ids, embeddings=new_embeddings)

            # Store to BM25 collection (ChromaDB computes embeddings internally)
            bm25_coll.upsert(documents=docs, metadatas=metas, ids=ids)

            log_event("rag_dual_collection_migration_complete", {
                "collection": name,
                "migrated_count": len(ids)
            })

        except Exception as e:
            log_event("rag_dual_collection_migration_error", {
                "collection": name,
                "error": str(e)
            })
            # Don't raise - let the application continue with empty collections

    def _migrate_collection_to_l2(self, old_collection: chromadb.Collection) -> chromadb.Collection:
        """Migrate collection data to a new L2-based collection."""
        try:
            coll_meta = old_collection.metadata or {}
            count = old_collection.count()
            old_data = old_collection.get(include=["documents", "metadatas"])

            docs = old_data.get('documents', [])
            metas = old_data.get('metadatas', [])
            ids = old_data.get('ids', [])

            log_event("rag_collection_migration_start", {
                "collection": old_collection.name,
                "old_space": coll_meta.get("hnsw:space", "cosine"),
                "found_count": len(ids),
                "actual_count": count
            })

            if count > 0 and not ids:
                log_event("rag_migration_error", {"error": "Count > 0 but get() returned no IDs. Aborting deletion to prevent data loss."})
                return old_collection

            self.client.delete_collection(name=old_collection.name)

            new_coll = self.client.create_collection(
                name=old_collection.name,
                embedding_function=self.embedding_fn,
                metadata={
                    "hnsw:space": "l2",
                    "embedding_model": self.embedding_model,
                    "embedding_dimension": self.embedding_dimension
                }
            )

            if ids:
                batch_size = config.RAG_MIGRATION_BATCH_SIZE
                for i in range(0, len(ids), batch_size):
                    try:
                        new_coll.add(
                            ids=ids[i:i+batch_size],
                            documents=docs[i:i+batch_size],
                            metadatas=metas[i:i+batch_size]
                        )
                    except Exception as e:
                        log_event("rag_migration_batch_error", {"error": str(e), "index": i})

                log_event("rag_migration_complete", {"collection": old_collection.name, "migrated": len(ids)})

            return new_coll

        except Exception as e:
            log_event("rag_migration_critical_failure", {"error": str(e)})
            return self.client.get_or_create_collection(
                name=old_collection.name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "l2"}
            )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def chunk_text(self, text: str, max_chars: int = None, max_tokens: int = None) -> list:
        """Split text into chunks for embedding.

        Guarantees that no chunk exceeds max_tokens. Structure (paragraphs, sentences)
        is respected when possible, but token limits always take priority.

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk (fallback, deprecated)
            max_tokens: Maximum tokens per chunk (primary limit)

        Returns:
            List of text chunks, each within max_tokens limit
        """
        if max_tokens is None:
            if max_chars is None:
                max_chars = config.RAG_CHUNK_MAX_CHARS
            # Fallback to character-based chunking if no token limit
            return self._chunk_by_chars(text, max_chars)

        # Empty or single token text
        if not text or len(text.strip()) == 0:
            return [text] if text else []

        # Single chunk fits
        if count_tokens(text) <= max_tokens:
            return [text]

        chunks = []
        current_chunk = ""
        current_tokens = 0

        # Split by paragraphs first
        paragraphs = text.split('\n\n')

        for para in paragraphs:
            para_tokens = count_tokens(para)
            para_stripped = para.strip()

            # Paragraph fits as-is
            if current_tokens + para_tokens <= max_tokens:
                if current_chunk:
                    current_chunk += "\n\n" + para_stripped
                else:
                    current_chunk = para_stripped
                current_tokens += para_tokens
            else:
                # Current chunk is full, save it
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_tokens = 0

                # If paragraph itself exceeds limit, split it
                if para_tokens > max_tokens:
                    # Split paragraph into sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para_stripped)
                    sentence_chunk = ""
                    sentence_tokens = 0

                    for sent in sentences:
                        sent_tokens = count_tokens(sent)

                        # Sentence fits as-is
                        if sentence_tokens + sent_tokens <= max_tokens:
                            if sentence_chunk:
                                sentence_chunk += " " + sent
                            else:
                                sentence_chunk = sent
                            sentence_tokens += sent_tokens
                        else:
                            # Sentence chunk full, save it
                            if sentence_chunk:
                                chunks.append(sentence_chunk)
                                sentence_chunk = ""
                                sentence_tokens = 0

                            # If sentence still exceeds limit, split by words
                            if sent_tokens > max_tokens:
                                words = sent.split()
                                word_chunk = ""
                                word_tokens = 0

                                for word in words:
                                    word_tokens_count = count_tokens(word)

                                    if word_tokens + word_tokens_count > max_tokens:
                                        if word_chunk:
                                            chunks.append(word_chunk)
                                            word_chunk = ""
                                            word_tokens = 0

                                    word_chunk += (" " if word_chunk else "") + word
                                    word_tokens += word_tokens_count

                                # Save remaining words
                                if word_chunk:
                                    chunks.append(word_chunk)
                                    word_chunk = ""
                                    word_tokens = 0
                            else:
                                sentence_chunk = sent
                                sentence_tokens = sent_tokens

                    # Save remaining sentence chunk
                    if sentence_chunk:
                        chunks.append(sentence_chunk)
                else:
                    # Paragraph fits, start new chunk
                    current_chunk = para_stripped
                    current_tokens = para_tokens

        # Save remaining chunk
        if current_chunk:
            chunks.append(current_chunk)

        # Final hard-limit guarantee - split any monolithic units recursively by tokens
        final_chunks = []
        for chunk in chunks:
            if count_tokens(chunk) <= max_tokens:
                final_chunks.append(chunk)
            else:
                final_chunks.extend(split_text_by_tokens(chunk, max_tokens))

        return final_chunks if final_chunks else [text]

    def _chunk_by_chars(self, text: str, max_chars: int) -> list:
        """Fallback chunking by character count.

        Args:
            text: Text to chunk
            max_chars: Maximum characters per chunk

        Returns:
            List of text chunks
        """
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

        # Final hard-limit guarantee for character-based fallback
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final_chunks.append(chunk)
            else:
                # Divide by character window as last resort
                for i in range(0, len(chunk), max_chars):
                    final_chunks.append(chunk[i:i + max_chars])

        return final_chunks if final_chunks else [text]

    def validate_and_truncate(self, text: str, max_tokens: int, context: dict = None) -> str:
        """Validate token count - chunking should guarantee limits are never exceeded.

        This method serves as a safety check. If a chunk exceeds max_tokens, it indicates
        a bug in the chunking logic that needs to be fixed.

        Args:
            text: Text to validate
            max_tokens: Maximum tokens allowed
            context: Optional context dict for logging

        Returns:
            Original text (chunking must guarantee limits)
        """
        if not text or len(text.strip()) == 0:
            return ""

        token_count = count_tokens(text)
        if token_count > max_tokens:
            if context:
                log_event(f"rag_{context.get('type', 'validation')}_limit_exceeded", {
                    **context,
                    "original_tokens": token_count,
                    "max_tokens": max_tokens
                })
            # Chunking should guarantee limits - if this happens, chunking has a bug
            # Return the text anyway; the embedding may fail but that's expected
            return text
        return text

    def embed_texts(self, texts: list, task: str = "document") -> list:
        """Embed a list of texts.

        Args:
            texts: List of text strings to embed
            task: Task type ("document" or "query")

        Returns:
            List of embeddings
        """
        # Query embeddings are cached in memory: the same query text always
        # produces the same embedding. During a grid search, identical queries
        # are embedded 512 times — caching eliminates all but the first call.
        # Document embeddings are NOT cached to avoid unbounded memory growth.
        if task == "query":
            results = []
            uncached_indices = []
            uncached_texts = []

            for i, text in enumerate(texts):
                key = text.strip() if text else ""
                cached = self._query_embedding_cache.get(key)
                if cached is not None:
                    results.append(cached)
                else:
                    results.append(None)  # placeholder
                    uncached_indices.append(i)
                    uncached_texts.append(text)

            if uncached_texts:
                validated = [t if t and len(t.strip()) > 0 else "" for t in uncached_texts]
                try:
                    if hasattr(self.embedding_fn, '_embed_with_task'):
                        new_embeddings = self.embedding_fn._embed_with_task(validated, task=task)
                    else:
                        new_embeddings = self.embedding_fn(validated)
                except Exception as e:
                    log_event("rag_embedding_error", {"error": str(e), "task": task})
                    raise

                for idx, emb in zip(uncached_indices, new_embeddings):
                    key = texts[idx].strip() if texts[idx] else ""
                    self._query_embedding_cache[key] = emb
                    results[idx] = emb

            return results

        # Document embeddings — no cache, send directly
        validated = []
        for text in texts:
            if text and len(text.strip()) > 0:
                validated.append(text)
            else:
                validated.append("")

        try:
            if hasattr(self.embedding_fn, '_embed_with_task'):
                embeddings = self.embedding_fn._embed_with_task(validated, task=task)
            else:
                embeddings = self.embedding_fn(validated)
            return embeddings
        except Exception as e:
            log_event("rag_embedding_error", {"error": str(e), "task": task})
            raise

    def get_collection(self, name: str) -> chromadb.Collection:
        """Get an existing collection by name."""
        return self.client.get_collection(name=name)

    def delete_collection(self, name: str) -> bool:
        """Delete a collection by name."""
        try:
            self.client.delete_collection(name=name)
            return True
        except Exception as e:
            log_event("rag_delete_collection_error", {"error": str(e), "collection": name})
            return False


# =============================================================================
# RAG Store Base Class
# =============================================================================

class RAGStore:
    """
    Base class for all RAG store implementations.

    Provides a common interface for:
    - Storing items with metadata
    - Retrieving by query
    - Deleting items
    - Cleanup operations

    Uses dual collection pattern for hybrid search:
    - vector_collection: custom embeddings (768-dim for embeddinggemma)
    - bm25_collection: ChromaDB's all-MiniLM (384-dim for BM25)
    """

    def __init__(self, rag_manager: RAGManager, collection_name: str):
        self.rag_manager = rag_manager
        self.collection_name = collection_name
        self.vector_collection, self.bm25_collection = rag_manager._ensure_l2_collections(collection_name)

    def store(self, documents: list, metadatas: list, ids: list = None) -> list:
        """Store documents with metadata to both vector and BM25 collections.

        Args:
            documents: List of document texts
            metadatas: List of metadata dicts
            ids: Optional list of IDs (auto-generated if not provided)

        Returns:
            List of document IDs
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(documents))]

        embeddings = self.rag_manager.embed_texts(documents, task="document")

        # Batch size for ChromaDB upsert (avoiding the 5461 SQLite limit)
        # We use a safe margin below 5461
        CHROMA_UPSERT_BATCH_SIZE = 5000
        
        for i in range(0, len(ids), CHROMA_UPSERT_BATCH_SIZE):
            batch_end = i + CHROMA_UPSERT_BATCH_SIZE
            
            # Store to vector collection with our custom embeddings
            self.vector_collection.upsert(
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end]
            )
            
            # Store to BM25 collection
            self.bm25_collection.upsert(
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
                ids=ids[i:batch_end]
            )

        return ids

    def retrieve_by_query(self, query: str, n_results: int = 5, where: dict = None,
                          hybrid: bool = True, fetch_multiplier: int = None) -> list:
        """Retrieve documents by semantic query with optional hybrid search.

        Uses dual collection pattern:
        - Vector search uses custom 768-dim embeddings (embeddinggemma)
        - BM25 search uses ChromaDB's 384-dim all-MiniLM embeddings

        Args:
            query: Search query text
            n_results: Number of results to return
            where: Optional metadata filter
            hybrid: If True, combine BM25 keyword search with vector search

        Returns:
            List of {text, metadata, score, rank_fusion} dicts
        """
        query_emb = self.rag_manager.embed_texts([query], task="query")[0]

        # Use fetch_multiplier to control how many candidates are retrieved
        # before re-ranking and deduplication; default is from config.
        multiplier = fetch_multiplier if fetch_multiplier is not None else config.RAG_FETCH_MULTIPLIER
        fetch_k = n_results * multiplier

        # Vector search using our custom 768-dim embeddings
        vector_results = self.vector_collection.query(
            query_embeddings=[query_emb],
            n_results=fetch_k,
            where=where,
            include=["documents", "metadatas", "embeddings", "distances"]
        )

        # BM25 search using ChromaDB's internal 384-dim all-MiniLM embeddings
        bm25_results = self.bm25_collection.query(
            query_texts=[query],
            n_results=fetch_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # Convert results to doc dicts
        vector_docs = self._results_to_docs(vector_results, source="vector")
        bm25_docs = self._results_to_docs(bm25_results, source="bm25")

        # Apply a very loose pre-filter to eliminate outright noise (score < 0.05).
        # The real quality gate (config.RAG_MIN_SEMANTIC_SCORE) is applied AFTER
        # RRF fusion so that a weak vector match can still be surfaced by BM25 rank.
        NOISE_FLOOR = 0.05
        vector_docs = [d for d in vector_docs if d.get('score', 0) >= NOISE_FLOOR]

        # If hybrid search is disabled, apply semantic filter and return vector-only results
        if not hybrid or not config.HYBRID_SEARCH_ENABLED:
            if config.RAG_MIN_SEMANTIC_SCORE:
                vector_docs = [d for d in vector_docs if d.get('score', 0) >= config.RAG_MIN_SEMANTIC_SCORE]
            results = self._score_only_results(vector_docs, n_results * 2)
            # Log RAG query metrics for non-hybrid path
            log_event("rag_query", {
                "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
                "collection": self.collection_name,
                "n_results": n_results,
                "hybrid": hybrid,
                "latency_ms": None,
                "vector_results": len(vector_docs),
                "bm25_results": 0,
                "fused_results": len(results)
            })
            return results

        # Fuse results using Reciprocal Rank Fusion (RRF), then deduplicate
        start_time = time.time()
        fused = self._rrf_fuse_results(vector_docs, bm25_docs, n_results)

        # Post-fusion semantic filter: drop results whose vector cosine similarity
        # is below the configured threshold. BM25-only results (no vector_score)
        # are not filtered because they won't have a meaningful cosine score.
        if config.RAG_MIN_SEMANTIC_SCORE:
            fused = [
                r for r in fused
                if r['rank_fusion'].get('vector_score') is None
                or r['rank_fusion'].get('vector_score', 0.0) >= config.RAG_MIN_SEMANTIC_SCORE
            ]

        fused = self._dedup_results(fused, n_results)

        # Log RAG query metrics
        log_event("rag_query", {
            "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
            "collection": self.collection_name,
            "n_results": n_results,
            "hybrid": hybrid,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "vector_results": len(vector_docs),
            "bm25_results": len(bm25_docs),
            "fused_results": len(fused)
        })

        return fused

    def _results_to_docs(self, results: dict, source: str) -> list:
        """Convert ChromaDB query results to doc dicts.

        Args:
            results: ChromaDB query result dict
            source: "vector" or "bm25" (for scoring)

        Returns:
            List of doc dicts with text, metadata, score
        """
        docs = []
        if results and results.get('documents') and results['documents'][0]:
                for id, doc, meta, dist in zip(
                    results['ids'][0],
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                ):
                    # BM25 distance: normalize using 1/(1+dist) — distance is not L2
                    if source == "bm25":
                        score = 1.0 / (1.0 + dist)
                    else:
                        # Vector distance is L2 on unit-normalized embeddings.
                        # For unit vectors: cos_sim = 1 - L2²/2
                        # This maps to a proper [0, 1] cosine similarity score.
                        score = max(0.0, 1.0 - (dist * dist) / 2.0)

                    doc_dict = {
                        "id": id,  # Unique ChromaDB ID (e.g. file_id_chunk_N)
                        "file_id": meta.get("file_id", ""), # Parent file ID for evaluation
                        "text": doc,
                        "metadata": meta,
                        "score": score,
                        "source": source
                    }

                    # Only include embedding for vector results
                    if source == "vector" and results.get('embeddings'):
                        embeddings_list = results['embeddings'][0] if isinstance(results['embeddings'], list) else results['embeddings']
                        if embeddings_list is not None and len(embeddings_list) > 0:
                            # Use enumerate to find the index (works with numpy arrays too)
                            emb_idx = 0
                            for i, d in enumerate(results['documents'][0]):
                                if d == doc:
                                    emb_idx = i
                                    break
                            doc_dict["embedding"] = embeddings_list[emb_idx]

                    docs.append(doc_dict)
        return docs

    # Standard RRF smoothing constant — must be separate from `n_results`.
    # The conventional value of 60 (from Cormack et al. 2009) prevents the
    # score from collapsing to near-zero for low-ranked but still relevant docs.
    _RRF_K = 60

    def _rrf_fuse_results(self, vector_docs: list, bm25_docs: list, n_results: int = 10) -> list:
        """Fuse results using Reciprocal Rank Fusion (RRF).

        RRF combines rankings from multiple retrieval methods by computing
        a score based on the rank of each document in each ranking.

        Uses a fixed smoothing constant (_RRF_K = 60) that is separate from
        `n_results` so rank sensitivity is consistent regardless of how many
        results are requested.

        Args:
            vector_docs: Documents from vector search
            bm25_docs: Documents from BM25 search
            n_results: Number of final results to return

        Returns:
            Fused and ranked list of documents (length <= n_results, before dedup)
        """
        rrf_k = self._RRF_K  # Smoothing constant — do NOT conflate with n_results
        all_docs = {}

        # Add vector search results with rank
        for i, doc in enumerate(vector_docs):
            # Use full content with truncation for hashing to avoid collisions
            doc_content = doc['text'].encode('utf-8')[:1000]
            doc_hash = int(hashlib.sha256(doc_content).hexdigest(), 16)
            # Preserve id from original doc
            doc_id = doc.get('id', '')
            if doc_hash not in all_docs:
                all_docs[doc_hash] = {
                    "id": doc_id,
                    "file_id": doc.get("file_id"),
                    "text": doc['text'],
                    "metadata": doc['metadata'],
                    "embedding": doc.get('embedding'),
                    "vector_rank": i + 1,
                    "bm25_rank": None,
                    "vector_score": doc.get('score', 0),
                    "bm25_score": None
                }
            else:
                all_docs[doc_hash]["vector_rank"] = i + 1
                all_docs[doc_hash]["vector_score"] = doc.get('score', 0)

        # Add BM25 results with rank
        for i, doc in enumerate(bm25_docs):
            # Use full content with truncation for hashing to avoid collisions
            doc_content = doc['text'].encode('utf-8')[:1000]
            doc_hash = int(hashlib.sha256(doc_content).hexdigest(), 16)
            # Preserve id from original doc
            doc_id = doc.get('id', '')
            if doc_hash not in all_docs:
                all_docs[doc_hash] = {
                    "id": doc_id,
                    "file_id": doc.get("file_id"),
                    "text": doc['text'],
                    "metadata": doc['metadata'],
                    "embedding": doc.get('embedding'),
                    "vector_rank": None,
                    "bm25_rank": i + 1,
                    "vector_score": None,
                    "bm25_score": doc.get('score', 0)
                }
            else:
                all_docs[doc_hash]["bm25_rank"] = i + 1
                all_docs[doc_hash]["bm25_score"] = doc.get('score', 0)

        # Compute RRF score for each document
        fused = []
        for doc_id, doc in all_docs.items():
            vector_rank = doc.get("vector_rank") or float('inf')
            bm25_rank = doc.get("bm25_rank") or float('inf')

            # Pure RRF formula: score = 1/(K + rank_vector) + 1/(K + rank_bm25)
            # Using pure rank-based fusion avoids mixing incomparable BM25 and
            # vector distance scores, which live on completely different scales.
            rrf_score = 1.0 / (rrf_k + vector_rank) + 1.0 / (rrf_k + bm25_rank)
            final_score = rrf_score

            # Apply time decay to final score.
            # RAG_DECAY_RATE is expressed as decay-per-DAY (e.g. 0.10 means
            # a document loses ~10 % of its score per day).  Dividing the raw
            # age in seconds by 86 400 keeps the exponent in a sensible range:
            #   rate=0.10, age=10 days → exp(-1.0) ≈ 0.37  (noticeable decay)
            #   rate=0.10, age=1  day  → exp(-0.1) ≈ 0.90  (very fresh)
            # With the old per-second formula even rate=0.01 over 1 day gave
            # exp(−864) ≈ 0, making all non-freshly-stored results collapse.
            timestamp = doc.get("metadata", {}).get("timestamp", 0)
            if timestamp > 0:
                current_time = time.time()
                age_days = (current_time - timestamp) / 86400.0
                time_decay = math.exp(-config.RAG_DECAY_RATE * age_days)
                final_score *= time_decay

            fused.append({
                "id": doc.get("id", ""),
                "file_id": doc.get("file_id"),
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": final_score,
                "embedding": doc.get("embedding"),
                "rank_fusion": {
                    "rrf_score": rrf_score,
                    "vector_rank": doc.get("vector_rank"),
                    "bm25_rank": doc.get("bm25_rank"),
                    # Preserve individual scores for post-fusion semantic filter
                    "vector_score": doc.get("vector_score"),
                    "bm25_score": doc.get("bm25_score"),
                }
            })

        # Sort by score and return top n_results (dedup happens in the caller)
        fused.sort(key=lambda x: x['score'], reverse=True)
        return fused[:n_results]

    def _dedup_results(self, docs: list, n_results: int) -> list:
        """Remove near-duplicate chunks using cosine similarity on stored embeddings.

        Two chunks are considered duplicates when their cosine similarity exceeds
        config.RAG_DEDUP_THRESHOLD.  The higher-scored chunk is always kept.
        For results without embeddings (BM25-only), text fingerprint dedup is used
        as a fallback to ensure RAG_DEDUP_THRESHOLD affects all results.

        Args:
            docs: Ranked list of fused result dicts (must be sorted descending by score)
            n_results: Maximum number of results to return after deduplication

        Returns:
            Deduplicated list of result dicts (length <= n_results)
        """
        threshold = config.RAG_DEDUP_THRESHOLD
        kept = []
        kept_embeddings = []
        kept_text_fingerprints = set()

        for doc in docs:
            emb = doc.get("embedding")

            if threshold >= 1.0:
                # Dedup disabled — keep everything
                kept.append(doc)
                if len(kept) >= n_results:
                    break
                continue

            if emb is not None:
                # Embedding-based dedup (cosine similarity)
                is_duplicate = False
                for kept_emb in kept_embeddings:
                    sim = _cosine_similarity(emb, kept_emb)
                    if sim >= threshold:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    kept.append(doc)
                    kept_embeddings.append(emb)
                    # Also track text fingerprint for cross-check
                    kept_text_fingerprints.add(doc['text'][:200])

            else:
                # Text-fingerprint dedup for BM25-only results (no embedding available)
                # Uses first 200 chars as a fast approximate duplicate detector
                text_fp = doc['text'][:200]
                if text_fp not in kept_text_fingerprints:
                    kept.append(doc)
                    kept_text_fingerprints.add(text_fp)

            if len(kept) >= n_results:
                break

        return kept

    def _score_only_results(self, docs: list, k: int) -> list:
        """Return top-k results based on vector score only."""
        docs.sort(key=lambda x: x.get('score', 0), reverse=True)
        return docs[:k]

    def retrieve_by_id(self, doc_id: str) -> dict:
        """Retrieve a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            {text, metadata} dict or None
        """
        # Try vector collection (authoritative), fall back to BM25
        results = self.vector_collection.get(ids=[doc_id])
        if not results or not results.get('documents'):
            results = self.bm25_collection.get(ids=[doc_id])
        if not results or not results.get('documents'):
            return None

        return {
            "text": results['documents'][0],
            "metadata": results['metadatas'][0]
        }

    def delete(self, ids: list) -> bool:
        """Delete documents by ID from both collections.

        Args:
            ids: List of document IDs to delete

        Returns:
            True if successful
        """
        try:
            self.vector_collection.delete(ids=ids)
            self.bm25_collection.delete(ids=ids)
            return True
        except Exception as e:
            log_event("rag_delete_error", {"error": str(e), "collection": self.collection_name})
            return False

    def cleanup(self, where: dict) -> int:
        """Delete documents matching a filter from both collections.

        Args:
            where: Metadata filter

        Returns:
            Number of deleted documents
        """
        try:
            # Get IDs from vector collection (authoritative)
            vector_results = self.vector_collection.get(where=where)
            vector_ids = vector_results.get('ids', []) if vector_results else []

            # Get IDs from BM25 collection
            bm25_results = self.bm25_collection.get(where=where)
            bm25_ids = bm25_results.get('ids', []) if bm25_results else []

            # Delete from both collections
            if vector_ids:
                self.vector_collection.delete(ids=vector_ids)
            if bm25_ids:
                self.bm25_collection.delete(ids=bm25_ids)

            return max(len(vector_ids), len(bm25_ids))
        except Exception as e:
            log_event("rag_cleanup_error", {"error": str(e), "collection": self.collection_name})
            return 0

    def list_all(self, where: dict = None, limit: int = None) -> list:
        """List all documents from vector collection.

        Args:
            where: Optional metadata filter
            limit: Optional result limit

        Returns:
            List of {id, text, metadata} dicts
        """
        try:
            results = self.vector_collection.get(where=where, limit=limit)
            if not results or not results.get('documents'):
                return []

            return [{
                "id": results['ids'][i],
                "text": results['documents'][i],
                "metadata": results['metadatas'][i]
            } for i in range(len(results['ids']))]
        except Exception:
            return []

    def count(self) -> int:
        """Count documents in vector collection (authoritative)."""
        try:
            return self.vector_collection.count()
        except:
            return 0


# =============================================================================
# AI Embedding Function (unchanged - kept for compatibility)
# =============================================================================

class AIEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_url=None, model_name=None, default_task="document", api_key=None):
        self.api_url = api_url or config.EMBEDDING_URL
        log_event("ai_embedding_fn_init", {"api_url": self.api_url, "model_name": model_name})
        # Model name must be provided - no fallbacks
        if model_name is None:
            raise ValueError("embedding_model must be explicitly provided")
        self.model_name = model_name
        self.default_task = default_task
        self.api_key = api_key

    def __call__(self, input):
        # Standard fallback for ChromaDB internal loops
        return self._embed_with_task(input, task=self.default_task)

    def _embed_with_task(self, input: list, task: str = None) -> list:
        """Embed text with task-specific formatting.

        Args:
            input: List of text strings to embed
            task: Task type ("query" or "document")

        Returns:
            List of embedding vectors
        """
        # Ensure base URL is clean and use /v1/embeddings
        base_url = self.api_url.rstrip("/")
        url = f"{base_url}/v1/embeddings"

        # Ensure input is a list of strings
        if isinstance(input, str):
            input = [input]

        # Determine token limit based on task type
        if task == "query":
            # Query embeddings use research token limit for retrieval
            max_tokens = config.EMBEDDING_MAX_TOKENS_RESEARCH
        elif self.default_task == "document":
            # Document embeddings - determine by RAG type based on model
            # Use a sensible default based on common embedding models
            max_tokens = config.EMBEDDING_MAX_TOKENS_CORE
        else:
            max_tokens = config.EMBEDDING_MAX_TOKENS_CORE

        # Process input - chunks should already respect token limits
        processed_input = []
        for item in input:
            if item and len(item.strip()) > 0:
                # Check token count - chunks should already be within limits
                token_count = count_tokens(item)
                if token_count > max_tokens:
                    # Final circuit-breaker: Truncate to avoid server rejection
                    # This logs as a critical error but allows the process to continue
                    processed_input.append(truncate_text_by_tokens(item, max_tokens))
                else:
                    processed_input.append(item)
            else:
                processed_input.append(item)

        # Format input with task-specific prefixes for embeddinggemma-300m
        formatted_input = []
        for item in processed_input:
            if task == "query":
                formatted_input.append(f"task: search result | query: {item}")
            else:
                formatted_input.append(f"title: none | text: {item}")

        # Embedding logic with batching support
        # Uses configurable batch size for hardware-specific tuning
        batch_size = config.EMBEDDING_BATCH_SIZE
        all_embeddings = []

        for i in range(0, len(formatted_input), batch_size):
            batch = formatted_input[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(formatted_input) + batch_size - 1) // batch_size

            # Log batch progress and stats
            batch_max_chars = max(len(s) for s in batch)
            log_event("rag_embedding_batch_start", {
                "batch": batch_num,
                "total_batches": total_batches,
                "items": len(batch),
                "max_chars": batch_max_chars,
                "url": url
            })

            payload = {
                "model": self.model_name,
                "input": batch
            }

            headers = {"Content-Type": "application/json"}
            api_key = self.api_key or config.EMBEDDING_API_KEY
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            print(f"    Embedding batch {batch_num}/{total_batches} ({len(batch)} items) to {url}...")
            
            try:
                start_time = time.time()
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=max(config.TIMEOUT_LLM_BLOCKING or 60, 120)  # Ensure at least 120s for embedding
                )
                
                elapsed = time.time() - start_time
                if response.status_code != 200:
                    log_event("rag_embedding_error", {
                        "url": url,
                        "status_code": response.status_code,
                        "response": response.text[:500],
                        "batch": batch_num
                    })
                    print(f"    [ERROR] Embedding failed with status {response.status_code} ({elapsed:.2f}s)")
                
                response.raise_for_status()
                data = response.json()
                
                # Handle potential variations in response format
                if "data" in data:
                    # Standard OpenAI format
                    batch_embeddings = [item["embedding"] for item in data["data"]]
                    all_embeddings.extend(batch_embeddings)
                elif isinstance(data, list):
                    # Simple list format
                    all_embeddings.extend(data)
                else:
                    # Unexpected format
                    log_event("rag_embedding_unexpected_response", {"keys": list(data.keys())})
                    all_embeddings.extend([[] for _ in batch])
                
                duration = time.time() - start_time
                log_llm_call(payload, f"Successfully embedded batch {batch_num} ({len(batch)} items).", self.model_name, duration_s=duration, call_type="embedding")
                
            except Exception as e:
                print(f"    [EXCEPTION] Embedding failed for batch {batch_num}: {e}")
                log_event("rag_embedding_exception", {
                    "url": url,
                    "error": str(e),
                    "batch": batch_num
                })
                raise e

        if len(all_embeddings) > 0:
            print(f"    [OK] Successfully embedded all {len(all_embeddings)} items.")
            
        return all_embeddings


# =============================================================================
# Research RAG - Ephemeral per-chat storage for Research passes
# =============================================================================

class ResearchRAG(RAGStore):
    """Ephemeral per-chat storage for Research passes.

    Extends RAGStore for shared RAG infrastructure while maintaining
    research-specific retrieval features.

    Requires a RAGManager instance - no fallback instantiation allowed.
    Get a manager via RAGProvider.get_manager().
    """

    def __init__(self, rag_manager: RAGManager = None, persist_path=None, api_url=None, embedding_model=None, api_key=None):
        # RAGManager MUST be provided - no fallback allowed
        if rag_manager is None:
            raise RuntimeError(
                "ResearchRAG requires a RAGManager instance. "
                "Get one via RAGProvider.get_manager() and pass it to ResearchRAG."
            )
        self.rag_manager = rag_manager
        super().__init__(self.rag_manager, "research_store")

    def store_chunk(self, chat_id, step_index, url, full_text, published_date=None):
        """Store a research chunk with deduplication.

        Args:
            chat_id: The research session ID
            step_index: Step index for filtering
            url: Source URL
            full_text: Content to store
            published_date: Optional published date

        Returns:
            Tuple of (success, token_count)
        """
        if not full_text or len(full_text.strip()) < 10:
            return False, 0

        import re
        import hashlib
        import time

        text_chunks = self.rag_manager.chunk_text(full_text, max_tokens=config.EMBEDDING_MAX_TOKENS_RESEARCH)
        total_tokens = 0
        any_success = False

        for i, chunk_text in enumerate(text_chunks):
            clean_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', chunk_text)
            clean_text = re.sub(r'https?://\S+', '', clean_text)
            clean_text = clean_text.strip()

            if len(clean_text) < 10:
                continue

            doc_id = hashlib.sha256((chat_id + url + clean_text).encode('utf-8')).hexdigest()

            try:
                # Check if exists in vector collection (authoritative)
                existing = self.vector_collection.get(ids=[doc_id])
                if existing and existing.get('ids'):
                    # Handle numpy array case
                    existing_ids = existing['ids'][0] if isinstance(existing['ids'], list) else existing['ids']
                    if len(existing_ids) > 0:
                        continue

                query_embedding = self.rag_manager.embed_texts([clean_text], task="document")[0]

                meta = {
                    "chat_id": chat_id,
                    "step_index": step_index,
                    "url": url,
                    "timestamp": time.time(),
                    "published_date": published_date or ""
                }

                # Store to vector collection with our embeddings
                self.vector_collection.upsert(
                    documents=[clean_text],
                    metadatas=[meta],
                    ids=[doc_id],
                    embeddings=[query_embedding]
                )

                # Store to BM25 collection (ChromaDB computes embeddings internally)
                self.bm25_collection.upsert(
                    documents=[clean_text],
                    metadatas=[meta],
                    ids=[doc_id]
                )

                total_tokens += count_tokens(clean_text)
                any_success = True

            except Exception as e:
                log_event("research_rag_store_error", {"error": str(e)})
                continue

        return any_success, total_tokens

    def get_all_chunks(self, chat_id, limit=None):
        """Retrieve all stored chunks for a session.

        Args:
            chat_id: The research session ID
            limit: Optional result limit

        Returns:
            List of chunk dicts with text, url, step_index, timestamp
        """
        try:
            results = self.vector_collection.get(
                where={"chat_id": chat_id},
                limit=limit
            )
            if not results or not results.get('documents'):
                return []

            # Handle both list and numpy array formats
            docs = results['documents'][0] if isinstance(results['documents'], list) else results['documents']
            metas = results['metadatas'][0] if isinstance(results['metadatas'], list) else results['metadatas']

            chunks = []
            for doc, meta in zip(docs, metas):
                chunks.append({
                    "text": doc,
                    "url": meta.get("url", ""),
                    "step_index": meta.get("step_index", 0),
                    "timestamp": meta.get("timestamp", 0)
                })

            chunks.sort(key=lambda x: (x['step_index'], x['timestamp']))
            return chunks
        except Exception as e:
            log_event("research_rag_retrieval_error", {"error": str(e)})
            return []

    def get_step_chunks(self, chat_id, step_index):
        """Retrieve all stored chunks for a specific step.

        Args:
            chat_id: The research session ID
            step_index: Step index to filter by

        Returns:
            List of chunk dicts
        """
        try:
            results = self.vector_collection.get(
                where={"$and": [{"chat_id": chat_id}, {"step_index": step_index}]}
            )
            if not results or not results.get('documents'):
                return []

            # Handle both list and numpy array formats
            docs = results['documents'][0] if isinstance(results['documents'], list) else results['documents']
            metas = results['metadatas'][0] if isinstance(results['metadatas'], list) else results['metadatas']

            chunks = []
            for doc, meta in zip(docs, metas):
                chunks.append({
                    "text": doc,
                    "url": meta.get("url", ""),
                    "step_index": meta.get("step_index", 0)
                })
            return chunks
        except Exception as e:
            log_event("research_rag_step_error", {"error": str(e)})
            return []

    def retrieve_for_report(self, chat_id, queries, max_tokens=None):
        """Multi-query semantic retrieval with dynamic token budgeting.

        Args:
            chat_id: The research session ID
            queries: List of {"query": str, "step_filter": int|None}
            max_tokens: Total token budget (uses config default)

        Returns:
            List of retrieved chunks sorted by relevance
        """
        if max_tokens is None:
            max_tokens = config.RESEARCH_MAX_TOKENS_RAG_CONTEXT

        if not queries:
            return self.get_all_chunks(chat_id)

        per_query_budget = max_tokens // len(queries)
        all_chunks = []
        seen_doc_ids = set()
        total_tokens = 0

        for q_info in queries:
            query_text = q_info["query"]
            step_filter = q_info.get("step_filter")

            try:
                query_emb = self.rag_manager.embed_texts([query_text], task="query")[0]

                if step_filter is not None:
                    where_clause = {"$and": [
                        {"chat_id": chat_id},
                        {"step_index": step_filter}
                    ]}
                else:
                    where_clause = {"chat_id": chat_id}

                # Vector search using custom embeddings
                results = self.vector_collection.query(
                    query_embeddings=[query_emb],
                    n_results=200,
                    where=where_clause,
                    include=["documents", "metadatas", "embeddings", "distances"]
                )

                if not results or not results.get('documents'):
                    continue

                # Handle both list and numpy array formats
                docs = results['documents'][0] if isinstance(results['documents'], list) else results['documents']
                metas = results['metadatas'][0] if isinstance(results['metadatas'], list) else results['metadatas']
                embs = results['embeddings'][0] if isinstance(results['embeddings'], list) else results['embeddings']
                dists = results['distances'][0] if isinstance(results['distances'], list) else results['distances']

                if not docs or len(docs) == 0:
                    continue

                query_tokens = 0
                for doc, meta, emb, dist in zip(docs, metas, embs, dists):
                    doc_content = doc[:200] + doc[-200:] if len(doc) > 400 else doc
                    doc_hash = hashlib.sha256(doc_content.encode('utf-8')).hexdigest()
                    if doc_hash in seen_doc_ids:
                        continue

                    chunk_tokens = count_tokens(doc)
                    if query_tokens + chunk_tokens > per_query_budget:
                        break
                    if total_tokens + chunk_tokens > max_tokens:
                        return all_chunks

                    similarity = 1.0 / (1.0 + dist)

                    all_chunks.append({
                        "text": doc,
                        "url": meta.get("url", ""),
                        "step_index": meta.get("step_index", 0),
                        "relevance": similarity,
                        "timestamp": meta.get("timestamp", 0),
                        "published_date": meta.get("published_date", "")
                    })
                    seen_doc_ids.add(doc_hash)
                    query_tokens += chunk_tokens
                    total_tokens += chunk_tokens

            except Exception as e:
                log_event("research_rag_query_error", {"error": str(e)})
                continue

        all_chunks.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return all_chunks

    def cleanup_chat(self, chat_id):
        """Delete all stored chunks for a given chat_id.

        Args:
            chat_id: The research session ID

        Returns:
            True if successful
        """
        return self.cleanup({"chat_id": chat_id})


# =============================================================================
# File RAG - File content storage with chunked embeddings
# =============================================================================

from backend.chunking import (
    detect_file_type,
    chunk_code_text,
    chunk_spreadsheet_text,
    chunk_mixed_text,
    chunk_document_text,
    extract_code_metadata,
    extract_document_metadata
)


class FileRAG(RAGStore):
    """File content storage with chunked embeddings for semantic search.

    Extends RAGStore for shared RAG infrastructure while maintaining
    file-specific storage and retrieval features.

    Features:
    - Content-based file type detection (code, document, spreadsheet, mixed)
    - Adaptive chunking strategies per file type
    - Rich metadata including line numbers, function names, section headers
    """

    def __init__(self, rag_manager: RAGManager = None, persist_path=None, api_url=None, embedding_model=None, api_key=None):
        """Initialize FileRAG.

        Requires a RAGManager instance - no fallback instantiation allowed.
        Get a manager via RAGProvider.get_manager().

        Args:
            rag_manager: Required RAGManager singleton instance
            persist_path, api_url, embedding_model, api_key: Ignored (kept for API compatibility)
        """
        # RAGManager MUST be provided - no fallback allowed
        if rag_manager is None:
            raise RuntimeError(
                "FileRAG requires a RAGManager instance. "
                "Get one via RAGProvider.get_manager() and pass it to FileRAG."
            )
        self.rag_manager = rag_manager
        super().__init__(self.rag_manager, "file_store")
        self._initialized = True

    def store_file(self, file_id, chat_id, content_text, filename=None, timestamp=None,
                   file_type_override=None):
        """Store a file's content with adaptive chunking and rich metadata.

        Args:
            file_id: Unique file identifier
            chat_id: Chat session ID
            content_text: File content to store
            filename: Original filename (for extension hint)
            timestamp: Optional Unix timestamp to record in chunk metadata.
                       When None (the default) time.time() is used, which is
                       the correct behaviour for all production callers.
                       Pass an explicit value in tests to simulate document age
                       without monkey-patching time.time.
            file_type_override: Optional explicit file type ('code', 'document', 'mixed',
                       'spreadsheet'). When provided, the classifier is bypassed entirely
                       and the supplied type drives both chunking strategy and stored
                       metadata. Intended for isolated RAG parameter evaluation where
                       classifier accuracy is assumed and must not be a confounding
                       variable. Production callers should never set this.

        Returns:
            List of stored document IDs
        """
        if not self._initialized:
            log_event("file_rag_not_initialized", {"file_id": file_id})
            return []

        if not content_text or len(content_text.strip()) < 50:
            return []

        # Detect file type from content, unless the caller supplied a known ground-truth.
        if file_type_override is not None:
            file_type = file_type_override
            detection_meta = {"overridden": True}
        else:
            file_type, detection_meta = detect_file_type(filename or "", content_text)

        # Choose chunking strategy based on detected (or overridden) type
        if file_type == 'spreadsheet':
            chunks = chunk_spreadsheet_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'row-based'
        elif file_type == 'code':
            chunks = chunk_code_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'syntax-aware'
        elif file_type == 'mixed':
            chunks = chunk_mixed_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'hybrid'
        else:  # document or unknown
            chunks = self.rag_manager.chunk_text(content_text, max_tokens=config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'paragraph-based'

        log_event("rag_file_chunking", {
            "file_id": file_id,
            "file_type": file_type,
            "chunk_strategy": chunk_strategy,
            "num_chunks": len(chunks)
        })

        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            doc_id = f"{file_id}_chunk_{i}"
            documents.append(chunk)

            # Build enhanced metadata based on file type
            metadata = {
                "file_id": file_id,
                "chat_id": chat_id,
                "chunk_index": i,
                # Use the caller-supplied timestamp when present (e.g. tests
                # injecting staggered ages), otherwise default to now.
                "timestamp": timestamp if timestamp is not None else time.time(),
                "file_type": file_type,
                "chunk_strategy": chunk_strategy
            }

            # Add file-type-specific metadata
            if file_type == 'code':
                # Extract code-specific metadata
                code_meta = extract_code_metadata(chunk)
                metadata.update({
                    "function_names": json.dumps(code_meta.get('function_names', [])),
                    "class_names": json.dumps(code_meta.get('class_names', [])),
                    "imports": json.dumps(code_meta.get('imports', [])),
                    "line_start": code_meta.get('line_start', i * 20),
                    "line_end": code_meta.get('line_end', (i + 1) * 20)
                })
            elif file_type == 'document':
                # Extract document metadata per-chunk
                chunk_metadata = extract_document_metadata(chunk)
                metadata.update({
                    "section_headers": json.dumps(chunk_metadata.get('section_headers', [])),
                    "subsection_headers": json.dumps(chunk_metadata.get('subsection_headers', []))
                })
            elif file_type == 'spreadsheet':
                # Spreadsheet metadata
                metadata.update({
                    "column_count": detection_meta.get('column_count', 0),
                    "column_headers": json.dumps(detection_meta.get('headers', [])),
                    "has_headers": detection_meta.get('has_headers', False),
                    "data_row_count": detection_meta.get('data_row_count', 0)
                })

            metadatas.append(metadata)
            ids.append(doc_id)

        try:
            return self.store(documents, metadatas, ids)
        except Exception as e:
            log_event("rag_file_store_error", {
                "file_id": file_id,
                "error": str(e),
                "num_chunks": len(documents)
            })
            return []

    def store_files_batch(self, files: list) -> list:
        """Store multiple files in a single bulk embedding call.

        Unlike calling store_file() N times (which sends N separate embedding
        requests), this method accumulates all chunks across all files first
        and then issues a single store() call. The embedder receives all chunks
        in one go, making it possible to saturate the CPU with a large batch.

        Args:
            files: List of dicts, each with keys:
                - file_id (str): Unique file identifier
                - chat_id (str): Chat session ID
                - content_text (str): File content
                - filename (str, optional): Original filename
                - timestamp (float, optional): Unix timestamp for the chunk metadata
                - file_type_override (str, optional): Skip classifier, use this type

        Returns:
            List of all stored document IDs across all files
        """
        if not self._initialized:
            log_event("file_rag_not_initialized", {"method": "store_files_batch"})
            return []

        STORAGE_BATCH_SIZE = 2000
        all_stored_ids: list = []
        
        # Accumulators for the current incremental batch
        batch_docs: list = []
        batch_metas: list = []
        batch_ids: list = []

        for file_spec in files:
            file_id   = file_spec['file_id']
            chat_id   = file_spec['chat_id']
            content_text = file_spec['content_text']
            filename  = file_spec.get('filename')
            timestamp = file_spec.get('timestamp')
            file_type_override = file_spec.get('file_type_override')

            if not content_text or len(content_text.strip()) < 50:
                continue

            # Detect / override file type
            if file_type_override is not None:
                file_type = file_type_override
                detection_meta = {"overridden": True}
            else:
                file_type, detection_meta = detect_file_type(filename or "", content_text)

            # Choose chunking strategy
            if file_type == 'spreadsheet':
                chunks = chunk_spreadsheet_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
                chunk_strategy = 'row-based'
            elif file_type == 'code':
                chunks = chunk_code_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
                chunk_strategy = 'syntax-aware'
            elif file_type == 'mixed':
                chunks = chunk_mixed_text(content_text, config.EMBEDDING_MAX_TOKENS_FILE)
                chunk_strategy = 'hybrid'
            else:
                chunks = self.rag_manager.chunk_text(content_text, max_tokens=config.EMBEDDING_MAX_TOKENS_FILE)
                chunk_strategy = 'paragraph-based'

            log_event("rag_file_chunking", {
                "file_id": file_id,
                "file_type": file_type,
                "chunk_strategy": chunk_strategy,
                "num_chunks": len(chunks)
            })

            for i, chunk in enumerate(chunks):
                doc_id = f"{file_id}_chunk_{i}"
                metadata = {
                    "file_id": file_id,
                    "chat_id": chat_id,
                    "chunk_index": i,
                    "timestamp": timestamp if timestamp is not None else time.time(),
                    "file_type": file_type,
                    "chunk_strategy": chunk_strategy
                }

                if file_type == 'code':
                    code_meta = extract_code_metadata(chunk)
                    metadata.update({
                        "function_names": json.dumps(code_meta.get('function_names', [])),
                        "class_names": json.dumps(code_meta.get('class_names', [])),
                        "imports": json.dumps(code_meta.get('imports', [])),
                        "line_start": code_meta.get('line_start', i * 20),
                        "line_end": code_meta.get('line_end', (i + 1) * 20)
                    })
                elif file_type == 'document':
                    chunk_metadata = extract_document_metadata(chunk)
                    metadata.update({
                        "section_headers": json.dumps(chunk_metadata.get('section_headers', [])),
                        "subsection_headers": json.dumps(chunk_metadata.get('subsection_headers', []))
                    })
                elif file_type == 'spreadsheet':
                    metadata.update({
                        "column_count": detection_meta.get('column_count', 0),
                        "column_headers": json.dumps(detection_meta.get('headers', [])),
                        "has_headers": detection_meta.get('has_headers', False),
                        "data_row_count": detection_meta.get('data_row_count', 0)
                    })

                batch_docs.append(chunk)
                batch_metas.append(metadata)
                batch_ids.append(doc_id)

                # Incremental flush to ChromaDB
                if len(batch_docs) >= STORAGE_BATCH_SIZE:
                    try:
                        stored_batch = self.store(batch_docs, batch_metas, batch_ids)
                        all_stored_ids.extend(stored_batch)
                    except Exception as e:
                        log_event("rag_file_store_partial_error", {
                            "error": str(e),
                            "num_attempted": len(batch_docs)
                        })
                    finally:
                        batch_docs = []
                        batch_metas = []
                        batch_ids = []

        # Flush final remaining chunks
        if batch_docs:
            try:
                stored_batch = self.store(batch_docs, batch_metas, batch_ids)
                all_stored_ids.extend(stored_batch)
            except Exception as e:
                log_event("rag_file_store_final_error", {
                    "error": str(e),
                    "num_attempted": len(batch_docs)
                })

        return all_stored_ids

    def retrieve_for_file(self, file_id, query, n_results=5, hybrid=True):
        """Retrieve relevant chunks for a specific file.

        Args:
            file_id: File identifier
            query: Search query
            n_results: Number of results to return
            hybrid: Enable hybrid search (BM25 + vector)

        Returns:
            List of retrieved chunks with scores (empty list if hybrid search fails)
        """
        where = {"file_id": file_id}
        try:
            results = self.retrieve_by_query(query, n_results=n_results, where=where, hybrid=hybrid)
            return results
        except RuntimeError as e:
            # BM25 not supported with cosine distance - return empty results
            # The error is already logged in retrieve_by_query
            log_event("rag_retrieval_fallback", {
                "file_id": file_id,
                "error": str(e),
                "retrieval_mode": "vector_only"
            })
            return []
        except Exception as e:
            # Log full error with traceback
            import traceback
            log_event("rag_retrieval_error", {
                "file_id": file_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return []

    def get_file_chunks(self, file_id):
        """Get all chunks for a specific file.

        Args:
            file_id: File identifier

        Returns:
            List of chunk dicts
        """
        return self.list_all(where={"file_id": file_id})

    def delete_file(self, file_id):
        """Delete all chunks for a specific file.

        Args:
            file_id: File identifier

        Returns:
            True if successful
        """
        return self.cleanup({"file_id": file_id})

    def cleanup_chat(self, chat_id):
        """Delete all file chunks for a chat session.

        Args:
            chat_id: Chat session ID

        Returns:
            Number of deleted documents
        """
        return self.cleanup({"chat_id": chat_id})

