"""
Factory module for creating a SqueezeBox JSON client.
"""

import http.client
import time
import urllib.request

from squeeze.exceptions import ConnectionError
from squeeze.json_client import SqueezeJsonClient


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
    last_error: Exception | None = None

    # Check if server URL ends with port
    base_url = server_url.rstrip("/")

    # Try to verify server is running by checking the base URL first
    try:
        # Just check if the server responds at all
        req = urllib.request.Request(base_url, method="HEAD")
        urllib.request.urlopen(req, timeout=5)
        # If we get here, server is responding, so we can try the JSON endpoint
    except Exception as e:
        # If we can't connect to the base URL, server is probably down
        raise ConnectionError(f"Server is not responding: {str(e)}")

    # Try different API endpoints - some server versions use different paths
    endpoints = [
        "/jsonrpc.js",  # Standard endpoint
        "/rpc/json",  # Alternative endpoint sometimes used
        "/api",  # Another possible endpoint
    ]

    # Try all endpoints with retries
    for endpoint in endpoints:
        endpoint_attempted = False
        for attempt in range(max_retries):
            try:
                json_url = f"{base_url}{endpoint}"
                # Silently try each endpoint
                req = urllib.request.Request(
                    json_url, headers={"Accept": "application/json"}, method="HEAD"
                )
                # Increase timeout to 5 seconds for better reliability
                urllib.request.urlopen(req, timeout=5)

                # If we reach here, endpoint works!
                # Create client with the working endpoint path
                return SqueezeJsonClient(base_url, api_path=endpoint)

            except urllib.error.HTTPError as e:
                # Don't retry authentication errors
                endpoint_attempted = True
                # Pattern matching with better compatibility
                match e.code:
                    case 401 | 403:
                        raise ConnectionError(f"Authentication required: HTTP {e.code}")
                    case 404:
                        # This endpoint doesn't exist, try next one
                        last_error = e
                        break  # Break out of retry loop for this endpoint
                    case _:
                        last_error = e

            except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
                # These are network errors that might be transient, so we'll retry
                endpoint_attempted = True
                last_error = e

            except Exception as e:
                # Other unexpected errors, retry with caution
                endpoint_attempted = True
                last_error = e

            # Only sleep if we're going to retry this endpoint
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        # If we tried the endpoint and got something other than a 404, it might work with the client
        if endpoint_attempted and (
            not isinstance(last_error, urllib.error.HTTPError)
            or getattr(last_error, "code", 0) != 404
        ):
            # We might have a valid endpoint but connection issues
            # Try creating client anyway - it might work for POST requests even if HEAD fails
            return SqueezeJsonClient(base_url, api_path=endpoint)

    # If we've exhausted all endpoints and retries, raise the appropriate error
    if isinstance(last_error, urllib.error.HTTPError):
        if last_error.code == 404:
            raise ConnectionError(
                "No valid API endpoint found. Server may not be a SqueezeBox server or may not have JSON API enabled."
            )
        else:
            raise ConnectionError(f"API not available: HTTP error {last_error.code}")
    elif isinstance(last_error, urllib.error.URLError):
        reason = (
            str(last_error.reason) if hasattr(last_error, "reason") else str(last_error)
        )
        raise ConnectionError(f"Failed to connect to server: {reason}")
    elif isinstance(last_error, http.client.RemoteDisconnected):
        # Try one last approach - just create the client and let it try to POST even if HEAD fails
        return SqueezeJsonClient(base_url)
    elif last_error:
        raise ConnectionError(f"Failed to connect to server: {str(last_error)}")
    else:
        # This should never happen, but just in case
        raise ConnectionError("Failed to connect to server")
