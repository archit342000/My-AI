"""
Error Handling Module

Provides error classification, retry mechanisms with jitter, circuit breakers,
and standardized error responses per error_handling.md directives.
"""

import asyncio
import json
import time
import random
import sqlite3
import logging
import threading
from typing import Optional, Dict, Any, List, Callable, Awaitable

from backend import config

# =============================================================================
# ERROR CLASSIFICATION CONSTANTS
# =============================================================================

RETRYABLE_ERRORS: List[str] = [
    'database_locked',
    'network_timeout',
    'connection_reset',
    'rate_limited',
    'temporary_failure'
]

NON_RETRYABLE_ERRORS: List[str] = [
    'validation_error',
    'permission_denied',
    'not_found',
    'schema_error',
    'configuration_error',
    'internal_error'
]

ATOMIC_TRANSACTION_ERRORS: List[str] = [
    'atomic_transaction_failure',
    'component_failure'
]

# =============================================================================
# ERROR CLASSIFICATION FUNCTIONS
# =============================================================================

def classify_error(error: Exception) -> str:
    """
    Classify an exception into an error type.

    Args:
        error: The exception to classify

    Returns:
        String error type identifier
    """
    if isinstance(error, sqlite3.OperationalError):
        if "database is locked" in str(error):
            return 'database_locked'
        return 'database_error'

    elif isinstance(error, TimeoutError):
        return 'network_timeout'

    elif isinstance(error, ConnectionResetError):
        return 'connection_reset'

    elif isinstance(error, PermissionError):
        return 'permission_denied'

    elif isinstance(error, json.JSONDecodeError):
        return 'schema_error'

    elif isinstance(error, AttributeError):
        return 'validation_error'

    elif isinstance(error, KeyError):
        return 'not_found'

    else:
        return 'internal_error'


def is_retryable(error_type: str) -> bool:
    """
    Check if an error type should be retried.

    Args:
        error_type: The classified error type

    Returns:
        True if error should be retried, False otherwise
    """
    return error_type in RETRYABLE_ERRORS


def is_transaction_retryable(error_type: str) -> bool:
    """
    Check if an entire transaction should be retried.

    Component-level failures should not trigger transaction retries.
    Currently unused - reserved for future transaction management.

    Args:
        error_type: The classified error type

    Returns:
        True if entire transaction should retry, False otherwise
    """
    # Note: ATOMIC_TRANSACTION_ERRORS are not in RETRYABLE_ERRORS,
    # so this check is redundant but kept for explicit intent documentation.
    # Unused currently - reserved for future distributed transaction support.
    if error_type in ATOMIC_TRANSACTION_ERRORS:
        return False
    return is_retryable(error_type)


# =============================================================================
# RETRY WITH JITTER UTILITIES
# =============================================================================

def calculate_backoff(attempt: int, backoff_base: float, jitter: bool = True) -> float:
    """
    Calculate exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        backoff_base: Base delay in seconds
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = backoff_base * (2 ** attempt)
    if jitter:
        # Add jitter of 0 to 0.5 seconds
        delay += random.uniform(0, 0.5)
    return delay


def execute_with_retry(
    func,
    max_retries: int = config.RETRY_COUNT,
    backoff_base: float = 1.0,
    jitter: bool = True,
    retryable_types: Optional[List[str]] = None
):
    """
    Execute a function with exponential backoff retry.

    Args:
        func: The function to execute
        max_retries: Maximum retry attempts
        backoff_base: Base backoff time in seconds
        jitter: Whether to add random jitter
        retryable_types: Override list of retryable error types

    Returns:
        Result from func if successful

    Raises:
        Exception: From func if all retries exhausted
    """
    if retryable_types is None:
        retryable_types = RETRYABLE_ERRORS

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            error_type = classify_error(e)

            # Check if retryable
            if error_type not in retryable_types:
                raise  # Non-retryable, fail immediately

            if attempt == max_retries:
                raise  # Exhausted retries

            # Calculate and apply backoff
            delay = calculate_backoff(attempt, backoff_base, jitter=jitter)
            time.sleep(delay)


# =============================================================================
# CIRCUIT BREAKER PATTERN
# =============================================================================

class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and blocking calls."""
    pass


class CircuitBreaker:
    """
    Circuit breaker for external API calls to prevent cascading failures.

    States:
        - closed: Normal operation, calls proceed
        - open: Circuit is open, calls fail immediately
        - half-open: Testing if service has recovered

    Example:
        circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

        try:
            result = circuit.call(external_api_call)
        except CircuitOpenError:
            # Circuit is open, use fallback
            result = get_cached_result()
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time: Optional[float] = None
        self.state: str = 'closed'  # closed, open, half-open
        self._lock = threading.Lock()  # Lock to prevent concurrent state changes

    def call(self, func, *args, **kwargs):
        """
        Execute synchronous function through circuit breaker.

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function if successful

        Raises:
            CircuitOpenError: If circuit is open
            Exception: From function if it fails
        """
        with self._lock:
            # Check if we can proceed
            if self.state == 'open':
                if self._should_attempt_recovery():
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

    async def call_async(self, func: Callable, *args, **kwargs):
        """
        Execute asynchronous function through circuit breaker.

        Args:
            func: Asynchronous function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function if successful

        Raises:
            CircuitOpenError: If circuit is open
            Exception: From function if it fails
        """
        with self._lock:
            # Check if we can proceed
            if self.state == 'open':
                if self._should_attempt_recovery():
                    self.state = 'half-open'
                else:
                    raise CircuitOpenError("Circuit is open")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) > self.recovery_timeout

    def on_success(self):
        """Called when the protected function succeeds."""
        self.failure_count = 0
        self.state = 'closed'

    def on_failure(self):
        """Called when the protected function fails."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time
        }


