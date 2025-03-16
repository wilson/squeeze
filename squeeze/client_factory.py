"""
Factory module for creating a SqueezeBox JSON client.
"""

import http.client
import urllib.request

from squeeze.exceptions import ConnectionError
from squeeze.json_client import SqueezeJsonClient
from squeeze.retry import retry_operation


def create_client(
    server_url: str, max_retries: int = 3, retry_delay: float = 1.0
) -> SqueezeJsonClient:
    """Create a SqueezeBox JSON client for the given server.

    Args:
        server_url: URL of the SqueezeBox server
        max_retries: Maximum number of connection attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 1.0)

    Returns:
        SqueezeJsonClient instance

    Raises:
        ConnectionError: If unable to connect to the server after all retries
    """
    # Check if server URL ends with port
    base_url = server_url.rstrip("/")

    # Try to verify server is running by checking the base URL first
    try:
        # Define a function to check base URL
        def check_base_url() -> bool:
            req = urllib.request.Request(base_url, method="HEAD")
            urllib.request.urlopen(req, timeout=5)
            return True

        # Attempt with single try since this is just a sanity check
        check_base_url()
    except Exception as e:
        # If we can't connect to the base URL, server is probably down
        raise ConnectionError(f"Server is not responding: {str(e)}")

    # Try different API endpoints - some server versions use different paths
    endpoints = [
        "/jsonrpc.js",  # Standard endpoint
        "/rpc/json",  # Alternative endpoint sometimes used
        "/api",  # Another possible endpoint
    ]

    last_error: Exception | None = None

    # Try each endpoint
    for endpoint in endpoints:
        # Define a function to try this endpoint with endpoint captured in closure
        def try_endpoint(current_endpoint: str = endpoint) -> bool:
            nonlocal last_error

            try:
                json_url = f"{base_url}{current_endpoint}"
                req = urllib.request.Request(
                    json_url, headers={"Accept": "application/json"}, method="HEAD"
                )
                urllib.request.urlopen(req, timeout=5)
                return True  # Success

            except urllib.error.HTTPError as e:
                # Don't retry authentication errors
                match e.code:
                    case 401 | 403:
                        raise ConnectionError(f"Authentication required: HTTP {e.code}")
                    case 404:
                        # This endpoint doesn't exist, try next one
                        last_error = e
                        return False  # Clear failure, don't retry
                    case _:
                        last_error = e
                        raise  # Will be caught and retried

            except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
                # These are network errors that might be transient
                last_error = e
                raise  # Will be caught and retried

        # Try this endpoint with retries
        try:
            result = retry_operation(
                try_endpoint,
                max_tries=max_retries,
                retry_delay=retry_delay,
                backoff_factor=1.5,
                retry_exceptions=(
                    urllib.error.URLError,
                    http.client.RemoteDisconnected,
                    Exception,
                ),
                no_retry_exceptions=(ConnectionError,),
            )

            # If we succeeded, create client with the working endpoint
            if result:
                return SqueezeJsonClient(base_url, api_path=endpoint)

        except Exception:
            # Endpoint failed after retries, try the next one
            pass

        # If we got something other than a 404 for this endpoint, it might work with POST
        if last_error and (
            not isinstance(last_error, urllib.error.HTTPError)
            or getattr(last_error, "code", 0) != 404
        ):
            # Try creating client anyway - POST might work even if HEAD fails
            return SqueezeJsonClient(base_url, api_path=endpoint)

    # If we've exhausted all endpoints, raise the appropriate error
    if isinstance(last_error, urllib.error.HTTPError):
        if last_error.code == 404:
            raise ConnectionError(
                "No valid API endpoint found. Server may not be a SqueezeBox server or may not have JSON API enabled."
            )
        else:
            raise ConnectionError(f"API not available: HTTP error {last_error.code}")
    elif isinstance(last_error, urllib.error.URLError):
        reason = getattr(last_error, "reason", str(last_error))
        raise ConnectionError(f"Failed to connect to server: {reason}")
    elif isinstance(last_error, http.client.RemoteDisconnected):
        # Try one last approach with default endpoint
        return SqueezeJsonClient(base_url)
    elif last_error:
        raise ConnectionError(f"Failed to connect to server: {str(last_error)}")
    else:
        raise ConnectionError("Failed to connect to server")
