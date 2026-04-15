# Error Handling Directives

## Overview

This document defines the error handling taxonomy, retry policies, error propagation rules, and best practices for all agents working with error handling in the system.

## Error Taxonomy

### Retryable Errors

These errors should trigger automatic retry with backoff:

| Error Type | Description | Retry Count | Backoff |
|------------|-------------|-------------|---------|
| `database_locked` | SQLite "database is locked" error | 5 | Exponential (0.1s, 0.2s, 0.4s, 0.8s, 1.6s) |
| `network_timeout` | Network timeout errors | 3 | Exponential (1s, 2s, 4s) |
| `connection_reset` | Connection reset by peer | 3 | Exponential (0.5s, 1s, 2s) |
| `rate_limited` | API rate limit responses | 3 | Exponential (5s, 10s, 20s) |
| `temporary_failure` | Transient service failures | 3 | Exponential (1s, 2s, 4s) |

**Rule 1: Only retry known retryable errors**

Do not retry errors that are not in the retryable list.

**Rule 2: Atomic transaction failures are non-retryable at component level**

Once a component fails after exhausting retries, the entire transaction fails.

```python
RETRYABLE_ERRORS = [
    'database_locked',
    'network_timeout',
    'connection_reset',
    'rate_limited',
    'temporary_failure'
]

def is_retryable(error_type):
    return error_type in RETRYABLE_ERRORS
```

### Non-Retryable Errors

These errors should NOT be retried - fail immediately:

| Error Type | Description | Action |
|------------|-------------|---------|
| `validation_error` | Invalid input data | Return error to user |
| `permission_denied` | Authz failure | Return error to user |
| `not_found` | Resource does not exist | Return error to user |
| `schema_error` | Data structure mismatch | Log and return error |
| `configuration_error` | Invalid config | Log and fail |
| `internal_error` | Unhandled exception | Log and fail |

### Tool Error Handling (Actual Implementation)

The actual implementation uses **graceful degradation** for tool errors:

| Error Type | Description | Action |
|------------|-------------|---------|
| `tool_execution_error` | Tool crashed during execution | Send error to LLM as tool result, continue with other tools |
| `tool_timeout` | Tool exceeded timeout | Send error to LLM as tool result, continue with other tools |

When a tool fails after exhausting retries:
1. The error is formatted as a tool result
2. The error is sent to the LLM for processing
3. Other tools in the same turn continue to execute
4. The turn completes with partial results if some tools succeeded

This allows users to get partial value even when some tools fail (e.g., if `search_web` is rate-limited, other tools like `manage_canvas` or `get_time` can still succeed).

**Rule 3: Never retry non-retryable errors**

```python
NON_RETRYABLE_ERRORS = [
    'validation_error',
    'permission_denied',
    'not_found',
    'schema_error',
    'configuration_error',
    'internal_error'
]

def is_retryable(error_type):
    if error_type in NON_RETRYABLE_ERRORS:
        return False
    return True
```

### Tool-Specific Errors

These errors are specific to tool execution:

| Error Type | Description | Action |
|------------|-------------|---------|
| `tool_execution_error` | Tool crashed during execution | Retry (up to 2 times) |
| `tool_timeout` | Tool exceeded timeout | Retry (up to 2 times) |
| `tool_not_found` | Tool not registered | Fail immediately |
| `tool_invalid_args` | Invalid tool arguments | Fail immediately |

## Retry Mechanism

### Retry Configuration

Retry parameters are configurable via `backend/config.py`:

```python
# In config.py
RETRY_COUNT = int(os.getenv("RETRY_COUNT", 2))  # Default for tool operations
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", 1.0))
```

The `execute_with_retry()` function in `error_handling.py` uses `config.RETRY_COUNT` as its default.

**Rule 5: Use configured retry count**

Always use the configured retry count from `config.py`.

```python
from backend import config

max_retries = config.RETRY_COUNT  # Use config value (default: 2)
```

### Exponential Backoff Pattern

Use exponential backoff for all retryable errors:

```python
import time
import random

def execute_with_retry(func, max_retries=2, backoff_base=1.0):
    """Execute with exponential backoff retry."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                raise  # Last attempt, re-raise

            # Exponential backoff with jitter
            delay = backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)
```

**Rule 6: Always use jitter**

Add random jitter to prevent thundering herd:

```python
# Good: With jitter
delay = backoff_base * (2 ** attempt) + random.uniform(0, 0.5)

# Bad: No jitter - all clients retry at same time
delay = backoff_base * (2 ** attempt)
```

