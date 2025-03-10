"""Tests for the custom exceptions."""

from squeeze.exceptions import (
    APIError,
    CommandError,
    ConfigError,
    ConnectionError,
    ParseError,
    PlayerNotFoundError,
    SqueezeError,
)


class TestExceptions:
    """Tests for the exception classes."""

    def test_squeeze_error_basic(self) -> None:
        """Test SqueezeError with a simple message."""
        error = SqueezeError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.code == 0

    def test_squeeze_error_with_code(self) -> None:
        """Test SqueezeError with a custom code."""
        error = SqueezeError("Test error", code=42)
        assert str(error) == "Error 42: Test error"
        assert error.message == "Test error"
        assert error.code == 42

    def test_connection_error(self) -> None:
        """Test ConnectionError."""
        error = ConnectionError("Could not connect")
        assert str(error) == "Error 1: Could not connect"
        assert error.message == "Could not connect"
        assert error.code == 1

        # With custom code
        error = ConnectionError("Could not connect", code=101)
        assert str(error) == "Error 101: Could not connect"
        assert error.message == "Could not connect"
        assert error.code == 101

    def test_api_error(self) -> None:
        """Test APIError."""
        error = APIError("API request failed")
        assert str(error) == "Error 2: API request failed"
        assert error.message == "API request failed"
        assert error.code == 2

        # With custom code
        error = APIError("API request failed", code=102)
        assert str(error) == "Error 102: API request failed"
        assert error.message == "API request failed"
        assert error.code == 102

    def test_command_error_without_command(self) -> None:
        """Test CommandError without specifying a command."""
        error = CommandError("Command failed")
        assert str(error) == "Error 3: Command failed"
        assert error.message == "Command failed"
        assert error.code == 3
        assert error.command == ""

    def test_command_error_with_command(self) -> None:
        """Test CommandError with a specified command."""
        error = CommandError("Failed to execute", command="play")
        assert str(error) == "Error 3: Command 'play' failed: Failed to execute"
        assert error.message == "Command 'play' failed: Failed to execute"
        assert error.code == 3
        assert error.command == "play"

        # With custom code
        error = CommandError("Failed to execute", command="play", code=103)
        assert str(error) == "Error 103: Command 'play' failed: Failed to execute"
        assert error.message == "Command 'play' failed: Failed to execute"
        assert error.code == 103
        assert error.command == "play"

    def test_player_not_found_error_without_id(self) -> None:
        """Test PlayerNotFoundError without specifying a player ID."""
        error = PlayerNotFoundError()
        assert str(error) == "Error 4: Player not found"
        assert error.message == "Player not found"
        assert error.code == 4

    def test_player_not_found_error_with_id(self) -> None:
        """Test PlayerNotFoundError with a specified player ID."""
        error = PlayerNotFoundError("00:11:22:33:44:55")
        assert str(error) == "Error 4: Player not found: 00:11:22:33:44:55"
        assert error.message == "Player not found: 00:11:22:33:44:55"
        assert error.code == 4

        # With custom code
        error = PlayerNotFoundError("00:11:22:33:44:55", code=104)
        assert str(error) == "Error 104: Player not found: 00:11:22:33:44:55"
        assert error.message == "Player not found: 00:11:22:33:44:55"
        assert error.code == 104

    def test_parse_error(self) -> None:
        """Test ParseError."""
        error = ParseError("Failed to parse response")
        assert str(error) == "Error 5: Failed to parse response"
        assert error.message == "Failed to parse response"
        assert error.code == 5

        # With custom code
        error = ParseError("Failed to parse response", code=105)
        assert str(error) == "Error 105: Failed to parse response"
        assert error.message == "Failed to parse response"
        assert error.code == 105

    def test_config_error(self) -> None:
        """Test ConfigError."""
        error = ConfigError("Invalid configuration")
        assert str(error) == "Error 6: Invalid configuration"
        assert error.message == "Invalid configuration"
        assert error.code == 6

        # With custom code
        error = ConfigError("Invalid configuration", code=106)
        assert str(error) == "Error 106: Invalid configuration"
        assert error.message == "Invalid configuration"
        assert error.code == 106