# =============================================================================
# STANDARDIZED ERROR RESPONSES
# =============================================================================

USER_FRIENDLY_MESSAGES = {
    'database_locked': 'Database is busy. Please try again.',
    'network_timeout': 'Connection timed out. Please check your internet connection.',
    'connection_reset': 'Connection was reset. Please try again.',
    'rate_limited': 'Too many requests. Please wait a moment and try again.',
    'temporary_failure': 'Service temporarily unavailable. Please try again later.',
    'validation_error': 'Invalid input. Please check your values and try again.',
    'permission_denied': 'You do not have permission to perform this action.',
    'not_found': 'The requested resource was not found.',
    'schema_error': 'Invalid data format. Please try again.',
    'configuration_error': 'System configuration error. Please contact support.',
    'internal_error': 'An unexpected error occurred. Our team has been notified.',
    'atomic_transaction_failure': 'The operation could not be completed. Please try again.',
    'component_failure': 'A component failed. The operation was aborted.',
}


def get_user_friendly_message(error_type: str) -> str:
    """
    Get a user-friendly message for an error type.

    Args:
        error_type: The classified error type

    Returns:
        User-friendly error message
    """
    return USER_FRIENDLY_MESSAGES.get(error_type, 'An unexpected error occurred.')


def create_error_response(
    error: Exception,
    error_type: str,
    retryable: bool = False,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error: The original exception
        error_type: The classified error type
        retryable: Whether the error is retryable
        details: Optional additional context for developers

    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": get_user_friendly_message(error_type),
        "error_type": error_type,
        "retryable": retryable
    }

    if details:
        response["details"] = details

    return response


def http_status_for_error(error_type: str) -> int:
    """
    Map error type to HTTP status code.

    Args:
        error_type: The classified error type

    Returns:
        HTTP status code
    """
    status_map = {
        'validation_error': 400,
        'permission_denied': 403,
        'not_found': 404,
        'rate_limited': 429,
        'network_timeout': 504,
        'internal_error': 500,
        'database_error': 500,
        'database_locked': 503,
        'schema_error': 400,
        'configuration_error': 500,
        'atomic_transaction_failure': 500,
        'component_failure': 500
    }
    return status_map.get(error_type, 500)


# =============================================================================
# ERROR LOGGING UTILITIES
# =============================================================================

def log_error(
    error: Exception,
    error_type: str,
    context: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Log error with full context for debugging.

    Args:
        error: The exception that occurred
        error_type: The classified error type
        context: Additional context about where error occurred
        extra: Additional data to include in log
        logger: Logger instance (defaults to module logger)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    log_data = {
        'error_type': error_type,
        'exception_type': type(error).__name__,
        'exception_message': str(error),
        'timestamp': time.time()
    }

    if context:
        log_data['context'] = context

    if extra:
        log_data.update(extra)

    logger.error(f"Error occurred: {error}", exc_info=True, extra=log_data)


def log_retry_attempt(
    operation: str,
    attempt: int,
    max_attempts: int,
    error_type: str,
    delay: float,
    logger: Optional[logging.Logger] = None
):
    """
    Log a retry attempt.

    Args:
        operation: Name of the operation being retried
        attempt: Current attempt number (0-indexed)
        max_attempts: Maximum retry attempts
        error_type: The classified error type
        delay: Delay before next attempt
        logger: Logger instance
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.warning(
        f"Retry {attempt + 1}/{max_attempts} for {operation} "
        f"(error_type={error_type}, delay={delay:.2f}s)"
    )


# =============================================================================
# CONTEXT MANAGERS
# =============================================================================

from contextlib import contextmanager


@contextmanager
def error_handler(
    operation_name: str,
    logger: Optional[logging.Logger] = None,
    capture_exceptions: Optional[List[type]] = None
):
    """
    Context manager for consistent error handling.

    Args:
        operation_name: Name of the operation for logging
        logger: Logger instance
        capture_exceptions: List of exception types to capture

    Yields:
        None if successful, raises exception on error

    Example:
        try:
            with error_handler("database_query"):
                result = do_query()
        except Exception as e:
            handle_error(e)
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if capture_exceptions is None:
        capture_exceptions = [Exception]

    try:
        yield
    except Exception as e:
        error_type = classify_error(e)

        # Only log if it's one of the captured types
        if any(isinstance(e, exc_type) for exc_type in capture_exceptions):
            log_error(e, error_type, context=operation_name, logger=logger)
        else:
            raise


@contextmanager
def circuit_breaker_handler(
    circuit: CircuitBreaker,
    fallback=None,
    logger: Optional[logging.Logger] = None
):
    """
    Context manager for circuit breaker pattern.

    Args:
        circuit: Circuit breaker instance
        fallback: Function to call if circuit is open
        logger: Logger instance

    Yields:
        None

    Example:
        with circuit_breaker_handler(circuit, fallback=get_cached):
            result = external_api_call()
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        yield
    except CircuitOpenError:
        if fallback:
            logger.warning("Circuit open, using fallback")
            try:
                fallback()
            except Exception as e:
                logger.error(f"Fallback failed: {e}", exc_info=True)
                raise
        else:
            raise
