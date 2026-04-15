#!/usr/bin/env python3
import os
import sys
import json
import hashlib
import random
import urllib.request
import re

# Add backend to path to use the ACTUAL application chunking logic
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.chunking import chunk_code_text, chunk_document_text, chunk_mixed_text

# Target ~800 tokens per chunk for processing test data (representing typical RAG sizes)
TEST_CHUNK_SIZE = 800

random.seed(42)

# =========================================================================
# URL SOURCES FOR REAL-WORLD DATA
# =========================================================================

# 10 Massive Python Files from CPython
CODE_URLS = [
    "https://raw.githubusercontent.com/python/cpython/main/Lib/asyncio/tasks.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/urllib/request.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/datetime.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/subprocess.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/logging/__init__.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/pathlib.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/json/encoder.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/tarfile.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/threading.py",
    "https://raw.githubusercontent.com/python/cpython/main/Lib/argparse.py"
]

# 10 Detailed Wikipedia Articles (Prose)
PROSE_TITLES = [
    "Quantum_mechanics",
    "History_of_Earth",
    "General_relativity",
    "Photosynthesis",
    "Industrial_Revolution",
    "Plate_tectonics",
    "Artificial_intelligence",
    "Black_hole",
    "Immune_system",
    "Evolution"
]

# 10 Deep Technical Articles/PEPs containing extensive text + code blocks (Mixed)
MIXED_URLS = [
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0484.rst", # Type Hints
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0008.rst", # Style Guide
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0333.rst", # WSGI
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0257.rst", # Docstrings
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0492.rst", # Async/Await
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0343.rst", # With Statement
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0557.rst", # Data Classes
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-3156.rst", # Asyncio
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0622.rst", # Pattern Matching
    "https://raw.githubusercontent.com/python/peps/master/peps/pep-0572.rst"  # Assignment Expressions
]

# Decoys
DECOY_CODE_URL = "https://raw.githubusercontent.com/python/cpython/main/Lib/turtle.py"
DECOY_PROSE_TITLE = "History_of_chess"
DECOY_MIXED_URL = "https://raw.githubusercontent.com/python/peps/master/peps/pep-0020.rst" # Zen of Python


