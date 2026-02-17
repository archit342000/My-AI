import chromadb
from chromadb.utils import embedding_functions
import uuid
import os

class MemoryRAG:
    def __init__(self, persist_path="./backend/chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_path)
        # using default embedding function (all-MiniLM-L6-v2)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="memory_store",
            embedding_function=self.embedding_fn
        )

    def add_memory(self, text, metadata=None):
        if not text:
            return

        self.collection.add(
            documents=[text],
            metadatas=[metadata] if metadata else [{"timestamp": "unknown"}],
            ids=[str(uuid.uuid4())]
        )

    def retrieve_context(self, query, n_results=5):
        if not query:
            return ""

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        if not results['documents']:
            return ""

        # Flatten list of lists
        docs = results['documents'][0]
        context = "\n".join(docs)
        return context
