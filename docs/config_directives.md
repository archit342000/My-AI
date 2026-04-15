# Configuration Directives



## Overview

This document defines the configuration architecture, patterns for adding new settings, and rules for how agents should read and use configuration values.

## Configuration Architecture

### Central Configuration Module

**Location:** `backend/config.py`

All configuration values are defined in a single, centralized module. This ensures:
- Single source of truth for all settings
- Easy to tune behavior without code changes
- Consistent defaults across the application
- Environment-based overrides possible

### Configuration Categories

Configuration is organized into logical sections:

1. **Retry & Resilience** - Error handling and retry logic
2. **Cache & TTL** - Caching behavior and expiration
3. **Research Agent** - Research-specific settings
4. **LLM & API** - Model and API connection settings
5. **Canvas & Storage** - Canvas system configuration
6. **Logging & Monitoring** - Observability settings

### File Location

```
backend/config.py
```

**Rule 1: All configuration must be in backend/config.py**

Never import from other locations. Never use hardcoded values.

## Configuration Structure

### Core Structure Pattern

```python
# backend/config.py

# Retry Configuration
RETRY_COUNT = 2
RETRY_DELAY_SECONDS = 1

# Cache Configuration
CACHE_ENABLED = True
DEFAULT_TTL_SECONDS = 300

# Database Configuration
DATABASE_PATH = "data/app.db"

# ... more configurations
```

### Configuration Sections

#### 1. Retry & Resilience

```python
# Retry settings
RETRY_COUNT = 2              # Default retry count for general operations
CACHE_RETRY_COUNT = 2        # Retry count for cache operations
CIRCUIT_FAILURE_THRESHOLD = 5  # Circuit breaker failure threshold
CIRCUIT_RECOVERY_TIMEOUT = 30.0  # Circuit breaker recovery timeout (seconds)

# Research retry settings
RESEARCH_MAX_RETRIES = 3     # Research agent specific retry count
RESEARCH_MAX_PLAN_RETRIES = 3  # Research plan generation retries
```

**Note:** `RETRY_COUNT` is defined in `config.py` and used throughout the codebase. The `execute_with_retry()` function uses this configurable value.

#### 2. Cache & TTL Configuration

```python
# Cache settings
CACHE_ENABLED = True
CACHE_ENTRY_TTL_SECONDS = 3600  # TTL for cache entries (1 hour)
CACHE_CLEANUP_INTERVAL = 300    # Cache cleanup interval (5 minutes)
DEFAULT_TTL_SECONDS = CACHE_ENTRY_TTL_SECONDS  # Alias for backward compatibility

# Research cache TTLs
RESEARCH_CACHE_TTL = 3600    # Research state cached for 1 hour
CHAT_CACHE_TTL = 600         # Chat cache TTL for 10 minutes
```

**Rule 3: All cache entries must have TTL**

Never store data in cache without expiration.

#### 2.1 Memory Configuration

```python
# Memory per-turn limits (prevent unbounded memory accumulation)
MEMORY_MAX_ADD_PER_TURN = 5    # Maximum memory additions per turn
MEMORY_MAX_EDIT_PER_TURN = 5   # Maximum memory edits per turn
MEMORY_MAX_DELETE_PER_TURN = 5 # Maximum memory deletions per turn
```

**Note:** These settings limit the number of memory operations per turn to prevent unbounded accumulation. They are applied in `chat.py` during memory processing.

#### 3. Research Agent Configuration

```python
# Section limits
RESEARCH_MAX_QUERIES_PER_SECTION = 2
RESEARCH_MAX_TOTAL_QUERIES = 10
RESEARCH_MAX_GAPS_PER_SECTION = 2

# Content limits
RESEARCH_CONTENT_BUDGET_REGULAR = 50000
RESEARCH_CONTENT_BUDGET_DEEP = 80000
RESEARCH_CONTENT_CHUNK_LIMIT = 15000

# Triage limits
RESEARCH_TRIAGE_MAX_FACTS = 25

# Audit limits
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3

# Meander detection thresholds (TOKENS)
# If reasoning exceeds the limit AND content output is below CONTENT_THRESHOLD,
# the response is considered "meandering" and gets retried or truncated.
RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_TRIAGE_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS = 5000
RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS_TOKENS = 3750
RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS = 1000
RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS = RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS
```

