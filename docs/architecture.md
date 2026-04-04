# Application Architecture (v3.0.0)

**Note:** This document may contain outdated information. The code is the source of truth. For discrepancies, see `IMPLEMENTATION_DISCREPANCIES.md`.

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
- **2 retry attempts** (hardcoded in `error_handling.py` as `max_retries=2`) before failure acknowledgment
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

**Note:** Retry count is hardcoded in `error_handling.py` as `max_retries=2`

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

#### `backend/utils.py`

Utility functions and helpers used across the application.

### Frontend Components

#### `static/`

Contains client-side resources:

- **index.html**: Main application UI
- **styles.css**: Styling and layout
- **script.js**: Client-side logic and API interactions

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

**Note:** Retry count is hardcoded in `error_handling.py` as `max_retries=2`. There is no `RETRY_COUNT` configuration variable in `config.py`.

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
