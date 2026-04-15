# Testing Directives (v3.1.0)

## Overview

This document outlines the testing methodologies and infrastructure within the My-AI repository. Our testing strategy combines standard unit/integration tests with a specialized RAG evaluation and hyperparameter optimization pipeline.

---

## 1. RAG Evaluation & Grid Search Pipeline

We use a high-fidelity evaluation pipeline to mathematically optimize two independent systems: the file-type classifier, and the semantic RAG engine. 

### Infrastructure (`docker/docker-compose.testing.yml`)

The RAG grid search requires the embedding server but runs computationally isolated in an ephemeral container to avoid disrupting the main application.
- **`rag_grid_search` Service**: Boots via `docker/Dockerfile.rag-grid-search`.

### Stage 1: Data Acquisition 
Instead of synthetic data, we pull massive real-world texts (CPython, Wikipedia, PEPs) to test exact natural boundaries and lengths.

**How to fetch data:**
```bash
# Run locally within the python venv (One-time setup)
python tests/fetch_real_test_data.py
```

### Stage 2: Classifier Tuning
The classifier logic is optimized independently of RAG. This guarantees that file misclassifications aren't accidentally masked by loose RAG parameters.

**How to run (AI / Local Execution):**
```bash
# Since this runs instantly in-memory, do this via Python directly
python tests/test_classifier_parameters.py
```

**How to run (User Executed via Docker):**
```bash
docker-compose -f docker/docker-compose.testing.yml run --rm classifier_grid_search
```
*Note: Update `CODE_THRESHOLD` and `DOC_THRESHOLD` in `backend/chunking.py` based on the output report.*

### Stage 3: RAG Grid Search
Evaluates hundreds of combinations of chunk retrieval sizes, semantic thresholds, and deduplication floors using Latin Hypercube Sampling (LHS) across multiple background processes.

**How to run (User Executed via Docker):**
```bash
docker-compose -f docker/docker-compose.testing.yml up --build rag_grid_search
```
*(Automatically executes `tests/test_rag_parameters.py` via Dockerfile CMD).*

**How to run (AI / Local Executed via Python):**
```bash
# Ensure the embedding server is active on localhost
python tests/test_rag_parameters.py
```
*Note: Update `RAG_MIN_SEMANTIC_SCORE`, `RAG_FETCH_MULTIPLIER`, `RAG_DEDUP_THRESHOLD`, and `RAG_DECAY_RATE` in `backend/config.py` based on the output report.*

---

## 2. Standard Testing Protocol

### 2.1 Python Environment
All tests must be run using the project's virtual environment:
```bash
source venv/bin/activate
pytest tests/
```

### 2.2 Adding New Tests
- **Unit Tests**: Store in `tests/` with `test_*.py` prefix.
- **Integration Tests**: Focus on the boundary between the Flask backend and the local LLM endpoints.
- **RAG Benchmarks**: Add new queries to `tests/test_queries.json` and run the grid search to verify no regression in retrieval quality.

---

## 3. Best Practices & Pitfalls

- **State Persistence**: If a test modifies the persistent database, use a temporary SQLite file or ensure cleanup in the `teardown` phase.
- **RAG Data Quality**: If you see "Zero Recall" metrics, it often indicates the synthetic document and query are too dissimilar for the embedding model's current chunking logic. Refine the generator to provide more contextual overlap.
- **Model Loading**: Many integration tests require a running `llama.cpp` server. Ensure the server is reachable and the model is loaded before starting the test suite.