**Rule 4: Research agent values are in config.py**

All research-specific settings are in config.py, not in the research code itself.

#### 3.1 Additional Research Configuration

```python
# Research token limits
RESEARCH_MAX_TOKENS_SCOUT = 16384
RESEARCH_MAX_TOKENS_PLANNER = 16384
RESEARCH_MAX_TOKENS_REFLECTION = 16384
RESEARCH_MAX_TOKENS_TRIAGE = 16384
RESEARCH_MAX_TOKENS_STEP_WRITER = 16384
RESEARCH_MAX_TOKENS_SUMMARY = 16384
RESEARCH_MAX_TOKENS_SYNTHESIS = 16384
RESEARCH_MAX_TOKENS_VISION = 16384
RESEARCH_MAX_TOKENS_AUDIT = 16384

# Research sampling settings
RESEARCH_SAMPLING_SCOUT = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_PLANNER = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_REFLECTION = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_TRIAGE = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_STEP_WRITER = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_SUMMARY = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_SYNTHESIS = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_VISION = "top_p:0.95,temp:0.7"
RESEARCH_SAMPLING_AUDIT = "top_p:0.95,temp:0.7"

# Research Tavily search limits
RESEARCH_TAVILY_MAX_RESULTS_SCOUT = 5
RESEARCH_TAVILY_MAX_RESULTS_PLANNER = 5
RESEARCH_TAVILY_MAX_RESULTS_REFLECTION = 3
RESEARCH_TAVILY_MAX_RESULTS_TRIAGE = 3
RESEARCH_TAVILY_MAX_RESULTS_STEP_WRITER = 5
RESEARCH_TAVILY_MAX_RESULTS_SUMMARY = 5
RESEARCH_TAVILY_MAX_RESULTS_SYNTHESIS = 10
RESEARCH_TAVILY_MAX_RESULTS_VISION = 5
RESEARCH_TAVILY_MAX_RESULTS_AUDIT = 5

# Research context history
RESEARCH_CONTEXT_HISTORY_SCOUT = 10
RESEARCH_CONTEXT_HISTORY_PLANNER = 10
RESEARCH_CONTEXT_HISTORY_REFLECTION = 10
RESEARCH_CONTEXT_HISTORY_TRIAGE = 10
RESEARCH_CONTEXT_HISTORY_STEP_WRITER = 10
RESEARCH_CONTEXT_HISTORY_SUMMARY = 10
RESEARCH_CONTEXT_HISTORY_SYNTHESIS = 10
RESEARCH_CONTEXT_HISTORY_VISION = 10
RESEARCH_CONTEXT_HISTORY_AUDIT = 10
```

#### 3.2 Research LLM Sampling Parameters

```python
# Research sampling parameters (used for fine-tuning LLM behavior)
RESEARCH_SAMPLING_TEMPERATURE = 0.7        # Controls randomness (0.0 = deterministic, 1.0 = random)
RESEARCH_SAMPLING_MIN_P = 0.1              # Minimum probability threshold
RESEARCH_SAMPLING_DRY_MULTIPLIER = 0.8     # Dry sampling multiplier
RESEARCH_SAMPLING_DRY_BASE = 1.75          # Dry sampling base value
RESEARCH_SAMPLING_DRY_ALLOWED_LENGTH = 3   # Dry sampling allowed length
RESEARCH_SAMPLING_XTC_PROBABILITY = 0.1    # XTC (Extra Tolerance Chance) probability
RESEARCH_SAMPLING_REPEAT_PENALTY = 1.1     # Penalty for repeated tokens
```

**Note:** These sampling parameters are used by the research agent to control LLM generation behavior. Each research phase may override these with its own sampling settings.

#### 4. LLM & API Configuration

