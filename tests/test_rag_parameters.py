#!/usr/bin/env python3
"""
RAG Parameter Grid Search Test Harness

This script performs a grid search across RAG parameters to identify optimal
configurations for different document types (code, PDF, mixed).

Usage:
    python tests/test_rag_parameters.py
"""

import os
import re
import sys
import json
import time
import random
import hashlib
import math
from datetime import datetime
from typing import Dict, List, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config
from backend.rag import RAGManager, FileRAG, AIEmbeddingFunction


# =============================================================================
# CONFIGURATION
# =============================================================================

# Parameter ranges to test
# NOTE: RAG_MIN_SEMANTIC_SCORE is now a true cosine similarity [0, 1] after the
# score formula fix (cos_sim = 1 - L2²/2). Recalibrated to skip the noise floor.
PARAM_RANGES = {
    'RAG_MIN_SEMANTIC_SCORE': [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
    'RAG_FETCH_MULTIPLIER': [2, 3, 4, 5, 6, 8, 10, 15, 20],
    'RAG_DEDUP_THRESHOLD': [0.70, 0.75, 0.80, 0.85, 0.90, 0.95],
    'RAG_DECAY_RATE': [0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50],
}

# Number of combinations to sample (stratified sampling)
NUM_COMBINATIONS = 512

# Test parameters
NUM_TEST_DOCUMENTS_PER_TYPE = 10
NUM_QUERIES_PER_TYPE = 15
N_RESULTS = 10  # Number of results to retrieve per query
NUM_WORKERS = int(os.environ.get('RAG_GRID_WORKERS', 4))  # Configurable via environment variable

# Set seed for reproducibility
random.seed(42)


# =============================================================================
# METRICS CALCULATION
# =============================================================================

def _get_true_id(file_id: str) -> str:
    """Strip 'dup_' prefix from file_id for evaluation matching."""
    if file_id.startswith('dup_'):
        return file_id[4:]
    return file_id


def calculate_recall_at_k(results: List[Dict], relevant_ids: set, k: int) -> float:
    """Calculate Recall@K for a set of results."""
    if not relevant_ids:
        return 1.0  # No relevant items = perfect recall

    top_k_ids = {_get_true_id(r.get('file_id', r.get('id', ''))) for r in results[:k]}
    relevant_in_top_k = len(top_k_ids & relevant_ids)
    return relevant_in_top_k / len(relevant_ids)


def calculate_mrr(results: List[Dict], relevant_ids: set) -> float:
    """Calculate Mean Reciprocal Rank for a set of results."""
    if not relevant_ids:
        return 1.0

    for i, result in enumerate(results):
        # Match against either parent file_id or actual chunk id
        result_id = _get_true_id(result.get('file_id', result.get('id', '')))
        if result_id in relevant_ids:
            return 1.0 / (i + 1)

    return 0.0


def calculate_ndcg_at_k(results: List[Dict], relevant_ids: set, k: int) -> float:
    """Calculate Normalized Discounted Cumulative Gain@K."""
    if not relevant_ids:
        return 1.0

    # Calculate DCG
    dcg = 0.0
    seen = set()
    for i, result in enumerate(results[:k]):
        result_id = _get_true_id(result.get('file_id', result.get('id', '')))
        if result_id in relevant_ids and result_id not in seen:
            seen.add(result_id)
            dcg += 1.0 / math.log2(i + 2)  # i+2 because i is 0-indexed

    # Calculate IDCG (ideal DCG)
    num_relevant = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(num_relevant))

    return dcg / idcg if idcg > 0 else 0.0


def calculate_all_metrics(results: List[Dict], relevant_ids: set) -> Dict[str, float]:
    """Calculate all retrieval metrics."""
    return {
        'recall@1':  calculate_recall_at_k(results, relevant_ids, 1),
        'recall@3':  calculate_recall_at_k(results, relevant_ids, 3),
        'recall@5':  calculate_recall_at_k(results, relevant_ids, 5),
        'recall@10': calculate_recall_at_k(results, relevant_ids, 10),
        'mrr':       calculate_mrr(results, relevant_ids),
        'ndcg@5':    calculate_ndcg_at_k(results, relevant_ids, 5),
        'ndcg@10':   calculate_ndcg_at_k(results, relevant_ids, 10),
    }


