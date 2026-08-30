"""
SignalAtlas Retry Utilities

Exponential backoff with jitter for retryable operations.
"""

import asyncio
import random
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from structlog import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: Optional[tuple] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    def should_retry(self, attempt: int, exception: Optional[Exception]) -> bool:
        """Determine if operation should be retried."""
        if attempt >= self.max_attempts:
            return False
        if exception is None:
            return False
        return isinstance(exception, self.retryable_exceptions)

    def get_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate delay before next retry."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)

        # Exponential backoff: base_delay * 2^attempt
        delay = self.base_delay * (2 ** attempt)

        # Add jitter (random value between 0 and base_delay)
        if self.jitter:
            delay += random.uniform(0, self.base_delay)

        return min(delay, self.max_delay)


# Default retry configurations
DEFAULT_RETRY = RetryConfig()
HTTP_RETRY = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    jitter=True,
)
RATE_LIMIT_RETRY = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=300.0,  # 5 minutes max
    jitter=True,
)


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration (uses DEFAULT_RETRY if not provided)
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Exception: Last exception if all retries fail
    """
    config = config or DEFAULT_RETRY
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                "Retryable error",
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                error=str(e),
                function=func.__name__,
            )

            if not config.should_retry(attempt, e):
                raise

            delay = config.get_delay(attempt)
            logger.info(
                "Retrying after delay",
                attempt=attempt + 1,
                delay=f"{delay:.2f}s",
                function=func.__name__,
            )
            await asyncio.sleep(delay)

    raise last_exception


def retry_sync(
    func: Callable[..., T],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Retry a sync function with exponential backoff.

    Args:
        func: Sync function to retry
        *args: Positional arguments for func
        config: Retry configuration (uses DEFAULT_RETRY if not provided)
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Exception: Last exception if all retries fail
    """
    import time
    config = config or DEFAULT_RETRY
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                "Retryable error",
                attempt=attempt + 1,
                max_attempts=config.max_attempts,
                error=str(e),
                function=func.__name__,
            )

            if not config.should_retry(attempt, e):
                raise

            delay = config.get_delay(attempt)
            logger.info(
                "Retrying after delay",
                attempt=attempt + 1,
                delay=f"{delay:.2f}s",
                function=func.__name__,
            )
            time.sleep(delay)

    raise last_exception


def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[tuple] = None,
) -> Callable:
    """
    Decorator to add retry logic to async functions.

    Args:
        config: Retry configuration
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function
    """
    if config is None:
        config = DEFAULT_RETRY
    if retryable_exceptions:
        config = RetryConfig(
            max_attempts=config.max_attempts,
            base_delay=config.base_delay,
            max_delay=config.max_delay,
            jitter=config.jitter,
            retryable_exceptions=retryable_exceptions,
        )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(func, *args, config=config, **kwargs)
        return wrapper
    return decorator
