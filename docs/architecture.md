# Application Architecture (v3.1.0)



## Core Architectural Principles

### 1. Cache-Aside Pattern

The application implements two separate caching strategies:

- **Response Cache** (`cache_system.py`): For SSE streaming with WAL support. TTL IS implemented via `_is_expired()` and `cleanup_expired()` methods.
- **Database Cache** (`cache_layer.py`): Row-level caching following the Cache-Aside pattern.

Both use TTL for automatic expiration.

```
┌─────────────────────────────────────────────────────────────┐
│                    Request Flow (Read)                      │
├─────────────────────────────────────────────────────────────┤
│  1. Check Cache (with TTL)                                  │
│  2. If Cache Hit → Return Cached Data                       │
│  3. If Cache Miss → Fetch from DB                           │
│  4. Update Cache from DB for subsequent hits                │
└─────────────────────────────────────────────────────────────┘
```

### 2. Atomic Operations with Retry Mechanism

All tools except the **Research Agent** are designed as **atomic operations**:

- Each tool operation is independent and idempotent
- **2 retry attempts** (configurable in `config.py` as `RETRY_COUNT=2`) before failure acknowledgment
- Fast execution time, allowing for retry overhead
- Clean failure states with proper error handling

```
┌─────────────────────────────────────────────────────────────┐
│                  Atomic Tool Flow                          │
├─────────────────────────────────────────────────────────────┤
│  1. Execute Tool Operation                                │
│  2. If Failure → Retry (attempt 1)                        │
│  3. If Failure → Retry (attempt 2)                        │
│  4. If Still Failing → Acknowledge Failure                │
└─────────────────────────────────────────────────────────────┘
```

### 3. Transaction Models: Atomic vs Graceful Degradation

The application uses **two different transaction models** depending on the operation type:

#### 3a. Atomic Transactions (Canvas Operations)

Canvas operations use a strict **atomic transaction** model:

**Core Principle: All-or-Nothing Execution**

Canvas create, update, and delete operations must all succeed together. If ANY component fails, the ENTIRE transaction fails—there is no partial success.

**Use Case:** Canvas operations modify shared state that should not be partially applied. A failed canvas update could leave data in an inconsistent state, so full rollback is required.

#### 3b. Graceful Degradation (Chat Tool Execution)

Chat agent tool execution uses **graceful degradation**:

**Core Principle: Partial Success is Acceptable**

If a user message triggers multiple tool calls, each tool executes independently. If a tool fails, its error is sent to the LLM and other tools continue executing. The user receives partial value from successful tools.

```
┌─────────────────────────────────────────────────────────────────┐
│           Graceful Degradation Flow                             │
├─────────────────────────────────────────────────────────────────┤
│  User Message → Execute All Tools in Sequence                  │
│    ├── Tool 1 Execution (with retry) → SUCCESS                 │
│    ├── Tool 2 Execution (with retry) → FAILURE                 │
│    ├── Tool 3 Execution (with retry) → SUCCESS                 │
│    └── Tool 4 Execution (with retry) → SUCCESS                 │
│                                                                 │
│  Result → Partial Success Reported to User                     │
│           (Tools 1, 3, 4 succeeded; Tool 2 failed)             │
└─────────────────────────────────────────────────────────────────┘
```

**Why Graceful Degradation?**

Chat tools are typically independent operations (e.g., search, file operations, calculations). A single tool failure shouldn't prevent the user from getting results from other successfully executed tools.

**Component-Level Retries**

Each tool has its own retry mechanism:

```
┌─────────────────────────────────────────────────────────────────┐
│        Component Retry Within Tool Execution                    │
├─────────────────────────────────────────────────────────────────┤
│  Tool Call                                                      │
│    ├── Attempt 1 → Failure                                      │
│    ├── Retry (Attempt 2) → Failure                              │
│    └── Retry (Attempt 3) → Failure → Tool Failed               │
│                                                                 │
│  Tool Failed → Error sent to LLM, other tools continue         │
└─────────────────────────────────────────────────────────────────┘
```

- Each tool retries **up to 2 times** (configurable via `config.RETRY_COUNT`, default: 2)
- Failed tools send error response to LLM but other tools continue
- Partial success IS reported to the user via successful tools

**Key Distinction:**
- **Atomic transactions**: Canvas operations - all must succeed or none do
- **Graceful degradation**: Chat tools - individual failures don't stop other tools

### 4. Cache-Aside Persistence

All state changes follow a **Cache-Aside** pattern where:

- Writes are recorded directly to the database.
- Immediate cache invalidation follows the write to ensure consistency.
- Proper transaction management and row-level locking are handled in `backend/db_wrapper.py` and `backend/cache_layer.py`.

### 5. Inference Separation of Concerns