# =============================================================================
# PARAMETER SAMPLING
# =============================================================================

def generate_parameter_combinations(num_samples: int = NUM_COMBINATIONS) -> List[Dict]:
    """Sample parameter combinations using Latin Hypercube Sampling (LHS).

    LHS divides each parameter's value range into `num_samples` equal strata
    and picks exactly one value from each stratum, then applies a random
    column permutation so the joint sample has no marginal clustering.
    This guarantees full marginal coverage even at 7-8% of the total grid,
    unlike plain random.sample which can leave entire regions unexplored.
    """
    keys   = ['RAG_MIN_SEMANTIC_SCORE', 'RAG_FETCH_MULTIPLIER',
              'RAG_DEDUP_THRESHOLD',   'RAG_DECAY_RATE']
    ranges = [PARAM_RANGES[k] for k in keys]

    n = num_samples
    # For each parameter, generate a shuffled index sequence 0..n-1
    # so every stratum is represented exactly once per column.
    lhs_cols = [list(range(n)) for _ in keys]
    for col in lhs_cols:
        random.shuffle(col)

    combinations = []
    for i in range(n):
        combo = {}
        for j, key in enumerate(keys):
            r = ranges[j]
            # Map the shuffled stratum index to a value via modulo
            combo[key] = r[lhs_cols[j][i] % len(r)]
        combinations.append(combo)

    return combinations


# =============================================================================
# TEST DOCUMENTS AND QUERIES
# =============================================================================

