"""
JobCopilot - Distributed Circuit Breaker Pattern
Protects system stability against cascading failures and outbound latency spikes.
Fails fast when external dependencies (ATS boards, LLMs, Stripe, Email) suffer outages.
"""

import time
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger("jobcopilot.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation: requests pass through
    OPEN = "OPEN"          # Outage detected: requests fail fast without calling remote service
    HALF_OPEN = "HALF_OPEN"  # Testing recovery: limited trial requests allowed


class CircuitOpenError(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, breaker_name: str, recovery_seconds_remaining: float):
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN. Fast-failing external call. Recovery in {recovery_seconds_remaining:.1f}s.")
        self.breaker_name = breaker_name
        self.recovery_seconds_remaining = recovery_seconds_remaining


class CircuitBreaker:
    """
    State machine managing outbound call resilience with automatic recovery probes.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_success_threshold: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        # Check if recovery timeout has elapsed while OPEN
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_state_change
            if elapsed >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState):
        prev = self._state
        self._state = new_state
        self._last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            logger.info(f"Circuit '{self.name}' transitioned from {prev} to CLOSED (fully healthy).")
        elif new_state == CircuitState.OPEN:
            self._success_count = 0
            logger.warning(f"Circuit '{self.name}' tripped from {prev} to OPEN (failing fast for {self.recovery_timeout}s).")
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            logger.info(f"Circuit '{self.name}' transitioned to HALF_OPEN (probing recovery).")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executes the callable within circuit breaker protection."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            elapsed = time.time() - self._last_state_change
            remaining = max(0.0, self.recovery_timeout - elapsed)
            raise CircuitOpenError(self.name, remaining)

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success path
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

            return result

        except Exception as exc:
            # Re-raise if it's already a CircuitOpenError
            if isinstance(exc, CircuitOpenError):
                raise

            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(f"Circuit '{self.name}' failure count: {self._failure_count}/{self.failure_threshold} - Error: {exc}")

            if self._state == CircuitState.HALF_OPEN:
                # Any failure during half-open trips back to OPEN immediately
                self._transition_to(CircuitState.OPEN)
            elif self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

            raise exc

    def __call__(self, func: Callable):
        """Decorator for protecting async functions with the circuit breaker."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper

    def reset(self):
        """Manually resets the circuit breaker to CLOSED."""
        self._transition_to(CircuitState.CLOSED)

    def trip(self):
        """Manually trips the circuit breaker to OPEN (useful for testing or emergency cutoff)."""
        self._transition_to(CircuitState.OPEN)

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry for monitoring and health probes."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
            "last_state_change": self._last_state_change
        }


# =========================================================================
# Predefined Enterprise Circuit Breakers
# =========================================================================
ats_api_breaker = CircuitBreaker("ats_api", failure_threshold=5, recovery_timeout=30.0)
llm_api_breaker = CircuitBreaker("llm_api", failure_threshold=3, recovery_timeout=20.0)
stripe_api_breaker = CircuitBreaker("stripe_api", failure_threshold=4, recovery_timeout=30.0)
email_api_breaker = CircuitBreaker("email_api", failure_threshold=5, recovery_timeout=30.0)

_ALL_BREAKERS = [ats_api_breaker, llm_api_breaker, stripe_api_breaker, email_api_breaker]


def get_all_circuit_statuses() -> Dict[str, Dict[str, Any]]:
    """Gathers status telemetry for all active circuit breakers."""
    return {b.name: b.get_status() for b in _ALL_BREAKERS}