**CRITICAL**: The `llama.cpp` inference server is a **completely separate repository and specialized service**. This application (My-AI) has **no responsibility** for orchestrating, starting, or managing the life cycle of the inference server.

The application interacts with inference solely as an external consumer:
1.  **URL Discovery**: Fetches the endpoint URL from `secrets/AI_URL` and `secrets/EMBEDDING_URL`.
2.  **Authentication**: Fetches keys from `secrets/AI_API_KEY` and `secrets/EMBEDDING_API_KEY`.
3.  **Consumption**: Sends OpenAI-compatible requests to the provided endpoints.

Any configuration or deployment logic for `llama.cpp` (e.g., GGUF model paths, GPU offloading, server parameters) belongs **exclusively** in the inference server's own repository and environment configuration.

## Component Architecture

### Backend Components

#### `backend/agents/`

Contains agent implementations that orchestate various operations:

- **chat.py**: Handles conversational AI interactions (uses canvas system)
- **research.py**: Manages research agent tasks (non-atomic, uses canvas system)

#### `backend/cache_system.py`

Implements session-level caching for SSE and high-throughput streaming (WAL support):

```python
# Cache operations pattern
cache.get(key)  # Get from cache
cache.set(key, value)  # Set with expiration
cache.invalidate(key)  # Invalidate on write
cache.cleanup_expired()  # Remove expired entries
```

**Note:** TTL IS implemented via `_is_expired()` and `cleanup_expired()` methods.

#### `backend/config.py`

Centralized configuration management:

- TTL settings for different cache types
- Database connection parameters
- Feature flags

**Note:** Retry count is defined in `config.py` as `RETRY_COUNT`

#### `backend/db_wrapper.py`

Primary database persistence layer (replaces deprecated `storage.py`):

```python
# Unified DB interface pattern
db.save_chat(chat_id, ...)
db.get_chat(chat_id)
db.update_chat(chat_id, ...)
```

**Note:** The database file is `{DATA_DIR}/chats.db` where `DATA_DIR` defaults to `./backend/data`.

#### `backend/cache_layer.py`

Implements the row-level caching with Cache-Aside pattern:

```python
# Cache operations pattern
cache_layer.get(table, row_id, fetch_fn, ttl=300)
cache_layer.invalidate(table, row_id)
```

#### `backend/llm.py`

LLM integration layer for AI model interactions.

#### `backend/file_manager.py`

Handles file uploads, storage sanitization, and content extraction. It orchestrates the background extraction pipeline and coordinates with the RAG system.
- **See**: `docs/file_management_directives.md` for detailed lifecycle and extraction logic.

#### `backend/rag.py`
Implements the hybrid search infrastructure (Vector + BM25) and coordinates retrieval across distributed collections.
- **See**: `docs/rag_directives.md` for architectural details on collections, search, and reciprocal rank fusion.

#### `backend/chunking.py`
Provides specialized logic for splitting text and code into semantically meaningful chunks. **Crucially, it acts as a Heuristic File Type Classifier**, bypassing file extensions to route content dynamically based on text layout and "syntax density" evaluations. (See `docs/file_management_directives.md`).

#### `backend/pdf_extractor.py`
A dedicated utility for high-fidelity text and structure extraction from PDF documents, utilizing `pdfplumber` and `PyPDF2`.

#### `backend/token_counter.py`
Handles precise token counting for multiple model architectures to ensure requests stay within context window limits.

#### `backend/utils.py`

Utility functions and helpers used across the application.

### Frontend Components

#### `static/`

Contains client-side resources:

- **index.html**: Main application UI
- **styles.css**: Styling and layout
- **script.js**: Client-side logic and API interactions

#### `tests/`
Contains the RAG evaluation framework and grid search utilities:
- **test_data_generator.py**: Synthetic dataset generation for RAG benchmarking.
- **test_rag_parameters.py**: Grid search execution and parameter optimization.
- **test_rag_hybrid.py**: Benchmarking for hybrid retrieval performance.

## Data Flow Architecture

### Read Operation Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────>│   Backend   │────>│   Cache     │
│   Request   │     │   Layer     │     │   (TTL)     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                              │
                              ┌───────────────┴───────────────┐
                              │ Cache Hit?                    │
                              └───────────────┬───────────────┘
                         Yes ┌───────────────┐│ No
                              ▼               ▼
                         ┌─────────────┐ ┌─────────────┐
                         │ Return      │ │   Query     │
                         │ Cached Data │ │   Database  │
                         └─────────────┘ └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │ Update      │
                                         │ Cache       │
                                         └─────────────┘
```

### Write Operation Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────>│   Backend   │────>│  Write      │
│   Request   │     │   Layer     │     │   Mechanism │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                              │
                              ┌───────────────┴───────────────┐
                              │ Update Cache                │
                              │ Invalidate Old Entries      │
                              └─────────────────────────────┘
```

