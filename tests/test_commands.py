"""Tests for the squeeze CLI commands."""

from unittest.mock import MagicMock, patch

from pytest import mark

from squeeze.cli.commands import (
    DisplayCommandArgs,
    PlayerCommandArgs,
    SeekCommandArgs,
    StatusCommandArgs,
    display_command,
    format_time,
    get_player_id,
    seek_command,
    status_command,
)
from squeeze.json_client import SqueezeJsonClient


def test_format_time() -> None:
    """Test the format_time function."""
    # Test seconds only
    assert format_time(45) == "0:45"

    # Test minutes and seconds
    assert format_time(65) == "1:05"
    assert format_time(125) == "2:05"

    # Test hours, minutes and seconds
    assert format_time(3665) == "1:01:05"


def test_get_player_id_with_arg() -> None:
    """Test get_player_id when player ID is provided."""
    client = MagicMock()
    args = PlayerCommandArgs(player_id="00:11:22:33:44:55")

    result = get_player_id(args, client)

    assert result == "00:11:22:33:44:55"
    # Shouldn't call get_players when ID is provided
    client.get_players.assert_not_called()


def test_get_player_id_no_player_found(mock_json_client: MagicMock) -> None:
    """Test get_player_id when no players are found."""
    # Set up mock to return empty list
    mock_json_client.get_players.return_value = []

    # Redirect stdout/stderr for testing
    with patch("sys.stdout"), patch("sys.stderr"):
        args = PlayerCommandArgs(player_id=None, no_interactive=True)
        result = get_player_id(args, mock_json_client)

        assert result is None
        mock_json_client.get_players.assert_called_once()


# Use parametrize to test multiple command scenarios
@mark.parametrize(
    "command, message, duration, expected_params",
    [
        # Display command tests
        ("display", "Test Message", None, ["line1", "Test Message"]),
        (
            "display",
            "Line1\\nLine2",
            None,
            ["line1", "Line1", "line2", "Line2"],
        ),
        (
            "display",
            "Line1\\nLine2\\nLine3",
            None,
            ["line1", "Line1", "line2", "Line2", "line3", "Line3"],
        ),
        (
            "display",
            "Message",
            5,
            ["line1", "Message", "duration", "5"],
        ),
    ],
)
def test_display_command(
    command: str,
    message: str,
    duration: int | None,
    expected_params: list[str],
    mock_json_client: MagicMock,
    player_id: str,
) -> None:
    """Test display_command with various arguments."""
    # Create a DisplayCommandArgs instance
    args = DisplayCommandArgs(player_id=player_id, message=message, duration=duration)

    # Redirect stdout/stderr for testing
    with (
        patch("sys.stdout"),
        patch("sys.stderr"),
        patch("squeeze.cli.commands.get_server_url") as mock_get_url,
        patch("squeeze.cli.commands.create_client") as mock_create_client,
        patch("squeeze.cli.commands.get_player_id") as mock_get_player_id,
    ):
        # Configure mocks
        mock_get_url.return_value = "http://example.com:9000"
        mock_create_client.return_value = mock_json_client
        mock_get_player_id.return_value = player_id

        # Run the command
        if command == "display":
            display_command(args)

        # Verify
        mock_json_client.send_command.assert_called_once()
        command_args = mock_json_client.send_command.call_args[0]

        # Check player_id and command name
        assert command_args[0] == player_id
        assert command_args[1] == "display"

        # Check command parameters match expected
        for _, param in enumerate(expected_params):
            assert param in command_args[2]


@mark.parametrize(
    "position, expected_seconds",
    [
        # Direct seconds
        ("30", 30),
        # MM:SS format
        ("1:30", 90),
        # HH:MM:SS format
        ("1:30:45", 5445),
    ],
)
def test_seek_command(
    position: str, expected_seconds: int, mock_json_client: MagicMock, player_id: str
) -> None:
    """Test seek_command with various time formats."""
    # Create SeekCommandArgs instance
    args = SeekCommandArgs(player_id=player_id, position=position)

    # Redirect stdout/stderr for testing
    with (
        patch("sys.stdout"),
        patch("sys.stderr"),
        patch("squeeze.cli.commands.get_server_url") as mock_get_url,
        patch("squeeze.cli.commands.create_client") as mock_create_client,
        patch("squeeze.cli.commands.get_player_id") as mock_get_player_id,
    ):
        # Configure mocks
        mock_get_url.return_value = "http://example.com:9000"
        mock_create_client.return_value = mock_json_client
        mock_get_player_id.return_value = player_id

        # Give the client a seek_to_time method
        mock_json_client.seek_to_time = MagicMock()

        # Run the command
        seek_command(args)

        # Verify
        mock_json_client.seek_to_time.assert_called_once_with(
            player_id, expected_seconds
        )