def fetch_url_text(url: str) -> str:
    print(f"Fetching: {url[-40:]}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return response.read().decode('utf-8')

def fetch_wiki_text(title: str) -> str:
    print(f"Fetching Wiki: {title}")
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={title}&format=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        pages = data['query']['pages']
        return list(pages.values())[0]['extract']

def get_hash(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]

def extract_query_from_chunk_code(chunk: str) -> str:
    """Find a class or function name in the chunk to build a query."""
    funcs = re.findall(r'def\s+(\w+)\s*\(', chunk)
    classes = re.findall(r'class\s+(\w+)\s*[:\(]', chunk)
    
    if classes:
        target = classes[0]
        return f"Explain the structure and purpose of the {target} class."
    elif funcs:
        target = funcs[-1]  # Pick the last one which is likely fully defined in the chunk
        return f"How is the {target} function implemented and what does it handle?"
    
    # Fallback to random long words
    words = [w.strip("(),:'\"") for w in chunk.split() if len(w) > 8 and w.isalpha()]
    target = random.choice(words) if words else "this specific component"
    return f"What module or process manages {target} in the source code?"

def extract_query_from_chunk_prose(chunk: str) -> str:
    """Extract a descriptive sentence from a prose chunk to build a query."""
    sentences = re.split(r'(?<=[.!?])\s+', chunk.strip())
    # Find a decent length sentence
    valid_sentences = [s for s in sentences if 40 < len(s) < 150]
    if valid_sentences:
        target_sentence = random.choice(valid_sentences)
        # Grab a key phrase from the sentence
        words = [w for w in target_sentence.split() if len(w) > 5]
        if len(words) > 3:
            phrase = " ".join(words[1:4]).strip(".,;:()")
            return f"What does the document state regarding {phrase}?"
        return f"Provide details retrieved concerning: '{target_sentence[:50]}...'"
    
    words = [w for w in chunk.split() if len(w) > 8]
    target = random.choice(words) if words else "the core topic"
    return f"Summarize the points revolving around {target}."

def setup_test_data():
    output_dir = 'tests/test_rag_data'
    os.makedirs(output_dir, exist_ok=True)
    
    # Clean previous records
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))
        
    queries = {"code": [], "pdf": [], "mixed": []}

    print("=== Fetching Real-World Data ===")
    
    # --- 1. CODE ---
    for url in CODE_URLS:
        try:
            content = fetch_url_text(url)
            # Ensure it fits "code" classifier (it's pure python)
            file_id = get_hash(content)
            
            with open(os.path.join(output_dir, f"code_{file_id}.py"), "w") as f:
                f.write(content)
                
            # Chunk the file using actual chunking logic
            chunks = chunk_code_text(content, TEST_CHUNK_SIZE)
            if len(chunks) > 2:
                # Pick a chunk from the middle to ensure good retrieval test
                target_chunk = chunks[len(chunks) // 2]
            else:
                target_chunk = chunks[0]
                
            query_str = extract_query_from_chunk_code(target_chunk)
            queries["code"].append({"query": query_str, "relevant_id": file_id})
            
            # Create a duplicate
            dup_content = content.replace("def ", "def _sub_").replace("class ", "class _Variant")
            with open(os.path.join(output_dir, f"code_dup_{file_id}.py"), "w") as f:
                f.write(dup_content)
        except Exception as e:
            print(f"Failed to process CODE url {url}: {e}")

    # --- 2. PROSE (PDF) ---
    for title in PROSE_TITLES:
        try:
            content = fetch_wiki_text(title)
            # STRIP ALL MARKDOWN/WIKI HEADINGS ('==' etc) to ensure classifier reads it as pure Document
            content = re.sub(r'={2,}.*?={2,}', '', content)
            
            file_id = get_hash(content)
            with open(os.path.join(output_dir, f"pdf_{file_id}.txt"), "w") as f:
                f.write(content)
                
            chunks = chunk_document_text(content, TEST_CHUNK_SIZE)
            
            # Select chunk, avoiding pure whitespace or very short ones
            valid_chunks = [c for c in chunks if len(c.strip()) > 100]
            target_chunk = valid_chunks[len(valid_chunks) // 2] if valid_chunks else chunks[0]
            
            query_str = extract_query_from_chunk_prose(target_chunk)
            queries["pdf"].append({"query": query_str, "relevant_id": file_id})
            
            # Duplicate
            dup_content = content.replace("the ", "the actual ").replace(" a ", " an observed ")
            with open(os.path.join(output_dir, f"pdf_dup_{file_id}.txt"), "w") as f:
                f.write(dup_content)
        except Exception as e:
            print(f"Failed to process PROSE title {title}: {e}")
            
    # --- 3. MIXED ---
    for url in MIXED_URLS:
        try:
            content = fetch_url_text(url)
            # Convert RST code blocks (:: or .. code-block::) into markdown standard (```)
            content = re.sub(r'\.\.\s+(code-block|python)::.*?\n\s*\n', '```python\n', content)
            content = content.replace('::\n\n ', '```python\n ')
            # It's not a perfect parser but it injects enough code blocks to trigger Mixed logic
            
            file_id = get_hash(content)
            
            with open(os.path.join(output_dir, f"mixed_{file_id}.txt"), "w") as f:
                f.write(content)
                
            chunks = chunk_mixed_text(content, TEST_CHUNK_SIZE)
            
            # For mixed, prefer a chunk that actually contains some code if possible
            code_chunks = [c for c in chunks if "```" in c or "def " in c or "class " in c]
            if code_chunks:
                target_chunk = random.choice(code_chunks)
            else:
                target_chunk = chunks[len(chunks) // 2]
                
            # Build query based on whether we hit code or prose
            if "def " in target_chunk or "class " in target_chunk:
                query_str = extract_query_from_chunk_code(target_chunk)
            else:
                query_str = extract_query_from_chunk_prose(target_chunk)
                
            queries["mixed"].append({"query": f"[MIXED] {query_str}", "relevant_id": file_id})
            
            # Duplicate
            dup_content = content.replace("if ", "if (True and) ").replace("def ", "def _x_")
            with open(os.path.join(output_dir, f"mixed_dup_{file_id}.txt"), "w") as f:
                f.write(dup_content)
        except Exception as e:
            print(f"Failed to process MIXED url {url}: {e}")

    # --- 4. DECOYS ---
    print("Fetching Decoys...")
    decoy_code = fetch_url_text(DECOY_CODE_URL)
    with open(os.path.join(output_dir, f"code_decoy_{get_hash(decoy_code)}.py"), "w") as f:
        f.write(decoy_code)
        
    decoy_prose = fetch_wiki_text(DECOY_PROSE_TITLE)
    decoy_prose = re.sub(r'={2,}.*?={2,}', '', decoy_prose)
    with open(os.path.join(output_dir, f"pdf_decoy_{get_hash(decoy_prose)}.txt"), "w") as f:
        f.write(decoy_prose)
        
    decoy_mixed = fetch_url_text(DECOY_MIXED_URL)
    with open(os.path.join(output_dir, f"mixed_decoy_{get_hash(decoy_mixed)}.txt"), "w") as f:
        f.write(decoy_mixed)
        
    # Write Queries
    with open('tests/test_queries.json', 'w') as f:
        json.dump(queries, f, indent=2)

    print("\nExtraction & Query Building Complete!")
    print(f"Produced Queries -> Code: {len(queries['code'])}, PDF: {len(queries['pdf'])}, Mixed: {len(queries['mixed'])}")

if __name__ == "__main__":
    setup_test_data()