### Database Locked Retry

Special handling for SQLite database locked errors uses **5 retries** with exponential backoff (0.1s, 0.2s, 0.4s, 0.8s, 1.6s) and jitter:

```python
import sqlite3
import time
import random
from backend import config

def safe_db_operation(operation, max_retries=5):
    """Execute DB operation with retry for locked errors."""
    backoff_base = 0.1
    for attempt in range(max_retries):
        try:
            return operation()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = backoff_base * (2 ** attempt) + random.uniform(0.01, 0.2)
                time.sleep(delay)
                continue
            raise  # Not a locked error or last attempt
```

## Error Classification

### Classification Rules

**Rule 7: Classify errors at the point of detection**

Every error handler should classify the error:

```python
def handle_operation_error(error):
    """Classify and handle error."""
    if isinstance(error, sqlite3.OperationalError):
        if "database is locked" in str(error):
            error_type = 'database_locked'
        else:
            error_type = 'database_error'
    elif isinstance(error, TimeoutError):
        error_type = 'network_timeout'
    elif isinstance(error, PermissionError):
        error_type = 'permission_denied'
    else:
        error_type = 'internal_error'

    return error_type
```

**Rule 8: Use specific error types**

Prefer specific error types over generic ones:

```python
# Good: Specific
error_type = 'validation_error'

# Bad: Too generic
error_type = 'error'
```

### Error Chain Handling

When errors are wrapped/chained, examine the cause:

```python
def get_root_error(error):
    """Extract the root cause from error chain."""
    while error.__cause__:
        error = error.__cause__
    return error
```

## Error Propagation

### Propagation Rules

**Rule 9: Propagate errors to appropriate layer**

- **Tool layer**: Return error dict to agent
- **API layer**: Return HTTP error response
- **UI layer**: Show user-friendly message

```python
# Tool layer return
def execute_tool(tool_name, args):
    try:
        result = run_tool(tool_name, args)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": classify(e)}
```

**Rule 10: Never propagate internal exceptions to users**

```python
# Bad: Propagate raw exception
raise Exception(f"Failed: {e}")

# Good: User-friendly message
logger.error(f"Operation failed: {e}")
return "Sorry, something went wrong. Please try again."
```

**Rule 11: Preserve error details for debugging**

```python
def handle_error(error, context=None):
    """Log full details, return user message."""
    # Log full error for debugging
    logger.error(f"Error in {context}: {error}", exc_info=True)

    # Return user-friendly message
    if isinstance(error, ValidationError):
        return "Invalid input. Please check your values."
    elif isinstance(error, TimeoutError):
        return "Operation timed out. Please try again."
    else:
        return "An error occurred. Please try again later."
```

## Error Response Format

### Standard Error Response

All errors should follow this format:

```json
{
    "success": false,
    "error": "User-friendly error message",
    "error_type": "validation_error",
    "details": {
        // Optional: Additional context for developers
        "field": "email",
        "value": "invalid-email"
    },
    "retryable": true
}
```

**Fields:**
- `success`: Always `false` for errors
- `error`: User-friendly message
- `error_type`: Classification for handling
- `details`: Optional context (may be omitted)
- `retryable`: Whether client can retry

### HTTP Error Responses

For API endpoints, map error types to HTTP status codes:

| Error Type | Status Code |
|------------|-------------|
| `validation_error` | 400 Bad Request |
| `permission_denied` | 403 Forbidden |
| `not_found` | 404 Not Found |
| `rate_limited` | 429 Too Many Requests |
| `internal_error` | 500 Internal Server Error |
| `network_timeout` | 504 Gateway Timeout |

```python
def http_error_response(error_type, error_message):
    """Map error type to HTTP response."""
    status_map = {
        'validation_error': 400,
        'permission_denied': 403,
        'not_found': 404,
        'rate_limited': 429,
        'internal_error': 500,
        'network_timeout': 504
    }

    status = status_map.get(error_type, 500)
    return {
        "success": False,
        "error": error_message,
        "error_type": error_type
    }, status
```

## Logging

### Logging Rules

**Rule 12: Log errors with full context**

```python
def log_error(error, context=None, extra=None):
    """Log error with full context."""
    logger = logging.getLogger(__name__)

    log_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': time.time()
    }

    if context:
        log_data['context'] = context

    if extra:
        log_data.update(extra)

    logger.error(f"Error occurred: {error}", exc_info=True, extra=log_data)
```