```python
# AI Inference settings
AI_URL = ""  # Default local LLM endpoint fetched from environment
AI_API_KEY = ""  # API key for external services fetched from environment

# Model settings
DEFAULT_MODEL = "qwen2.5-coder-32b"
VISION_MODEL = None  # Optional vision model

# MCP client settings
TAVILY_API_KEY = ""
PLAYWRIGHT_HEADLESS = True
```

**Rule 5: API URLs are configurable**

Agents should read API URLs from config.py, not hardcode them.

#### 4.1 Search Configuration

```python
# Tavily search configuration
TAVILY_BASE_URL = "https://api.tavily.com"  # Tavily API base URL
SEARCH_DEPTH = "basic"                       # Search depth: "basic" or "advanced"
MAX_SEARCH_RESULTS = 5                       # Maximum search results per query
MIN_SEARCH_RESULTS = 3                       # Minimum search results required
INCLUDE_ANSWER = "advanced"                  # Include answer in search results
INCLUDE_RAW_CONTENT = True                   # Include raw page content
RELEVANCE_THRESHOLD = 0.6                    # Minimum relevance score for results
SEARCH_CACHE_TTL = 3600                      # Search result cache TTL (1 hour)
```

**Note:** Search configuration is used by the research agent for web searches via Tavily API.

#### 5. Canvas Configuration

```python
# Canvas settings
CANVAS_MAX_HISTORY = 50
CANVAS_AUTO_SAVE_INTERVAL = 30  # Seconds between auto-saves
CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT = 5000  # Max chars of canvas content in context
```

#### 6. Tool Execution Configuration

```python
# Tool execution settings
MAX_TOOL_ROUNDS = 8          # Maximum tool rounds per conversation
```

**Rule 7: Tool round limits prevent infinite loops**

The chat agent limits tool execution to `MAX_TOOL_ROUNDS` to prevent infinite loops.

#### 7. Logging Configuration

```python
# Logging settings
LOG_LEVEL = "INFO"
LOG_TO_FILE = True
LOG_DIR = "logs"
```

#### 8. Timeout Configuration

```python
# LLM timeout settings (in seconds, None = no timeout)
TIMEOUT_LLM_BLOCKING = None   # Blocking LLM calls
TIMEOUT_LLM_ASYNC = None      # Async LLM calls

# Tavily search timeout settings (in seconds)
TIMEOUT_TAVILY_SEARCH = 15        # Basic search
TIMEOUT_TAVILY_SEARCH_ASYNC = 60  # Async search
TIMEOUT_TAVILY_MAP = 150          # Map/area search
TIMEOUT_TAVILY_EXTRACT = 60       # Content extraction

# Web scraping and fetch timeouts (in seconds)
TIMEOUT_WEB_SCRAPE = 15   # Web page scrape
TIMEOUT_IMAGE_FETCH = 15  # Image download
TIMEOUT_URLHAUS = 5       # URLhaus security check
```

**Note:** Timeout settings prevent operations from hanging indefinitely. Set to `None` for no timeout or a numeric value for maximum seconds to wait.

#### 9. Content Length Thresholds

```python
# Minimum content length requirements (characters)
RESEARCH_EXTRACT_MIN_RAW_CONTENT = 50      # Raw web content
RESEARCH_EXTRACT_MIN_PDF_CONTENT = 100     # PDF content
RESEARCH_EXTRACT_MIN_TAVILY_CONTENT = 100  # Tavily search results
RESEARCH_MAP_MIN_CONTENT = 100             # Map/area search content

# Content quality thresholds
RESEARCH_CONTENT_MIN_LENGTH_REGULAR = 50   # Regular content minimum
RESEARCH_CONTENT_MIN_LENGTH_DEEP = 200     # Deep research minimum
```

**Note:** Content length thresholds ensure minimum quality for research results. Shorter content may be rejected or flagged for review.

## How to Read Configuration

### Import Pattern

**Rule 6: Always import from backend.config**

```python
from backend import config

# Use configuration
retries = config.RETRY_COUNT
ttl = config.DEFAULT_TTL_SECONDS
```

