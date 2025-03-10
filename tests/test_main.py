"""Tests for the CLI main entry point."""

import argparse
import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from squeeze.cli.main import create_parser, main, parse_args


class TestParser:
    """Tests for the command-line argument parser."""

    def test_create_parser(self) -> None:
        """Test creating the argument parser."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "squeeze"

    def test_parse_args_minimal(self) -> None:
        """Test parsing minimal command-line arguments."""
        args = parse_args(["status"])
        assert args.command == "status"
        assert args.player_id is None

    def test_parse_args_with_options(self) -> None:
        """Test parsing command-line arguments with options."""
        args = parse_args(["status", "00:11:22:33:44:55", "--live"])
        assert args.command == "status"
        assert args.player_id == "00:11:22:33:44:55"
        assert args.live is True

    def test_parse_args_with_server(self) -> None:
        """Test parsing command-line arguments with server URL."""
        args = parse_args(["--server", "http://example.com:9000", "players"])
        assert args.command == "players"
        assert args.server == "http://example.com:9000"


class TestMainFunction:
    """Tests for the main function."""

    def test_main_no_command(self) -> None:
        """Test main function with no command."""
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            result = main(["--server", "http://example.com:9000"])
            assert result == 1
            assert "Error: No command specified" in mock_stderr.getvalue()

    def test_main_unknown_command(self) -> None:
        """Test main function with unknown command."""
        # We need to handle the case where argparse calls sys.exit
        with patch("squeeze.cli.main.create_parser") as mock_create_parser:
            # Create a mock parser that behaves like we want
            mock_parser = MagicMock()

            # Configure the mock parser to raise SystemExit when an unknown command is used
            def mock_parse_args(args: list[str] | None = None) -> argparse.Namespace:
                if args and args[0] == "unknown_command":
                    # Write to stderr and exit like argparse does
                    sys.stderr.write(
                        "error: argument command: invalid choice: 'unknown_command'"
                    )
                    sys.exit(2)
                return argparse.Namespace(command=None)

            mock_parser.parse_args = mock_parse_args
            mock_create_parser.return_value = mock_parser

            # Now patch sys.exit so it doesn't terminate our test
            with patch("sys.exit") as mock_exit:
                # Capture stderr for error message
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    main(["unknown_command"])

                    # Verify sys.exit was called with the correct code
                    mock_exit.assert_called_once_with(2)

                    # Verify the error message was printed
                    assert "unknown_command" in mock_stderr.getvalue()

    def test_main_players_command(self) -> None:
        """Test main function with players command."""
        with patch("squeeze.cli.main.players_command") as mock_command:
            result = main(["players"])
            assert result == 0
            mock_command.assert_called_once()
            # Now commands receive dataclass instances
            args = mock_command.call_args[0][0]
            assert hasattr(args, "server")

    def test_main_status_command(self) -> None:
        """Test main function with status command."""
        with patch("squeeze.cli.main.status_command") as mock_command:
            result = main(["status", "00:11:22:33:44:55", "--live"])
            assert result == 0
            mock_command.assert_called_once()
            # Verify the arguments passed to the StatusCommandArgs
            args = mock_command.call_args[0][0]
            assert args.player_id == "00:11:22:33:44:55"
            assert args.live is True

    @pytest.mark.parametrize(
        "command,mock_function,extra_args",
        [
            ("play", "play_command", []),
            ("pause", "pause_command", []),
            ("stop", "stop_command", []),
            ("volume", "volume_command", ["50"]),
            ("power", "power_command", ["on"]),
            ("config", "config_command", ["--set-server", "http://example.com:9000"]),
            ("search", "search_command", ["test"]),
            ("server", "server_command", []),
            ("next", "next_command", []),
            ("prev", "prev_command", []),
            ("jump", "jump_command", ["0"]),
            ("now", "now_playing_command", []),
            ("shuffle", "shuffle_command", []),
            ("repeat", "repeat_command", []),
            ("remote", "remote_command", ["up"]),
            ("display", "display_command", ["Hello World"]),
            ("seek", "seek_command", ["30"]),
        ],
    )
    def test_main_commands(
        self, command: str, mock_function: str, extra_args: list[str]
    ) -> None:
        """Test main function with various commands."""
        with patch(f"squeeze.cli.main.{mock_function}") as mock_command:
            args = [command] + extra_args

            result = main(args)
            assert result == 0
            mock_command.assert_called_once()

            # Verify that we are passing a dataclass
            args_obj = mock_command.call_args[0][0]

            # All command args dataclasses have debug_command attribute
            assert hasattr(args_obj, "debug_command")

            # For commands with extra args, check some specific attributes
            if command == "volume" and extra_args:
                assert hasattr(args_obj, "volume")
                assert args_obj.volume == 50
            elif command == "power" and extra_args:
                assert hasattr(args_obj, "state")
                assert args_obj.state == "on"
            elif command == "config" and extra_args:
                assert hasattr(args_obj, "set_server")
                assert args_obj.set_server == "http://example.com:9000"
            elif command == "search" and extra_args:
                assert hasattr(args_obj, "term")
                assert args_obj.term == "test"
            elif command == "jump" and extra_args:
                assert hasattr(args_obj, "index")
                assert args_obj.index == 0
            elif command == "remote" and extra_args:
                assert hasattr(args_obj, "button")
                assert args_obj.button == "up"
            elif command == "display" and extra_args:
                assert hasattr(args_obj, "message")
                assert args_obj.message == "Hello World"
            elif command == "seek" and extra_args:
                assert hasattr(args_obj, "position")
                assert args_obj.position == "30"
