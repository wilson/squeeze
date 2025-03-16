"""Tests for the retry module."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from squeeze.retry import retry_operation, with_retry


class TestWithRetry:
    """Tests for the with_retry decorator."""

    def test_successful_execution(self) -> None:
        """Test that the function is called once when it succeeds."""
        mock_func = Mock(return_value="success")
        decorated_func = with_retry()(mock_func)

        result = decorated_func()

        assert result == "success"
        mock_func.assert_called_once()

    def test_retry_on_temporary_failure(self) -> None:
        """Test that the function is retried on temporary failures."""
        mock_func = Mock(side_effect=[ValueError, ValueError, "success"])
        decorated_func = with_retry(
            max_tries=3, retry_delay=0.01, retry_exceptions=(ValueError,)
        )(mock_func)

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_no_retry_on_permanent_failure(self) -> None:
        """Test that the function is not retried on permanent failures."""
        mock_func = Mock(side_effect=RuntimeError("Permanent error"))
        decorated_func = with_retry(
            max_tries=3, retry_delay=0.01, retry_exceptions=(ValueError,)
        )(mock_func)

        with pytest.raises(RuntimeError, match="Permanent error"):
            decorated_func()

        mock_func.assert_called_once()

    def test_max_tries_exceeded(self) -> None:
        """Test that the function raises the last exception when max tries are exceeded."""
        mock_func = Mock(side_effect=[ValueError, ValueError, ValueError])
        decorated_func = with_retry(
            max_tries=3, retry_delay=0.01, retry_exceptions=(ValueError,)
        )(mock_func)

        with pytest.raises(ValueError):
            decorated_func()

        assert mock_func.call_count == 3

    def test_backoff_factor(self) -> None:
        """Test that retry delay increases with the backoff factor."""
        mock_func = Mock(side_effect=[ValueError, ValueError, "success"])

        with patch("time.sleep") as mock_time_sleep:
            decorated_func = with_retry(
                max_tries=3,
                retry_delay=1.0,
                backoff_factor=2.0,
                retry_exceptions=(ValueError,),
            )(mock_func)

            result = decorated_func()

            assert result == "success"
            assert mock_func.call_count == 3
            # First delay should be 1.0, second should be 2.0
            mock_time_sleep.assert_any_call(1.0)
            mock_time_sleep.assert_any_call(2.0)

    def test_no_retry_exceptions(self) -> None:
        """Test that specified exceptions are not retried."""
        mock_func = Mock(side_effect=ValueError("Do not retry"))
        decorated_func = with_retry(
            max_tries=3,
            retry_delay=0.01,
            retry_exceptions=(Exception,),
            no_retry_exceptions=(ValueError,),
        )(mock_func)

        with pytest.raises(ValueError, match="Do not retry"):
            decorated_func()

        mock_func.assert_called_once()


class TestRetryOperation:
    """Tests for the retry_operation function."""

    def test_successful_operation(self) -> None:
        """Test that the operation is executed once when it succeeds."""
        mock = Mock(return_value="success")

        def test_func() -> Any:
            return mock()

        result = retry_operation(test_func, max_tries=3, retry_delay=0.01)

        assert result == "success"
        mock.assert_called_once()

    def test_retry_on_failure(self) -> None:
        """Test that the operation is retried on failures."""
        mock = Mock(side_effect=[ValueError, ValueError, "success"])

        def test_func() -> Any:
            return mock()

        result = retry_operation(
            test_func, max_tries=3, retry_delay=0.01, retry_exceptions=(ValueError,)
        )

        assert result == "success"
        assert mock.call_count == 3

    def test_max_tries_exceeded(self) -> None:
        """Test that the function raises the last exception when max tries are exceeded."""
        mock = Mock(side_effect=ValueError)

        def test_func() -> Any:
            return mock()

        with pytest.raises(ValueError):
            retry_operation(
                test_func, max_tries=3, retry_delay=0.01, retry_exceptions=(ValueError,)
            )

        assert mock.call_count == 3

    def test_no_retry_exceptions(self) -> None:
        """Test that specified exceptions are not retried."""
        mock = Mock(side_effect=ValueError("Do not retry"))

        def test_func() -> Any:
            return mock()

        with pytest.raises(ValueError, match="Do not retry"):
            retry_operation(
                test_func,
                max_tries=3,
                retry_delay=0.01,
                retry_exceptions=(Exception,),
                no_retry_exceptions=(ValueError,),
            )

        mock.assert_called_once()

    def test_backoff_factor(self) -> None:
        """Test that retry delay increases with the backoff factor."""
        mock = Mock(side_effect=[ValueError, ValueError, "success"])

        def test_func() -> Any:
            return mock()

        with patch("time.sleep") as mock_time_sleep:
            result = retry_operation(
                test_func,
                max_tries=3,
                retry_delay=1.0,
                backoff_factor=2.0,
                retry_exceptions=(ValueError,),
            )

            assert result == "success"
            assert mock.call_count == 3
            # First delay should be 1.0, second should be 2.0
            mock_time_sleep.assert_any_call(1.0)
            mock_time_sleep.assert_any_call(2.0)

    def test_fallback_function(self) -> None:
        """Test that the fallback function is used after first failure."""
        mock_main = Mock(side_effect=ValueError("Main function failed"))
        mock_fallback = Mock(return_value="fallback result")

        def main_func() -> Any:
            return mock_main()

        def fallback_func() -> Any:
            return mock_fallback()

        result = retry_operation(
            main_func,
            max_tries=3,
            retry_delay=0.01,
            fallback_func=fallback_func,
            retry_exceptions=(ValueError,),
        )

        assert result == "fallback result"
        mock_main.assert_called_once()
        mock_fallback.assert_called_once()