**Never do this:**

```python
# WRONG - Hardcoded value
RETRY_COUNT = 2

# WRONG - Wrong import path
from config import RETRY_COUNT
```

### Reading Configuration Values

```python
from backend import config

# Read a setting
max_retries = config.RESEARCH_MAX_RETRIES

# Use in code
for attempt in range(1, config.RESEARCH_MAX_RETRIES + 1):
    try:
        result = perform_operation()
        break
    except Exception as e:
        if attempt == config.RESEARCH_MAX_RETRIES:
            raise
        time.sleep(config.RETRY_DELAY_SECONDS)
```

### Configuration with Defaults

**Rule 7: Use sensible defaults when configuration is missing**

```python
from backend import config
import os

# Configuration with environment override
ai_url = os.environ.get("AI_URL") or config.AI_URL

# Configuration with fallback
timeout = os.environ.get("TIMEOUT") or config.TIMEOUT_LLM_BLOCKING
```

## Adding New Configuration

### When to Add New Configuration

Add new configuration when:

1. **Tunable behavior** - The value can be adjusted without code changes
2. **Environment-specific** - Values differ between environments
3. **User-configurable** - Users may want to change the value
4. **Testing** - Values differ during testing

### How to Add New Configuration

**Step 1: Choose the right section**

Group related settings together:
- Retry settings → Retry section
- Cache settings → Cache section
- Research settings → Research section

**Step 2: Add the configuration**

```python
# backend/config.py

# New setting in appropriate section
NEW_SETTING_NAME = default_value  # With docstring if needed
```

**Step 3: Document the setting**

Add a comment explaining:
- What the setting controls
- Valid range (if applicable)
- Default rationale

```python
# Maximum number of concurrent research queries
RESEARCH_MAX_CONCURRENT_QUERIES = 3  # Balance speed vs resource usage
```

**Step 4: Update documentation**

If the setting is significant, update the relevant directive files:
- Add to config_directives.md
- Update any component-specific documentation

### Configuration Naming Conventions

**Rule 8: Follow naming conventions**

| Pattern | Description | Example |
|---------|-------------|---------|
| `RETRY_*` | Retry settings (hardcoded in error_handling.py) | N/A |
| `CACHE_*` | Cache settings | `CACHE_ENTRY_TTL_SECONDS`, `CACHE_CLEANUP_INTERVAL` |
| `RESEARCH_*` | Research settings | `RESEARCH_MAX_QUERIES` |
| `AI_*` | AI settings | `AI_URL`, `AI_API_KEY` |
| `LOG_*` | Logging settings | `LOG_LEVEL`, `LOG_DIR` |
| `CANVAS_*` | Canvas settings | `CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT` |

**Rule 9: Use UPPER_SNAKE_CASE for all configuration**

```python
# CORRECT
MAX_RETRIES = 2
cache_ttl = 300  # WRONG - mixed case

# CORRECT
RESEARCH_MAX_QUERIES = 2
research_max_queries = 2  # WRONG - lowercase
```

### Configuration Defaults

**Rule 10: Document default rationale**

```python
# CORRECT - Explains why
RESEARCH_MAX_QUERIES_PER_SECTION = 2  # Balance between thoroughness and speed

# WRONG - No explanation
RESEARCH_MAX_QUERIES_PER_SECTION = 2
```

**Rule 11: Use sensible defaults**

- Start with conservative values
- Document why the default was chosen
- Allow override for power users

### Environment-Specific Configuration

**Rule 12: Support environment overrides via environment variables**

```python
import os
from backend import config

# Override configuration with environment variable
API_KEY = os.environ.get("API_KEY") or config.DEFAULT_API_KEY
```

## Configuration Validation

### Validation Patterns

**Rule 13: Validate configuration at startup**

```python
def validate_config():
    """Validate configuration values at startup."""
    errors = []

    if config.RETRY_COUNT < 0:
        errors.append("RETRY_COUNT must be non-negative")

    if config.DEFAULT_TTL_SECONDS < 60:
        errors.append("DEFAULT_TTL_SECONDS must be at least 60 seconds")

    if errors:
        raise ValueError("Invalid configuration: " + ", ".join(errors))
```