### Tool Execution Flow (Atomic)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────>│   Agent     │────>│   Tool      │
│   Request   │     │   Router    │     │   Execute   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                              │
                              ┌───────────────┴───────────────┐
                              │ Success?                      │
                              └───────────────┬───────────────┘
                         Yes ┌───────────────┐│ No
                              ▼               ▼
                         ┌─────────────┐ ┌─────────────┐
                         │ Return      │ │ Retry       │
                         │ Result      │ │ (max: 2)    │
                         └─────────────┘ └──────┬──────┘
                                                │
                              ┌───────────────┴───────────────┐
                              │ Retry Count < Max?          │
                              └───────────────┬───────────────┘
                         Yes ┌───────────────┐│ No
                              ▼               ▼
                         ┌─────────────┐ ┌─────────────┐
                         │ Retry       │ │ Return      │
                         │ Operation   │ │ Failure     │
                         └─────────────┘ └─────────────┘
```

## Configuration Architecture

### Retry Configuration

**Note:** Retry count is defined in `config.py` as `RETRY_COUNT`.

```python
# Cache TTL settings
CACHE_ENTRY_TTL_SECONDS = 3600  # 1 hour default
CACHE_CLEANUP_INTERVAL = 300    # 5 min cleanup
```

### Cache Configuration

- **Default TTL**: Configurable per cache type
- **Invalidation Strategy**: Write-through with immediate cache update, TTL-based expiration
- **Expiration**: Automatic based on TTL - expired entries fall back to DB
- **Freshness**: Cache is authoritative while valid (within TTL), DB is fallback on TTL expiry

## Error Handling Strategy

### Retry Logic

- **Maximum retries**: 2 (configurable)
- **Retry delay**: Exponential backoff (if applicable)
- **Failure acknowledgment**: Clear error message to client
- **Error taxonomy**: Documented in `docs/error_handling.md`

### Cache-DB Consistency

- **Primary source**: Cache (authoritative while within TTL)
- **Fallback source**: Database (used when cache expired or unavailable)
- **Sync mechanism**: Write-through ensures cache is updated before DB; TTL expiration triggers DB fallback

**Note:** The cache system (`cache_system.py`) implements TTL via `_is_expired()` and `cleanup_expired()` methods.

## Exception: Research Agent and Chat Agent

There are **two exceptions** to the atomic transaction model:

### Research Agent
- Long-running, multi-step process (Reflection, Triage, Writing, Summary)
- Uses different persistence requirements (progressive updates)
- Partial success is expected and reported during execution
- Documented separately in `docs/research_agent.md`

### Chat Agent (Tool Execution)
- Uses **graceful degradation** for tool execution
- Individual tool failures do NOT stop other tools
- Partial success IS reported via successful tools
- Documented in `docs/chat_agent.md`

**Other operations (canvas operations) follow the atomic transaction model.**

## Extension Points

### Adding New Tools

1. Define tool in `backend/tools.py`
2. Add retry configuration if needed
3. Ensure atomic operation design
4. Update cache invalidation logic

### Adding New Agents

1. Create agent in `backend/agents/`
2. Implement cache/DB interaction patterns
3. Add to agent router
4. Document specific requirements

### Adding New Cache Types

1. Define TTL in `config.py`
2. Implement key naming convention
3. Add invalidation rules
4. Update cache system

## Docker Infrastructure

The application is orchestrated using Docker Compose, isolating components into specialized services.

### Core Stack (`docker-compose.yml`)

- **`app`**: The main Flask backend container. Orchestrates agents, handles API requests, and manages RAG/File processes.
- **`bastion_ssh`**: A secure SSH entry point for administrative access.
- **`tavily_mcp`**: Isolated container running the Tavily MCP server for web search.
- **`playwright_mcp`**: Isolated container running the Playwright MCP server for headless browsing.

### Optimization Stack (`docker/docker-compose.testing.yml`)

- **`rag_grid_search`**: A specialized, ephemeral service used for RAG hyperparameter optimization. It runs evaluation pipelines against synthetic datasets to tune retrieval settings.

## Security Considerations

- All writes go through validated mechanism
- Cache TTL prevents stale data exposure
- Retry mechanism prevents resource exhaustion
- Proper error handling avoids information leakage

## Performance Considerations

- **Cache-first**: Reduces DB load
- **Atomic tools**: Predictable execution time
- **Configurable retries**: Tunable for workload
- **TTL management**: Automatic cleanup (implemented in `cache_system.py` via `_is_expired()` and `cleanup_expired()`)

## Future Improvements

- Add circuit breaker pattern for external dependencies
- Implement cache warming for critical data
- Add monitoring and metrics for cache hit rates
- Enhance error handling with detailed taxonomy
