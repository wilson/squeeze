"""Tests for the SqueezeHtmlClient class using pytest."""

from unittest.mock import MagicMock, patch

from squeeze.html_client import SqueezeHtmlClient


def test_init() -> None:
    """Test initialization of SqueezeHtmlClient."""
    client = SqueezeHtmlClient("http://example.com:9000")
    assert client.server_url == "http://example.com:9000"

    # Test with trailing slash
    client = SqueezeHtmlClient("http://example.com:9000/")
    assert client.server_url == "http://example.com:9000"


def test_get_html(mock_urlopen: MagicMock) -> None:
    """Test get_html method."""
    # Set the mock response
    mock_response = mock_urlopen.return_value.__enter__.return_value
    mock_response.read.return_value = b"<html><body><div>Test</div></body></html>"

    client = SqueezeHtmlClient("http://example.com:9000")
    result = client.get_html("status.html")

    assert result == b"<html><body><div>Test</div></body></html>"

    # Test with player ID
    client.get_html("status.html", "00:11:22:33:44:55")
    mock_urlopen.assert_called_with(
        "http://example.com:9000/status.html?player=00:11:22:33:44:55"
    )


def test_get_players(html_client: SqueezeHtmlClient) -> None:
    """Test get_players method."""
    # Patch the get_html method
    with patch.object(html_client, "get_html") as mock_get_html:
        # Create a mock HTML response
        html_str = b"""
        <html>
          <select name="player">
            <option value="00:11:22:33:44:55">Player One</option>
            <option value="aa:bb:cc:dd:ee:ff">Player Two</option>
          </select>
        </html>
        """
        mock_get_html.return_value = html_str

        result = html_client.get_players()

        assert len(result) == 2
        assert result[0]["id"] == "00:11:22:33:44:55"
        assert result[0]["name"] == "Player One"
        assert result[1]["id"] == "aa:bb:cc:dd:ee:ff"
        assert result[1]["name"] == "Player Two"


def test_send_command(mock_urlopen: MagicMock) -> None:
    """Test send_command method."""
    client = SqueezeHtmlClient("http://example.com:9000")

    # Test without params
    client.send_command("00:11:22:33:44:55", "play")
    # The URL is URL-encoded, so : becomes %3A
    mock_urlopen.assert_called_with(
        "http://example.com:9000/status.html?player=00%3A11%3A22%3A33%3A44%3A55&p0=play"
    )

    # Test with params
    client.send_command("00:11:22:33:44:55", "mixer", ["volume", "50"])
    mock_urlopen.assert_called_with(
        "http://example.com:9000/status.html?player=00%3A11%3A22%3A33%3A44%3A55&p0=mixer&p1=volume&p2=50"
    )