### Runtime Validation

**Rule 14: Validate configuration values before use**

```python
from backend import config

# Validate before use
if config.MAX_QUERIES > config.MAX_CONCURRENT_OPERATIONS:
    config.MAX_QUERIES = config.MAX_CONCURRENT_OPERATIONS

# Log warning if out of bounds
import logging
if config.MAX_QUERIES < 1:
    logging.warning("MAX_QUERIES is less than 1, using default")
    config.MAX_QUERIES = 1
```

## Configuration Best Practices

### 1. Use Configuration for Tunable Values

```python
# GOOD - Configuration for tunable value
max_items = config.ITEMS_PER_PAGE

# BAD - Hardcoded value
max_items = 10
```

### 2. Group Related Settings

```python
# GOOD - Grouped settings
RESEARCH_MAX_QUERIES = 10
RESEARCH_MAX_RESULTS = 50
RESEARCH_TIMEOUT_SECONDS = 300

# BAD - Mixed grouping
RESEARCH_MAX_QUERIES = 10
ITEMS_PER_PAGE = 20  # Not research-related
RESEARCH_MAX_RESULTS = 50
```

### 3. Use Meaningful Names

```python
# GOOD - Clear purpose
RESEARCH_CONTENT_BUDGET = 50000

# BAD - Unclear purpose
MAX_VAL = 50000
```

### 4. Avoid Magic Numbers

```python
# GOOD - Configuration for magic number
MAX_RETRIES = 3

for attempt in range(1, MAX_RETRIES + 1):
    # ...

# BAD - Magic number
for attempt in range(1, 4):
    # ...
```

### 5. Document Configuration Changes

```python
# GOOD - Documented change
# Updated to 3 after testing showed 2 insufficient for some queries
RESEARCH_MAX_RETRIES = 3

# BAD - No documentation
RESEARCH_MAX_RETRIES = 3
```

## Configuration Security

### Sensitive Configuration

**Rule 15: Never hardcode sensitive values**

```python
# CORRECT - From environment
AI_API_KEY = os.environ.get("AI_API_KEY")

# WRONG - Hardcoded
AI_API_KEY = "sk-..."  # DO NOT DO THIS
```

### Secret Management

```python
# CORRECT - Environment variable
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# CORRECT - From config with fallback
AI_API_KEY = config.AI_API_KEY or os.environ.get("AI_API_KEY")
```

### Environment Variables

Common environment variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `AI_API_KEY` | AI authentication | No |
| `TAVILY_API_KEY` | Tavily search API | For research |
| `PLAYWRIGHT_HEADLESS` | Playwright mode | No |
| `LOG_LEVEL` | Logging verbosity | No |

## Configuration Files

### Environment Files

**Rule 16: Use environment files for environment-specific settings**

```bash
# .env.development
LOG_LEVEL=DEBUG

# .env.production
LOG_LEVEL=INFO
```

### Loading Environment Files

```python
import os
from dotenv import load_dotenv

# Load environment file based on environment
env_file = f".env.{os.environ.get('ENVIRONMENT', 'development')}"
load_dotenv(env_file)
```

## Configuration Testing

### Testing Configuration Changes

**Rule 17: Test with different configuration values**

```python
import pytest
from backend import config

def test_retry_count():
    """Test that retry count works correctly."""
    # RETRY_COUNT is configurable via config.RETRY_COUNT (default: 2)
    # For testing, use monkeypatch to override: monkeypatch.setattr("backend.config.RETRY_COUNT", 3)
```

### Configuration Fixtures

```python
@pytest.fixture
def custom_config(monkeypatch):
    """Fixture to override configuration for testing."""
    monkeypatch.setattr("backend.config.CACHE_ENTRY_TTL_SECONDS", 600)
    monkeypatch.setattr("backend.config.RESEARCH_MAX_RETRIES", 5)
    yield
    # Cleanup
    monkeypatch.undo
```