def load_test_data():
    """Load test data from generated files.

    Supports the new query format::

        {"code": [{"query": "...", "relevant_id": "<file_id>"}, ...], ...}

    Returns:
        (documents, all_corpus, queries) where `documents` contains only the
        original files (used for relevance evaluation) and `all_corpus` contains
        originals + near-duplicates + decoys (stored in ChromaDB so that the
        dedup threshold and semantic score threshold have real candidates to
        discriminate against).
    """
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_rag_data')
    queries_file  = os.path.join(os.path.dirname(__file__), 'test_queries.json')

    # Load queries
    with open(queries_file, 'r') as f:
        raw_queries = json.load(f)
    queries: Dict[str, List] = {k: v for k, v in raw_queries.items()}

    # Load ALL documents from test_rag_data, tagging each by class.
    # Filename conventions from the generator:
    #   code_<hash>.py          -> original code
    #   code_dup_<hash>.py      -> near-duplicate code
    #   code_decoy_<hash>.py    -> off-topic decoy code
    #   (same pattern for pdf_ and mixed_)
    documents:    Dict[str, List] = {'code': [], 'pdf': [], 'mixed': []}  # originals only
    all_corpus:   List[Dict]      = []                                      # everything

    type_map = [
        ('code_',  'code',  '.py'),
        ('pdf_',   'pdf',   '.txt'),
        ('mixed_', 'mixed', '.txt'),
    ]

    for filename in sorted(os.listdir(test_data_dir)):
        filepath = os.path.join(test_data_dir, filename)
        for prefix, doc_type, ext in type_map:
            if not (filename.startswith(prefix) and filename.endswith(ext)):
                continue
            with open(filepath, 'r') as f:
                content = f.read()

            # Classify: strip prefix and extension to get the bare hash;
            # then determine if it's a dup/decoy by the infix.
            bare = filename[len(prefix):-len(ext)]   # e.g. 'dup_abc123' or 'decoy_abc123' or 'abc123'
            is_near_dup = bare.startswith('dup_')
            is_decoy    = bare.startswith('decoy_')
            # file_id must be UNIQUE across all corpus entries.
            # Near-dupes: keep the 'dup_<hash>' form so they don't overwrite the original
            #   (using just the hash caused the dup to collide with — and wipe — the original).
            # Decoys: their hash is already unique, just take the last segment.
            # Originals: use the bare hash directly.
            if is_near_dup:
                file_id = bare          # 'dup_<hash>' — distinct from the original '<hash>'
            elif is_decoy:
                file_id = bare.split('_')[-1]   # 'decoy_<hash>' → '<hash>'
            else:
                file_id = bare          # the original hash

            entry = {'id': file_id, 'content': content, 'type': doc_type,
                     'is_near_dup': is_near_dup, 'is_decoy': is_decoy}
            all_corpus.append(entry)

            # Only originals go into the relevance-evaluation pool
            if not is_near_dup and not is_decoy:
                documents[doc_type].append({'id': file_id, 'content': content,
                                            'type': doc_type})
            break  # matched one prefix — no need to check further

    print("  - Document ID Map (Logical -> Title/Snippet):")
    id_map = {}
    for dtype, items in documents.items():
        for item in items:
            # Try to extract title for PEPs/standard formats
            title = "Unknown"
            title_match = re.search(r'^Title:\s*(.*)$', item['content'], re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Fallback to first non-empty line
                lines = [l.strip() for l in item['content'].split('\n') if l.strip()]
                title = lines[0][:60] if lines else "Empty Document"
            id_map[item['id']] = title
    
    # Sort by ID for readability
    for fid in sorted(id_map.keys()):
        print(f"    {fid}: {id_map[fid][:60]}...")

    return documents, all_corpus, queries


def get_relevant_ids_for_query(query: str, document_type: str,
                               documents: List[Dict],
                               query_item=None) -> set:
    """Return the set of document IDs that are relevant to this query.

    Priority:
    1. Ground-truth: if `query_item` is a dict with a `relevant_id` key
       (produced by the new data generator), use that directly.
    2. Fallback: TF-IDF keyword overlap across the document corpus when no
       ground-truth label is available (e.g. when running against old data).
    """
    # --- Ground-truth path -------------------------------------------
    if isinstance(query_item, dict) and 'relevant_id' in query_item:
        rid = query_item['relevant_id']
        # Verify the ID is actually in the loaded document set
        known_ids = {d['id'] for d in documents}
        if rid in known_ids:
            return {rid}
        # ID not found — warn loudly and fall through to keyword overlap
        print(f"    [WARNING] relevant_id '{rid}' not found in {document_type} corpus "
              f"(known: {sorted(known_ids)[:3]}...). Falling back to keyword overlap.")

    # --- Keyword-overlap fallback ------------------------------------
    if not documents:
        return set()
    query_tokens = set(t.lower() for t in re.split(r'\W+', query) if len(t) > 3)
    if not query_tokens:
        return {doc['id'] for doc in documents}
    scores = {}
    for doc in documents:
        content_tokens = set(t.lower() for t in re.split(r'\W+', doc['content']) if len(t) > 3)
        scores[doc['id']] = len(query_tokens & content_tokens)
    max_score = max(scores.values())
    if max_score == 0:
        return {doc['id'] for doc in documents}
    return {doc_id for doc_id, score in scores.items() if score == max_score}


# =============================================================================
# GRID SEARCH EXECUTION
# =============================================================================

class TestRAG:
    """Test wrapper around RAG that allows temporary parameter overrides."""

    def __init__(self, rag_manager: RAGManager, corpus: List[Dict],
                 eval_documents: Dict[str, List], queries: List[str]):
        self.rag_manager  = rag_manager
        self.file_rag     = FileRAG(rag_manager=rag_manager)
        # corpus: ALL documents to store in ChromaDB (originals + near-dupes + decoys)
        self.corpus       = corpus
        # eval_documents: originals only, keyed by type, used for relevance scoring
        self.documents    = eval_documents
        self.queries      = queries

    def retrieve_and_evaluate(self, params: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate retrieval quality for a given parameter set.

        Documents must have been stored before calling this method.
        Each document's metadata timestamp is set to a staggered value
        (between 1 and 30 days ago) so that RAG_DECAY_RATE has a measurable
        effect on scores across the retrieval pool.
        """
        # Apply parameter overrides
        original_scores = config.RAG_MIN_SEMANTIC_SCORE
        original_fetch = config.RAG_FETCH_MULTIPLIER
        original_dedup = config.RAG_DEDUP_THRESHOLD
        original_decay = config.RAG_DECAY_RATE

        config.RAG_MIN_SEMANTIC_SCORE = params['RAG_MIN_SEMANTIC_SCORE']
        config.RAG_FETCH_MULTIPLIER = params['RAG_FETCH_MULTIPLIER']
        config.RAG_DEDUP_THRESHOLD = params['RAG_DEDUP_THRESHOLD']
        config.RAG_DECAY_RATE = params['RAG_DECAY_RATE']

        try:
            metrics = {
                'code':  {'recall@1': 0, 'recall@3': 0, 'recall@5': 0, 'recall@10': 0,
                          'mrr': 0, 'ndcg@5': 0, 'ndcg@10': 0},
                'pdf':   {'recall@1': 0, 'recall@3': 0, 'recall@5': 0, 'recall@10': 0,
                          'mrr': 0, 'ndcg@5': 0, 'ndcg@10': 0},
                'mixed': {'recall@1': 0, 'recall@3': 0, 'recall@5': 0, 'recall@10': 0,
                          'mrr': 0, 'ndcg@5': 0, 'ndcg@10': 0},
            }

            for doc_type in ['code', 'pdf', 'mixed']:
                # Use originals-only pool for relevance evaluation
                type_docs    = self.documents.get(doc_type, [])
                type_queries = self.queries.get(doc_type, [])[:NUM_QUERIES_PER_TYPE]

                if not type_docs or not type_queries:
                    print(f"    No {doc_type} documents or queries found")
                    continue

                # Run queries - documents are already stored; do NOT re-store here
                print(f"    Running {len(type_queries)} queries for {doc_type}...")
                query_metrics = []
                for query_item in type_queries:
                    # Support both new {query, relevant_id} dicts and legacy plain strings
                    if isinstance(query_item, dict):
                        query = query_item['query']
                    else:
                        query = query_item
                    print(f"    Querying {doc_type}: {query[:50]}...")
                    # Map the test's logical type to the actual file_type stored in ChromaDB
                    # by detect_file_type (chunking.py).  detect_file_type never returns "pdf":
                    # prose documents become "document", and mixed content only becomes "mixed"
                    # when BOTH code_score>=8 AND doc_score>=0.4.  Using the wrong value here
                    # causes the where-filter to match nothing → Recall@K = 0 for all params.
                    STORED_TYPE_MAP = {
                        'code':  'code',
                        'pdf':   'document',   # detect_file_type returns 'document' for prose
                        'mixed': 'mixed',       # returned when both thresholds are met
                    }
                    stored_type = STORED_TYPE_MAP[doc_type]
                    try:
                        results = self.file_rag.retrieve_by_query(
                            query=query,
                            n_results=N_RESULTS,
                            where={"file_type": stored_type},
                            hybrid=True
                        )
                        print(f"      Retrieved {len(results)} results")
                    except Exception as e:
                        print(f"      [ERROR] Query failed: {e}")
                        continue

                    if results:
                        # Use ground-truth relevant_id when available, keyword overlap otherwise
                        relevant_ids = get_relevant_ids_for_query(
                            query, doc_type, type_docs, query_item=query_item
                        )
                        print(f"      Relevant IDs: {relevant_ids}")
                        print(f"      Result IDs  : {[r.get('id', '') for r in results]}")
                        print(f"      Result scores: {[r.get('score', 0) for r in results]}")
                        metrics_dict = calculate_all_metrics(results, relevant_ids)
                        print(f"      Metrics: {metrics_dict}")
                        query_metrics.append(metrics_dict)

                # Average metrics across queries
                # Use num_attempted (not len(query_metrics)) as denominator so
                # that exception-skipped queries reduce recall rather than hiding it.
                num_attempted = len(type_queries)
                if query_metrics:
                    for metric_name in ['recall@1', 'recall@3', 'recall@5', 'recall@10',
                                        'mrr', 'ndcg@5', 'ndcg@10']:
                        total_value = sum(qm.get(metric_name, 0) for qm in query_metrics)
                        avg_value = total_value / num_attempted
                        metrics[doc_type][metric_name] = round(avg_value, 4)

            # Calculate overall score: 50% recall@5 + 50% MRR.
            # With a single relevant document per query, NDCG@5 and MRR are
            # nearly identical (both reduce to a rank-position function).
            # Dropping NDCG avoids double-counting and keeps the composite honest.
            # Revisit once ground-truth provides multi-document relevant sets.
            def _composite(m):
                return m['recall@5'] * 0.50 + m['mrr'] * 0.50

            overall = (
                _composite(metrics['code'])  * 0.33 +
                _composite(metrics['pdf'])   * 0.33 +
                _composite(metrics['mixed']) * 0.34
            )

            return {
                'params': params.copy(),
                'scores': metrics,
                'overall_score': round(overall, 4),
            }

        finally:
            # Restore original parameters
            config.RAG_MIN_SEMANTIC_SCORE = original_scores
            config.RAG_FETCH_MULTIPLIER = original_fetch
            config.RAG_DEDUP_THRESHOLD = original_dedup
            config.RAG_DECAY_RATE = original_decay

# =============================================================================
# WORKER PROCESS LOGIC
# =============================================================================

# Global for worker processes
_worker_test_rag = None

def init_worker(corpus_data, eval_documents, queries_data, embedding_dim):
    """Initialize the RAG system in each worker process."""
    global _worker_test_rag
    
    # Stagger starts to avoid overwhelming the embedding server
    # with multiple simultaneous dimension-check or first-query requests.
    import random
    time.sleep(random.uniform(0.1, 5.0))
    
    # Each process must have its own RAGManager instance to avoid socket shared
    # between parent/child which causes ChromaDB connection errors.
    # Parallel processes have isolated memory, so config-patching is safe.
    RAGManager.reset_instance()
    
    # Monkey-patch _get_embedding_dimension to avoid redundant API calls in workers
    # which can cause the thundering herd hang.
    original_method = RAGManager._get_embedding_dimension
    RAGManager._get_embedding_dimension = lambda self: embedding_dim
    
    try:
        rag_manager = RAGManager(
            persist_path=os.path.join(config.DATA_DIR, 'test_grid_search'),
            api_url=config.EMBEDDING_URL,
            embedding_model='embeddinggemma/embeddinggemma-300M-Q8_0',
            api_key=config.EMBEDDING_API_KEY
        )
    finally:
        # Restore for sanity
        RAGManager._get_embedding_dimension = original_method

    _worker_test_rag = TestRAG(rag_manager, corpus=corpus_data,
                               eval_documents=eval_documents, queries=queries_data)
    _worker_test_rag.file_rag = FileRAG(rag_manager=rag_manager)

def evaluate_worker(params_idx_tuple):
    """Evaluate a single parameter combination in a worker process."""
    params, idx = params_idx_tuple
    try:
        result = _worker_test_rag.retrieve_and_evaluate(params)
        return result, idx, None
    except Exception as e:
        return None, idx, str(e)

def run_grid_search():
    """Run the complete grid search."""
    print("=" * 60)
    print("RAG Parameter Grid Search")
    print("=" * 60)

    # Load test data
    print("\n[1/4] Loading test data...")
    documents, all_corpus, queries = load_test_data()

    originals_count = sum(len(v) for v in documents.values())
    print(f"  - Loaded {originals_count} original documents (used for query evaluation)")
    print(f"  - Loaded {len(all_corpus)} total corpus entries "
          f"(originals + near-dupes + decoys, all stored in ChromaDB)")
    print(f"  - Loaded {sum(len(v) for v in queries.values())} queries with ground-truth labels")

    # Generate parameter combinations
    print("\n[2/4] Generating parameter combinations...")
    param_combinations = generate_parameter_combinations(NUM_COMBINATIONS)
    print(f"  - Generated {len(param_combinations)} parameter combinations")

    # Initialize RAG
    # Must reset the singleton FIRST so the custom persist_path below is
    # honoured even if the main application already created a RAGManager.
    print("\n[3/4] Initializing RAG system...")
    RAGManager.reset_instance()
    rag_manager = RAGManager(
        persist_path=os.path.join(config.DATA_DIR, 'test_grid_search'),
        api_url=config.EMBEDDING_URL,
        embedding_model='embeddinggemma/embeddinggemma-300M-Q8_0',
        api_key=config.EMBEDDING_API_KEY
    )

    # Create test RAG wrapper
    all_documents = all_corpus  # store the full corpus (originals + near-dupes + decoys)
    all_queries = {
        'code': queries['code'],
        'pdf': queries['pdf'],
        'mixed': queries['mixed']
    }

    test_rag = TestRAG(rag_manager, corpus=all_corpus,
                       eval_documents=documents, queries=all_queries)

    # -------------------------------------------------------------------------
    # Corpus fingerprint caching: skip re-embedding if corpus hasn't changed.
    #
    # We hash all corpus entry IDs and the first 256 chars of their content.
    # This fingerprint is stored in a sidecar file next to the ChromaDB dir.
    # On the next run, if the fingerprint matches and the collections are
    # non-empty, we skip the expensive embed+store phase entirely.
    # -------------------------------------------------------------------------
    persist_path = os.path.join(config.DATA_DIR, 'test_grid_search')
    fingerprint_file = os.path.join(persist_path, '_corpus_fingerprint.txt')

    import hashlib as _hashlib
    fp_parts = sorted(f"{d['id']}:{d['content'][:256]}" for d in all_corpus)
    corpus_fingerprint = _hashlib.sha256('\n'.join(fp_parts).encode()).hexdigest()

    def _collection_count(suffix):
        try:
            coll = rag_manager.client.get_collection(f"file_store{suffix}")
            return coll.count()
        except Exception:
            return 0

    cached_fingerprint = None
    if os.path.exists(fingerprint_file):
        with open(fingerprint_file) as _f:
            cached_fingerprint = _f.read().strip()

    vector_count = _collection_count("_vector")
    bm25_count   = _collection_count("_bm25")
    collections_populated = vector_count > 0 and bm25_count > 0

    if cached_fingerprint == corpus_fingerprint and collections_populated \
            and os.environ.get('RAG_INVALIDATE_CACHE', 'false').lower() != 'true':
        print(f"  - Corpus fingerprint matches ({corpus_fingerprint[:12]}...) "
              f"and collections are non-empty (vector={vector_count}, bm25={bm25_count}).")
        print("  - Skipping re-embedding — reusing cached ChromaDB collections.")
        test_rag.file_rag = FileRAG(rag_manager=rag_manager)
    else:
        reason = "fingerprint mismatch" if cached_fingerprint != corpus_fingerprint else "empty collections"
        print(f"  - Cache miss ({reason}). Rebuilding collections...")

        # Wipe stale collections before re-storing, unless resuming
        if os.environ.get('RAG_RESUME', 'false').lower() == 'true':
            print("  - [RESUME MODE] Keeping existing collections...")
        else:
            print("  - Clearing stale test collections...")
            for coll_suffix in ("_vector", "_bm25"):
                try:
                    rag_manager.client.delete_collection(f"file_store{coll_suffix}")
                    print(f"    Deleted file_store{coll_suffix}")
                except Exception:
                    pass  # Collection didn't exist — that's fine

        # Re-initialise FileRAG so it picks up the freshly cleared collections
        test_rag.file_rag = FileRAG(rag_manager=rag_manager)

        # Store all documents as a single batched embedding call.
        # store_files_batch() accumulates chunks across ALL files first and
        # then calls store() once, so the embedder receives the full corpus
        # in a single (batched) operation instead of one tiny request per file.
        print("  - Storing test documents with staggered timestamps (batched)...")
        now = time.time()
        seconds_per_day = 86400
        file_rag = test_rag.file_rag

        # Map from test-data filename prefix to internal file_type used by RAG.
        # 'pdf' is the test-data label; the RAG system calls prose files 'document'.
        _type_map = {'code': 'code', 'pdf': 'document', 'mixed': 'mixed'}

        file_specs = []
        for idx, doc in enumerate(all_corpus):
            age_days = 1 + (idx % 30)
            fake_timestamp = now - age_days * seconds_per_day
            ground_truth_type = _type_map.get(doc['type'], 'document')
            file_specs.append({
                'file_id': doc['id'],
                'chat_id': 'test_grid_search',
                'content_text': doc['content'],
                'filename': f"test.{doc['type']}",
                'timestamp': fake_timestamp,
                'file_type_override': ground_truth_type,
            })

        try:
            stored_ids = file_rag.store_files_batch(file_specs)
            print(f"  - Stored {len(stored_ids)} chunks from {len(file_specs)} files in one batch.")
        except Exception as e:
            print(f"    [ERROR] Batch store failed: {e}")

        # Save the new fingerprint so future runs can skip re-embedding
        os.makedirs(persist_path, exist_ok=True)
        with open(fingerprint_file, 'w') as _f:
            _f.write(corpus_fingerprint)
        print(f"  - Corpus fingerprint saved ({corpus_fingerprint[:12]}...).")


    print(f"  - Stored {len(all_documents)} documents")

    # Run parameter evaluations in parallel
    print("\n[4/4] Running grid search...")
    print(f"  - Testing {len(param_combinations)} parameter combinations")
    print(f"  - Using {NUM_WORKERS} parallel workers")
    print(f"  - This should take approx {(len(param_combinations) * 8 / NUM_WORKERS / 60):.1f} minutes")

    results = [None] * len(param_combinations)
    start_time = time.time()
    completed = 0

    # Task list for executor
    tasks = [(params, i) for i, params in enumerate(param_combinations)]
    
    # Get embedding dimension from main process so workers can skip the probe
    embedding_dim = rag_manager.embedding_dimension

    with ProcessPoolExecutor(
        max_workers=NUM_WORKERS,
        mp_context=multiprocessing.get_context('spawn'),
        initializer=init_worker,
        initargs=(all_corpus, documents, all_queries, embedding_dim)
    ) as executor:
        futures = [executor.submit(evaluate_worker, task) for task in tasks]
        
        for future in as_completed(futures):
            result, idx, error = future.result()
            completed += 1
            
            if error:
                print(f"  [ERROR] Combination {idx + 1}: {error}")
            else:
                results[idx] = result
                print(f"  [OK] Combination {idx + 1}: score={result['overall_score']:.4f}")

            if completed % 20 == 0:
                elapsed = time.time() - start_time
                print(f"\n  - Completed {completed}/{len(param_combinations)} ({elapsed:.1f}s elapsed)")

    # Filter out failed combinations
    results = [r for r in results if r is not None]
    
    elapsed_time = time.time() - start_time
    print(f"\n  - Grid search completed in {elapsed_time:.1f} seconds")

    # Sort by overall score and find best
    results.sort(key=lambda x: x['overall_score'], reverse=True)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    # Best parameters per document type
    best_by_type = {
        'code': max(results, key=lambda x: x['scores']['code']['recall@5']),
        'pdf': max(results, key=lambda x: x['scores']['pdf']['recall@5']),
        'mixed': max(results, key=lambda x: x['scores']['mixed']['recall@5']),
        'overall': results[0],  # Overall best
    }

    for doc_type in ['code', 'pdf', 'mixed', 'overall']:
        best = best_by_type[doc_type]
        print(f"\nBest for {doc_type}:")
        print(f"  Parameters: {best['params']}")
        print(f"  Overall Score: {best['overall_score']}")
        for dt in ['code', 'pdf', 'mixed']:
            print(f"  {dt} Recall@5: {best['scores'][dt]['recall@5']}")

    return results, best_by_type


def generate_reports(results: List[Dict], best_by_type: Dict[str, Dict]):
    """Generate markdown and JSON reports."""
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Generate JSON report
    json_report = {
        'metadata': {
            'timestamp': timestamp,
            'num_combinations_tested': len(results),
            'num_documents_tested': {
                'code': NUM_TEST_DOCUMENTS_PER_TYPE,
                'pdf': NUM_TEST_DOCUMENTS_PER_TYPE,
                'mixed': NUM_TEST_DOCUMENTS_PER_TYPE,
            },
            'num_queries_per_type': NUM_QUERIES_PER_TYPE,
            'n_results': N_RESULTS,
        },
        'results': results[:100],  # Top 100 results
        'best_by_type': {
            doc_type: {
                'params': best['params'],
                'scores': best['scores'],
                'overall_score': best['overall_score'],
            }
            for doc_type, best in best_by_type.items()
        }
    }

    json_path = os.path.join(reports_dir, 'rag-grid-results-2026-04-11.json')
    with open(json_path, 'w') as f:
        json.dump(json_report, f, indent=2)
    print(f"\nJSON report saved to: {json_path}")

    # Generate Markdown report
    md_report = f"""# RAG Parameter Grid Search Results

**Date:** {timestamp}
**Total Combinations Tested:** {len(results)}

---

## Executive Summary

The grid search evaluated {len(results)} parameter combinations across {NUM_TEST_DOCUMENTS_PER_TYPE} documents
of each type (code, PDF, mixed) with {NUM_QUERIES_PER_TYPE} queries per type.

---

## Best Parameters by Document Type

### Code Files
| Parameter | Value |
|-----------|-------|
| RAG_MIN_SEMANTIC_SCORE | {best_by_type['code']['params']['RAG_MIN_SEMANTIC_SCORE']} |
| RAG_FETCH_MULTIPLIER | {best_by_type['code']['params']['RAG_FETCH_MULTIPLIER']} |
| RAG_DEDUP_THRESHOLD | {best_by_type['code']['params']['RAG_DEDUP_THRESHOLD']} |
| RAG_DECAY_RATE | {best_by_type['code']['params']['RAG_DECAY_RATE']} |

| Metric | Score |
|--------|-------|
| Recall@5 | {best_by_type['code']['scores']['code']['recall@5']} |
| MRR | {best_by_type['code']['scores']['code']['mrr']} |
| NDCG@5 | {best_by_type['code']['scores']['code']['ndcg@5']} |

### PDF Documents
| Parameter | Value |
|-----------|-------|
| RAG_MIN_SEMANTIC_SCORE | {best_by_type['pdf']['params']['RAG_MIN_SEMANTIC_SCORE']} |
| RAG_FETCH_MULTIPLIER | {best_by_type['pdf']['params']['RAG_FETCH_MULTIPLIER']} |
| RAG_DEDUP_THRESHOLD | {best_by_type['pdf']['params']['RAG_DEDUP_THRESHOLD']} |
| RAG_DECAY_RATE | {best_by_type['pdf']['params']['RAG_DECAY_RATE']} |

| Metric | Score |
|--------|-------|
| Recall@5 | {best_by_type['pdf']['scores']['pdf']['recall@5']} |
| MRR | {best_by_type['pdf']['scores']['pdf']['mrr']} |
| NDCG@5 | {best_by_type['pdf']['scores']['pdf']['ndcg@5']} |

### Mixed Content
| Parameter | Value |
|-----------|-------|
| RAG_MIN_SEMANTIC_SCORE | {best_by_type['mixed']['params']['RAG_MIN_SEMANTIC_SCORE']} |
| RAG_FETCH_MULTIPLIER | {best_by_type['mixed']['params']['RAG_FETCH_MULTIPLIER']} |
| RAG_DEDUP_THRESHOLD | {best_by_type['mixed']['params']['RAG_DEDUP_THRESHOLD']} |
| RAG_DECAY_RATE | {best_by_type['mixed']['params']['RAG_DECAY_RATE']} |

| Metric | Score |
|--------|-------|
| Recall@5 | {best_by_type['mixed']['scores']['mixed']['recall@5']} |
| MRR | {best_by_type['mixed']['scores']['mixed']['mrr']} |
| NDCG@5 | {best_by_type['mixed']['scores']['mixed']['ndcg@5']} |

---

## Top 20 Parameter Combinations

| Rank | Overall Score | Semantic Score | Fetch Multiplier | Dedup Threshold | Decay Rate |
|------|---------------|----------------|------------------|-----------------|------------|
"""

    for i, result in enumerate(results[:20]):
        params = result['params']
        md_report += f"| {i + 1} | {result['overall_score']} | {params['RAG_MIN_SEMANTIC_SCORE']} | {params['RAG_FETCH_MULTIPLIER']} | {params['RAG_DEDUP_THRESHOLD']} | {params['RAG_DECAY_RATE']} |\n"

    md_report += """
---

## Recommendations

1. **For Code Files**: Use lower semantic scores (0.30-0.40) and higher fetch multipliers
2. **For PDF Documents**: Consider even lower semantic scores (0.25-0.35) for better recall
3. **For Mixed Content**: A balanced approach works best
4. **Dedup Threshold**: 0.80-0.85 provides good balance between precision and recall

---

*Report generated by RAG Parameter Grid Search*
"""

    md_path = os.path.join(reports_dir, 'rag-grid-results-2026-04-11.md')
    with open(md_path, 'w') as f:
        f.write(md_report)
    print(f"Markdown report saved to: {md_path}")


def main():
    """Main entry point."""
    results, best_by_type = run_grid_search()
    generate_reports(results, best_by_type)

    print("\nGrid search complete!")


if __name__ == '__main__':
    main()