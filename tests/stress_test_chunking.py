import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag import RAGManager
from backend import config
from backend.providers import RAGProvider
from backend.token_counter import count_tokens

def test_hard_chunking():
    print("Testing Hard Chunking Guarantee...")
    
    # Create a giant monolithic "word" (no spaces, no newlines)
    # 26,000 characters is roughly 6,500 tokens for Gemma
    giant_word = "A" * 26000
    
    rag = RAGProvider.get_manager(
        persist_path=config.CHROMA_PATH,
        api_url=config.EMBEDDING_URL,
        embedding_model=config.EMBEDDING_MODEL if hasattr(config, 'EMBEDDING_MODEL') else None,
        api_key=config.EMBEDDING_API_KEY
    )
    limit = 1000
    
    print(f"Input length: {len(giant_word)} chars")
    
    chunks = rag.chunk_text(giant_word, max_tokens=limit)
    
    print(f"Produced {len(chunks)} chunks")
    
    all_ok = True
    for i, chunk in enumerate(chunks):
        tokens = count_tokens(chunk)
        print(f"  Chunk {i}: {len(chunk)} chars, {tokens} tokens")
        if tokens > limit:
            print(f"  FAILED: Chunk {i} exceeds limit!")
            all_ok = False
            
    if all_ok and len(chunks) > 1:
        print("\nSUCCESS: All chunks are within the hard limit.")
    elif len(chunks) <= 1:
        print("\nFAILED: Output should have been split into multiple chunks.")
    else:
        print("\nFAILED: One or more chunks exceeded the limit.")

if __name__ == "__main__":
    test_hard_chunking()