def test_status_command_basic(mock_json_client: MagicMock, player_id: str) -> None:
    """Test basic status_command functionality."""
    # Create StatusCommandArgs instance
    args = StatusCommandArgs(player_id=player_id, live=False)

    # Redirect stdout/stderr for testing
    with (
        patch("sys.stdout"),
        patch("sys.stderr"),
        patch("squeeze.cli.commands.get_server_url") as mock_get_url,
        patch("squeeze.cli.commands.create_client") as mock_create_client,
        patch("squeeze.cli.commands.get_player_id") as mock_get_player_id,
    ):
        # Configure mocks
        mock_get_url.return_value = "http://example.com:9000"
        mock_create_client.return_value = mock_json_client
        mock_get_player_id.return_value = player_id

        # Run the command
        status_command(args)

        # Verify the client was called without subscribe
        mock_json_client.get_player_status.assert_called_once()
        assert mock_json_client.get_player_status.call_args[0][0] == player_id
        # Should be only one arg (player_id) when live=False
        assert len(mock_json_client.get_player_status.call_args[0]) == 1


def test_status_command_live_mode(mock_json_client: MagicMock, player_id: str) -> None:
    """Test status_command in live mode."""
    # Create StatusCommandArgs instance with live=True
    args = StatusCommandArgs(player_id=player_id, live=True)

    # Redirect stdout/stderr for testing
    with (
        patch("sys.stdout"),
        patch("sys.stderr"),
        patch("squeeze.cli.commands.get_server_url") as mock_get_url,
        patch("squeeze.cli.commands.create_client") as mock_create_client,
        patch("squeeze.cli.commands.get_player_id") as mock_get_player_id,
        # Patch the keyboard functions to avoid stdin issues in tests
        patch(
            "squeeze.cli.commands.is_keystroke_module_available"
        ) as mock_keyboard_check,
        patch("squeeze.cli.commands.get_keypress") as mock_get_keypress,
    ):
        # Configure mocks
        mock_get_url.return_value = "http://example.com:9000"
        mock_create_client.return_value = mock_json_client
        mock_get_player_id.return_value = player_id
        mock_keyboard_check.return_value = False  # Disable keyboard in tests
        mock_get_keypress.return_value = None  # No keypress

        # We'll patch the hasattr and isinstance functions to make our type checks pass
        # This avoids the type error with __class__ assignment
        with (
            patch("squeeze.cli.commands.hasattr") as mock_hasattr,
            patch("squeeze.cli.commands.isinstance") as mock_isinstance,
        ):

            # Configure mocks to pass the type checks in the code
            mock_hasattr.side_effect = lambda obj, attr: (
                True
                if obj is mock_json_client
                and attr in ["get_player_status", "send_command"]
                else hasattr(obj, attr)
            )
            mock_isinstance.side_effect = lambda obj, cls: (
                True
                if obj is mock_json_client and cls is SqueezeJsonClient
                else isinstance(obj, cls)
            )

            # Simulate KeyboardInterrupt after first call
            mock_json_client.get_player_status.side_effect = [
                {
                    "player_id": player_id,
                    "player_name": "Test",
                    "power": 1,
                    "status": "playing",
                    "volume": 50,
                    "current_track": {
                        "title": "Test",
                        "artist": "Test",
                        "position": 30,
                        "duration": 300,
                    },
                },
                KeyboardInterrupt(),
            ]

            # Run the command, should exit on KeyboardInterrupt
            status_command(args)

            # Verify subscribe was used
            mock_json_client.get_player_status.assert_called_with(
                player_id, subscribe=True
            )