**Rule 13: Use appropriate log levels**

| Level | Use Case |
|-------|----------|
| `debug` | Detailed debugging info |
| `info` | Normal operation (not errors) |
| `warning` | Recoverable issues |
| `error` | Errors that are handled |
| `critical` | Unhandled critical failures |

**Rule 14: Never log sensitive data**

```python
# Bad: Log sensitive data
logger.error(f"User {user.password} failed login")

# Good: Log safely
logger.error(f"User {user.username} failed login")
```

### Error Logging Format

Standard error log format:

```
ERROR: [timestamp] - [error_type] - [message] - context: {context}
Traceback (most recent call last):
  ...
```

## Circuit Breaker Pattern

### When to Use

Use circuit breaker for:
- External API calls (Tavily, etc.)
- Unreliable dependencies
- Cascading failure prevention

**Rule 15: Implement circuit breaker for external calls**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half-open'
            else:
                raise CircuitOpenError("Circuit is open")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def on_success(self):
        self.failure_count = 0
        self.state = 'closed'

    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
```

## Best Practices

### 1. Always Classify Errors

```python
def handle_operation():
    try:
        return do_operation()
    except ValidationError as e:
        return handle_validation_error(e)
    except TimeoutError as e:
        return handle_timeout_error(e)
    except Exception as e:
        return handle_unexpected_error(e)
```

### 2. Use Context Managers for Error Handling

```python
from contextlib import contextmanager

@contextmanager
def error_handler(operation_name):
    try:
        yield
    except Exception as e:
        log_error(e, context=operation_name)
        raise
```

### 3. Provide User-Friendly Messages

```python
def handle_error(error):
    """Convert technical error to user message."""
    error_messages = {
        'validation_error': 'Please check your input and try again.',
        'database_locked': 'Database is busy. Please try again.',
        'network_timeout': 'Connection timed out. Please check your internet.',
        'internal_error': 'Something went wrong. Our team has been notified.'
    }

    error_type = classify_error(error)
    return error_messages.get(error_type, 'An error occurred.')
```

### 4. Log Stack Traces

Always log full stack traces for debugging:

```python
logger.error("Operation failed", exc_info=True)
```

### 5. Don't Suppress Exceptions

```python
# Bad: Silently swallowing errors
try:
    do_something()
except:
    pass

# Good: At least log the error
try:
    do_something()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise
```

## Tool Error Handling

### Tool Execution Errors

Tools have specific error handling requirements:

```python
def execute_tool(tool_name, args):
    """Execute a tool with proper error handling."""
    try:
        tool = get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        result = tool.run(args)
        return {"success": True, "result": result}

    except ToolTimeout as e:
        return {"success": False, "error": "Tool timed out", "error_type": "tool_timeout"}
    except ToolError as e:
        return {"success": False, "error": str(e), "error_type": "tool_error"}
    except Exception as e:
        logger.error(f"Unexpected tool error: {e}")
        return {"success": False, "error": "Unexpected error occurred"}
```

### Tool Retry Policy

Tools should retry on transient failures:

```python
def tool_with_retry(tool_func, max_retries=2):
    """Execute tool with retry."""
    for attempt in range(max_retries + 1):
        try:
            return tool_func()
        except ToolTransientError:
            if attempt == max_retries:
                raise
            time.sleep(0.5 * (attempt + 1))
```

## Testing Error Handling

### Testing Retry Logic

```python
def test_retry_on_failure():
    """Test that retries work correctly."""
    call_count = 0

    def failing_then_succeeding():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TemporaryFailureError()
        return "success"

    result = execute_with_retry(failing_then_succeeding, max_retries=3)
    assert result == "success"
    assert call_count == 3
```

### Testing Error Classification

```python
def test_error_classification():
    """Test that errors are classified correctly."""
    assert classify_error(ValidationError()) == 'validation_error'
    assert classify_error(TimeoutError()) == 'network_timeout'
    assert classify_error(Exception()) == 'internal_error'
```

## Error Handling Checklist

Before deploying code, verify:

- [ ] All errors are classified
- [ ] Retryable errors have retry logic
- [ ] Non-retryable errors fail fast
- [ ] User messages are user-friendly
- [ ] Stack traces are logged
- [ ] No sensitive data is logged
- [ ] Circuit breakers are in place for external calls
- [ ] Error responses follow standard format
