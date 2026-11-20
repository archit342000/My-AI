"""
Error Handling Module

Provides resilience patterns like circuit breakers for external API calls.
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, Callable

USER_STREAM_ERROR = "Something went wrong while answering. Try sending again."  # sent to the person when a turn fails; the detail goes to the log


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
        """
        with self._lock:
            if self.state == 'open':
                if self._should_attempt_recovery():
                    self.state = 'half-open'
                else:
                    raise CircuitOpenError("Circuit is open")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception:
            self.on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs):
        """
        Execute asynchronous function through circuit breaker.
        """
        with self._lock:
            if self.state == 'open':
                if self._should_attempt_recovery():
                    self.state = 'half-open'
                else:
                    raise CircuitOpenError("Circuit is open")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception:
            self.on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) > self.recovery_timeout

    def on_success(self):
        """Called when the protected function succeeds."""
        with self._lock:
            self.failure_count = 0
            self.state = 'closed'

    def on_failure(self):
        """Called when the protected function fails."""
        with self._lock:
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
