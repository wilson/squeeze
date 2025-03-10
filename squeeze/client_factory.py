"""
Factory module for creating appropriate SqueezeBox clients.
"""

import urllib.request
from typing import Optional, Union

from squeeze.html_client import SqueezeHtmlClient
from squeeze.exceptions import ConnectionError
from squeeze.json_client import SqueezeJsonClient


def create_client(
    server_url: str, prefer_json: Optional[bool] = None
) -> Union[SqueezeHtmlClient, SqueezeJsonClient]:
    """Create an appropriate SqueezeBox client for the given server.

    Args:
        server_url: URL of the SqueezeBox server
        prefer_json: Whether to prefer JSON API if available (None = auto-detect)

    Returns:
        Either SqueezeHtmlClient or SqueezeJsonClient instance

    Raises:
        ConnectionError: If unable to connect to the server when explicit JSON is requested
    """
    # If preference is explicit, honor it
    if prefer_json is not None:
        if prefer_json:
            # When explicitly asking for JSON client, any connection failure
            # should be reported as an error
            try:
                # Try to access the JSON API endpoint to verify it works
                json_url = f"{server_url.rstrip('/')}/jsonrpc.js"
                req = urllib.request.Request(
                    json_url, headers={"Accept": "application/json"}, method="HEAD"
                )
                urllib.request.urlopen(req, timeout=2)
                return SqueezeJsonClient(server_url)
            except urllib.error.HTTPError as e:
                raise ConnectionError(f"JSON API not available: HTTP error {e.code}")
            except urllib.error.URLError as e:
                reason = str(e.reason) if hasattr(e, "reason") else str(e)
                raise ConnectionError(f"Failed to connect to JSON API: {reason}")
            except Exception as e:
                raise ConnectionError(f"Failed to connect to JSON API: {str(e)}")
        else:
            return SqueezeHtmlClient(server_url)

    # Otherwise, try to auto-detect JSON API support
    json_url = f"{server_url.rstrip('/')}/jsonrpc.js"
    try:
        # Try to access the JSON API endpoint
        req = urllib.request.Request(
            json_url, headers={"Accept": "application/json"}, method="HEAD"
        )
        urllib.request.urlopen(req, timeout=2)

        # If we reach here, JSON API is likely supported
        return SqueezeJsonClient(server_url)
    except Exception:
        # Fall back to HTML-based client, don't raise an error
        # since we're detecting capabilities
        return SqueezeHtmlClient(server_url)
