"""Tests for the SqueezeHtmlClient class."""

import unittest
from unittest.mock import Mock, patch

from squeeze.html_client import SqueezeHtmlClient


class TestSqueezeHtmlClient(unittest.TestCase):
    """Test cases for the SqueezeHtmlClient class."""

    def test_init(self) -> None:
        """Test initialization of SqueezeHtmlClient."""
        client = SqueezeHtmlClient("http://example.com:9000")
        self.assertEqual(client.server_url, "http://example.com:9000")

        # Test with trailing slash
        client = SqueezeHtmlClient("http://example.com:9000/")
        self.assertEqual(client.server_url, "http://example.com:9000")

    @patch("urllib.request.urlopen")
    def test_get_html(self, mock_urlopen: Mock) -> None:
        """Test get_html method."""
        # Mock the response
        mock_response = Mock()
        mock_response.read.return_value = b"<html><body><div>Test</div></body></html>"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = SqueezeHtmlClient("http://example.com:9000")
        result = client.get_html("status.html")

        self.assertEqual(result, b"<html><body><div>Test</div></body></html>")

        # Test with player ID
        client.get_html("status.html", "00:11:22:33:44:55")
        mock_urlopen.assert_called_with(
            "http://example.com:9000/status.html?player=00:11:22:33:44:55"
        )

    @patch("squeeze.html_client.SqueezeHtmlClient.get_html")
    def test_get_players(self, mock_get_html: Mock) -> None:
        """Test get_players method."""
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

        client = SqueezeHtmlClient("http://example.com:9000")
        result = client.get_players()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "00:11:22:33:44:55")
        self.assertEqual(result[0]["name"], "Player One")
        self.assertEqual(result[1]["id"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(result[1]["name"], "Player Two")

    @patch("urllib.request.urlopen")
    def test_send_command(self, mock_urlopen: Mock) -> None:
        """Test send_command method."""
        client = SqueezeHtmlClient("http://example.com:9000")

        # Test without params
        client.send_command("00:11:22:33:44:55", "play")
        mock_urlopen.assert_called_with(
            "http://example.com:9000/status.html?player=00:11:22:33:44:55&p0=play"
        )

        # Test with params
        client.send_command("00:11:22:33:44:55", "mixer", ["volume", "50"])
        mock_urlopen.assert_called_with(
            "http://example.com:9000/status.html?player=00:11:22:33:44:55&p0=mixer&p1=volume&p2=50"
        )


if __name__ == "__main__":
    unittest.main()
