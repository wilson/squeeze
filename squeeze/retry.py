"""
Unified retry logic for handling transient failures.

This module provides common retry mechanisms for API calls, network operations,
and other functions that might experience transient failures.
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

# For proper return type annotation with generics
T = TypeVar("T")
RetryableFunc = Callable[..., T]


def retry_operation(
    func: Callable[..., T],
    *args: Any,
    max_tries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 1.0,
    fallback_func: Callable[..., T] | None = None,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    no_retry_exceptions: tuple[type[Exception], ...] = (),
) -> T:
    """Execute a function with retry logic and optional fallback.

    Args:
        func: Function to call
        *args: Arguments to pass to the function
        max_tries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for increasing delay between retries
        fallback_func: Optional fallback function to try after first failure
        retry_exceptions: Tuple of exception types to retry on
        no_retry_exceptions: Tuple of exception types to not retry on (takes precedence)

    Returns:
        Result of the function call if successful

    Raises:
        Exception: The last exception encountered if all attempts fail
    """
    last_error: Exception | None = None

    for attempt in range(max_tries):
        try:
            result = func(*args)
            return result  # Success, return the result
        except Exception as e:
            # Check if this is an exception we should not retry
            if isinstance(e, no_retry_exceptions):
                raise

            # Check if this is an exception we should retry
            if not isinstance(e, retry_exceptions):
                raise

            last_error = e

            if attempt < max_tries - 1:
                # Wait before retry, with configurable backoff
                delay = retry_delay * (backoff_factor**attempt)
                time.sleep(delay)

                # Try fallback on first failure if provided
                if attempt == 0 and fallback_func is not None:
                    try:
                        result = fallback_func(*args)
                        return result  # Fallback succeeded
                    except Exception:
                        # Fallback failed, continue with normal retries
                        pass

    # If we get here, all attempts failed
    if last_error:
        raise last_error

    # Shouldn't reach here, but just in case
    raise Exception("All retry attempts failed without a specific error")


def with_retry(
    max_tries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 1.0,
    fallback_func: Callable[..., Any] | None = None,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    no_retry_exceptions: tuple[type[Exception], ...] = (),
) -> Callable[[RetryableFunc[T]], RetryableFunc[T]]:
    """Decorator for adding retry logic to functions.

    Args:
        max_tries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for increasing delay between retries
        fallback_func: Optional fallback function to try after first failure
        retry_exceptions: Tuple of exception types to retry on
        no_retry_exceptions: Tuple of exception types to not retry on (takes precedence)

    Returns:
        Decorator function that adds retry logic
    """

    def decorator(func: RetryableFunc[T]) -> RetryableFunc[T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Define the function to retry
            def execute_func() -> T:
                return func(*args, **kwargs)

            # Call retry_operation with the wrapped function
            result: T = retry_operation(
                execute_func,
                max_tries=max_tries,
                retry_delay=retry_delay,
                backoff_factor=backoff_factor,
                fallback_func=fallback_func,
                retry_exceptions=retry_exceptions,
                no_retry_exceptions=no_retry_exceptions,
            )
            return result

        return cast(RetryableFunc[T], wrapper)

    return decorator