## Configuration Migration

### Migrating Configuration Values

When changing configuration values:

1. **Update the default** in `config.py`
2. **Document the change** in the configuration comment
3. **Update documentation** in directive files
4. **Test thoroughly** with new values

### Versioned Configuration

For significant configuration changes:

```python
# Versioned configuration with migration
CONFIG_VERSION = 2

if CONFIG_VERSION < 2:
    # Migrate from old format
    migrate_config()
```

## Configuration Reference

### All Configuration Categories

| Category | Settings | File Location |
|----------|----------|---------------|
| Retry & Resilience | `RETRY_COUNT`, `CACHE_RETRY_COUNT`, `CIRCUIT_FAILURE_THRESHOLD`, `CIRCUIT_RECOVERY_TIMEOUT` | `backend/config.py` |
| Cache | `CACHE_ENTRY_TTL_SECONDS`, `CACHE_CLEANUP_INTERVAL`, `DEFAULT_TTL_SECONDS` | `backend/config.py` |
| Memory | `MEMORY_MAX_ADD_PER_TURN`, `MEMORY_MAX_EDIT_PER_TURN`, `MEMORY_MAX_DELETE_PER_TURN` | `backend/config.py` |
| Research | `RESEARCH_MAX_*`, `RESEARCH_CONTENT_*`, `RESEARCH_MEANDER_*`, `RESEARCH_TOKENS_*`, `RESEARCH_SAMPLING_*`, `RESEARCH_TAVILY_*`, `RESEARCH_CONTEXT_*` | `backend/config.py` |
| Research Sampling | `RESEARCH_SAMPLING_TEMPERATURE`, `RESEARCH_SAMPLING_MIN_P`, `RESEARCH_SAMPLING_DRY_*`, `RESEARCH_SAMPLING_XTC_PROBABILITY`, `RESEARCH_SAMPLING_REPEAT_PENALTY` | `backend/config.py` |
| Search | `TAVILY_BASE_URL`, `SEARCH_DEPTH`, `MAX_SEARCH_RESULTS`, `MIN_SEARCH_RESULTS`, `INCLUDE_ANSWER`, `INCLUDE_RAW_CONTENT`, `RELEVANCE_THRESHOLD`, `SEARCH_CACHE_TTL` | `backend/config.py` |
| Timeouts | `TIMEOUT_LLM_*`, `TIMEOUT_TAVILY_*`, `TIMEOUT_WEB_SCRAPE`, `TIMEOUT_IMAGE_FETCH`, `TIMEOUT_URLHAUS` | `backend/config.py` |
| Content Thresholds | `RESEARCH_EXTRACT_MIN_*`, `RESEARCH_CONTENT_MIN_*` | `backend/config.py` |
| Tool Execution | `MAX_TOOL_ROUNDS` | `backend/config.py` |
| LLM | `AI_URL`, `AI_API_KEY`, `DEFAULT_MODEL`, `VISION_MODEL` | `backend/config.py` |
| Embeddings | `EMBEDDING_URL` (MANDATORY), `EMBEDDING_API_KEY` (MANDATORY), `EMBEDDING_MAX_TOKENS_*` | `backend/config.py` |
| Canvas | `CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT`, `CANVAS_MAX_HISTORY`, `CANVAS_AUTO_SAVE_INTERVAL` | `backend/config.py` |
| Logging | `LOG_LEVEL`, `LOG_DIR` | `backend/config.py` |

### Configuration Lookup

**Rule 18: Always check config.py first**

Before using any value, check if it's in `config.py`:

```python
from backend import config

# Check config first
max_items = config.ITEMS_PER_PAGE

# Only hardcode if not in config
max_items = 10  # Only if not configurable
```

### RAG & Embeddings

Settings for vector search and retrieval optimization.

