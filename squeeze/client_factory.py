"""
Factory module for creating a SqueezeBox JSON client.
"""

import urllib.request

from squeeze.exceptions import ConnectionError
from squeeze.json_client import SqueezeJsonClient


def create_client(server_url: str) -> SqueezeJsonClient:
    """Create a SqueezeBox JSON client for the given server.

    Args:
        server_url: URL of the SqueezeBox server

    Returns:
        SqueezeJsonClient instance

    Raises:
        ConnectionError: If unable to connect to the server
    """
    try:
        json_url = f"{server_url.rstrip('/')}/jsonrpc.js"
        req = urllib.request.Request(
            json_url, headers={"Accept": "application/json"}, method="HEAD"
        )
        urllib.request.urlopen(req, timeout=2)
        return SqueezeJsonClient(server_url)
    except urllib.error.HTTPError as e:
        match e.code:
            case 401 | 403:
                raise ConnectionError(f"Authentication required: HTTP {e.code}")
            case 404:
                raise ConnectionError("API endpoint not found")
            case _:
                raise ConnectionError(f"API not available: HTTP error {e.code}")
    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        raise ConnectionError(f"Failed to connect to server: {reason}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to server: {str(e)}")
