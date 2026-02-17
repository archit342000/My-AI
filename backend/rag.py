import chromadb
from chromadb.utils import embedding_functions
import uuid
import os
import requests

class LMStudioEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, api_url="http://localhost:1234", model_name="text-embedding-embeddinggemma-300m"):
        self.api_url = api_url
        self.model_name = model_name

    def __call__(self, input):
        # Determine endpoint. Some versions use /v1/embeddings, others might vary.
        # We assume OpenAI compatible /v1/embeddings
        url = f"{self.api_url}/v1/embeddings"

        # Ensure input is a list of strings
        if isinstance(input, str):
            input = [input]

        payload = {
            "model": self.model_name,
            "input": input
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # OpenAI format: data: [{embedding: [...], ...}, ...]
            embeddings = [item['embedding'] for item in data['data']]
            return embeddings
        except Exception as e:
            print(f"Embedding error: {e}")
            # Fallback or re-raise? For RAG, failure to embed is critical.
            # Returning None or empty might crash Chroma.
            # We'll return dummy embeddings of correct size if possible? No, size unknown.
            raise e

class MemoryRAG:
    def __init__(self, persist_path="./backend/chroma_db", api_url="http://localhost:1234", embedding_model="text-embedding-embeddinggemma-300m"):
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
