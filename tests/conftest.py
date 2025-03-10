"""Pytest configuration and shared fixtures for squeeze tests."""

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from pytest import fixture

from squeeze.json_client import SqueezeJsonClient

# No custom protocol needed with proper typing

# Sample player data for testing
SAMPLE_PLAYERS = [
    {"id": "00:11:22:33:44:55", "name": "Living Room Player"},
    {"id": "aa:bb:cc:dd:ee:ff", "name": "Kitchen Player"},
]

# Sample status data for testing
SAMPLE_STATUS = {
    "player_id": "00:11:22:33:44:55",
    "player_name": "Living Room Player",
    "power": 1,
    "status": "playing",
    "mode": "play",
    "volume": 50,
    "shuffle": 0,
    "shuffle_mode": "off",
    "repeat": 0,
    "repeat_mode": "off",
    "playlist_count": 10,
    "playlist_position": 2,
    "current_track": {
        "title": "Test Track",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 240,
        "position": 45,
    },
}

# Sample JSON API response for player status
SAMPLE_JSON_STATUS_RESPONSE = {
    "result": {
        "player_name": "Living Room Player",
        "power": 1,
        "mode": "play",
        "volume": 50,
        "playlist_shuffle": 0,
        "playlist_repeat": 0,
        "playlist_tracks": 10,
        "playlist_cur_index": 2,
        "time": 45,
        "playlist_loop": [
            {
                "title": "Test Track",
                "artist": "Test Artist",
                "album": "Test Album",
                "duration": 240,
            }
        ],
    }
}


@fixture
def server_url() -> str:
    """Fixture for test server URL."""
    return "http://example.com:9000"


@fixture
def player_id() -> str:
    """Fixture for test player ID."""
    return SAMPLE_PLAYERS[0]["id"]


# HTML client fixture removed in v0.3.0


@fixture
def mock_json_client() -> Generator[MagicMock, None, None]:
    """Fixture for a mocked SqueezeJsonClient."""
    with patch("squeeze.json_client.SqueezeJsonClient") as mock_client:
        # Configure the mock
        instance = mock_client.return_value
        instance.get_players.return_value = SAMPLE_PLAYERS
        instance.get_player_status.return_value = SAMPLE_STATUS

        # Configure the mock to simulate sending commands
        instance._send_request.return_value = {"result": {}}
        instance.send_command.return_value = None

        # Return the configured mock
        yield instance


@fixture
def mock_urlopen() -> Generator[MagicMock, None, None]:
    """Fixture for mocking urllib.request.urlopen."""
    with patch("urllib.request.urlopen") as mock:
        response_mock = MagicMock()
        # Default HTML response
        response_mock.read.return_value = (
            b'<html><select name="player">'
            b'<option value="00:11:22:33:44:55">Living Room Player</option>'
            b'<option value="aa:bb:cc:dd:ee:ff">Kitchen Player</option>'
            b"</select></html>"
        )
        mock.return_value.__enter__.return_value = response_mock
        yield mock


# HTML client fixture removed in v0.3.0


@fixture
def json_client(server_url: str) -> SqueezeJsonClient:
    """Fixture for creating a real SqueezeJsonClient instance."""
    return SqueezeJsonClient(server_url)


# Mock request and response handling for JSON client
class MockResponse:
    """Mock urllib response for testing."""

    def __init__(self, content: bytes, status: int = 200):
        """Initialize with content and status."""
        self.content = content
        self.status = status

    def read(self) -> bytes:
        """Return the response content."""
        return self.content


@fixture
def json_mock_urlopen() -> Generator[MagicMock, None, None]:
    """Fixture for mocking urlopen to return JSON responses."""
    with patch("urllib.request.urlopen") as mock:

        def side_effect(request: Any) -> Any:
            """Return appropriate mock response based on request."""
            request_json = json.loads(request.data)
            mock_response = MockResponse(b"{}")

            # Determine the command from the request
            params = request_json.get("params", [[]])
            if len(params) > 1 and isinstance(params[1], list) and params[1]:
                command = params[1][0]

                # Return different responses based on command
                if command == "players":
                    mock_response = MockResponse(
                        json.dumps(
                            {
                                "result": {
                                    "players_loop": [
                                        {"playerid": p["id"], "name": p["name"]}
                                        for p in SAMPLE_PLAYERS
                                    ]
                                }
                            }
                        ).encode("utf-8")
                    )
                elif command == "status":
                    mock_response = MockResponse(
                        json.dumps(SAMPLE_JSON_STATUS_RESPONSE).encode("utf-8")
                    )

            response = MagicMock()
            response.__enter__.return_value = mock_response
            return response

        mock.side_effect = side_effect
        yield mock
