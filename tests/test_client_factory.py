"""Tests for the client factory module."""

import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from squeeze.client_factory import create_client
from squeeze.exceptions import ConnectionError
from squeeze.html_client import SqueezeHtmlClient
from squeeze.json_client import SqueezeJsonClient


class TestCreateClient:
    """Tests for the create_client function."""

    @pytest.fixture
    def server_url(self) -> str:
        """Fixture for test server URL."""
        return "http://example.com:9000"

    def test_prefer_json_true_success(self, server_url: str) -> None:
        """Test creating a JSON client when prefer_json is True and JSON API is available."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            client = create_client(server_url, prefer_json=True)
            assert isinstance(client, SqueezeJsonClient)
            assert client.server_url == server_url
            mock_urlopen.assert_called_once()

    def test_prefer_json_true_http_error(self, server_url: str) -> None:
        """Test creating a client when prefer_json is True and JSON API returns HTTP error."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            # Create an HTTP error with the proper header type that urllib actually uses
            from http.client import HTTPMessage

            headers = HTTPMessage()
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url=f"{server_url}/jsonrpc.js",
                code=404,
                msg="Not Found",
                hdrs=headers,
                fp=None,
            )
            with pytest.raises(ConnectionError) as excinfo:
                create_client(server_url, prefer_json=True)
            assert "JSON API not available" in str(excinfo.value)
            assert "HTTP error 404" in str(excinfo.value)

    def test_prefer_json_true_url_error(self, server_url: str) -> None:
        """Test creating a client when prefer_json is True and JSON API connection fails."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with pytest.raises(ConnectionError) as excinfo:
                create_client(server_url, prefer_json=True)
            assert "Failed to connect to JSON API" in str(excinfo.value)
            assert "Connection refused" in str(excinfo.value)

    def test_prefer_json_true_generic_error(self, server_url: str) -> None:
        """Test creating a client when prefer_json is True and a generic error occurs."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Something went wrong")
            with pytest.raises(ConnectionError) as excinfo:
                create_client(server_url, prefer_json=True)
            assert "Failed to connect to JSON API" in str(excinfo.value)
            assert "Something went wrong" in str(excinfo.value)

    def test_prefer_json_false(self, server_url: str) -> None:
        """Test creating an HTML client when prefer_json is False."""
        client = create_client(server_url, prefer_json=False)
        assert isinstance(client, SqueezeHtmlClient)
        assert client.server_url == server_url

    def test_auto_detect_json_success(self, server_url: str) -> None:
        """Test auto-detecting JSON API when it's available."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            client = create_client(server_url)  # No preference specified
            assert isinstance(client, SqueezeJsonClient)
            assert client.server_url == server_url
            mock_urlopen.assert_called_once()

    def test_auto_detect_fallback_to_html(self, server_url: str) -> None:
        """Test falling back to HTML client when JSON API detection fails."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            # Create an HTTP error with the proper header type that urllib actually uses
            from http.client import HTTPMessage

            headers = HTTPMessage()
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url=f"{server_url}/jsonrpc.js",
                code=404,
                msg="Not Found",
                hdrs=headers,
                fp=None,
            )
            client = create_client(server_url)  # No preference specified
            assert isinstance(client, SqueezeHtmlClient)
            assert client.server_url == server_url
            mock_urlopen.assert_called_once()

    def test_url_trailing_slash_handling(self) -> None:
        """Test handling of URLs with and without trailing slashes."""
        with patch("urllib.request.urlopen"):
            # URL with trailing slash
            client1 = create_client("http://example.com:9000/", prefer_json=True)
            # URL without trailing slash
            client2 = create_client("http://example.com:9000", prefer_json=True)

            # Both should result in the same server_url without trailing slash
            assert client1.server_url == "http://example.com:9000"
            assert client2.server_url == "http://example.com:9000"