| Setting | Default | Description |
|---------|---------|-------------|
| `RAG_CHUNK_MAX_CHARS` | 2200 | Max characters per embedding chunk |
| `RAG_MIN_SEMANTIC_SCORE` | 0.40 | Min cosine similarity for retrieval |
| `RAG_DEDUP_THRESHOLD` | 0.80 | Similarity above which chunks are considered duplicates |
| `RAG_FETCH_MULTIPLIER` | 2 | Overfetch ratio for hybrid re-ranking |
| `RAG_DECAY_RATE` | 0.30 | Time-decay weight for older entries |
| `RAG_RETRIEVAL_LIMIT` | 500 | Hard cap on total retrieved chunks per turn |
| `RAG_MIGRATION_BATCH_SIZE` | 50 | Batch size for collection re-indexing |
| `HYBRID_SEARCH_ENABLED` | `True` | Enable BM25 + Vector fusion |
| `CODE_CHUNKING_ENABLED` | `True` | Enable syntax-aware chunking for code |
| `RAG_GRID_WORKERS` | 16 | (Experimental) Workers for grid search pipeline |

### File Upload & Extraction

Settings for user-uploaded files and processing.

| Setting | Default | Description |
|---------|---------|-------------|
| `FILE_UPLOAD_MAX_SIZE` | 100MB | Max size per individual file |
| `FILE_UPLOAD_ALLOWED_TYPES` | See list | Allowed MIME types |
| `FILE_RAG_ENABLED` | `True` | Index file content in RAG |
| `FILE_VISION_ENABLED` | `True` | Process images/video with VLM |
| `READ_FILE_CONTENT_LIMIT` | 10000 | Max chars returned to LLM from `read_file` |
| `PDF_PAGE_LIMIT` | 5 | Max pages extracted for vision analysis |
| `PDF_EXTRACTOR_ENABLED` | `True` | Enable text extraction from PDFs |
| `PDF_OCR_ENABLED` | `True` | Enable OCR fallback for scanned PDFs |

### Embedding Token Limits

Token constraints for embedding model requests.

| Setting | Default | Description |
|---------|---------|-------------|
| `EMBEDDING_MAX_TOKENS_CORE` | 1000 | Token limit for core memory |
| `EMBEDDING_MAX_TOKENS_RESEARCH` | 1000 | Token limit for research RAG |
| `EMBEDDING_MAX_TOKENS_FILE` | 1000 | Token limit for file RAG |

## Troubleshooting

### Configuration Not Taking Effect

**Common issues:**

1. **Wrong import path**
   ```python
   # WRONG
   from config import RETRY_COUNT

   # CORRECT
   from backend import config
   ```

2. **Environment variable not set**
   ```bash
   # Check environment variables
   echo $API_KEY
   ```

3. **Config file not loaded**
   ```python
   # Ensure config is loaded
   from backend import config
   ```

### Configuration Values Not Updating

**Common issues:**

1. **Module already imported**
   ```python
   # Reload module after config change
   import importlib
   import backend.config
   importlib.reload(backend.config)
   ```

2. **Environment variable precedence**
   ```python
   # Environment variables override config
   API_KEY = os.environ.get("API_KEY") or config.DEFAULT_API_KEY
   ```

## Summary

### Key Rules

1. **All configuration must be in `backend/config.py`**
2. **Retry count is configurable** via `RETRY_COUNT` in `config.py`
3. **All cache entries must have TTL**
4. **Research agent values are in config.py**
5. **AI URLs are configurable** (use `AI_URL`, not `API_URL`)
6. **Always import from `backend.config`**
7. **Use sensible defaults when configuration is missing**
8. **Follow naming conventions**
9. **Use UPPER_SNAKE_CASE for all configuration**
10. **Document default rationale**
11. **Never hardcode sensitive values**
12. **Support environment overrides**
13. **Validate configuration at startup**
14. **Validate configuration values before use**
15. **Test with different configuration values**

**Note:** This document may have discrepancies with the actual code. See `IMPLEMENTATION_DISCREPANCIES.md` for details.

### Best Practices

- Group related settings together
- Use meaningful names for configuration
- Avoid magic numbers
- Document configuration changes
- Use environment files for environment-specific settings

This ensures configuration is maintainable, testable, and easy to tune.
