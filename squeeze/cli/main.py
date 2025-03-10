"""
Main CLI entry point for Squeeze.
"""

import argparse
import sys

from squeeze import __version__
from squeeze.cli.commands import (
    config_command,
    display_command,
    jump_command,
    next_command,
    now_playing_command,
    pause_command,
    play_command,
    players_command,
    power_command,
    prev_command,
    remote_command,
    repeat_command,
    search_command,
    seek_command,
    server_command,
    shuffle_command,
    status_command,
    stop_command,
    volume_command,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        The argument parser
    """
    parser = argparse.ArgumentParser(
        prog="squeeze",
        description="CLI for interacting with SqueezeBox players over the network",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--server",
        help="SqueezeBox server URL (defaults to value in ~/.squeezerc)",
    )

    # API selection
    parser.add_argument(
        "--json", action="store_true", help="Use JSON API (default is auto-detect)"
    )
    parser.add_argument(
        "--no-json",
        action="store_false",
        dest="json",
        help="Force HTML-based API (don't use JSON API)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show player status")
    status_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to show status for"
    )
    status_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    status_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )
    status_parser.add_argument(
        "--live",
        action="store_true",
        help="Live mode - continuously display player status with updates",
    )

    # Players command
    subparsers.add_parser("players", help="List available players")

    # Play command
    play_parser = subparsers.add_parser("play", help="Send play command to a player")
    play_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    play_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    play_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Pause command
    pause_parser = subparsers.add_parser("pause", help="Send pause command to a player")
    pause_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    pause_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    pause_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Send stop command to a player")
    stop_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    stop_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    stop_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Volume command
    volume_parser = subparsers.add_parser("volume", help="Set volume for a player")
    volume_parser.add_argument("volume", help="Volume level (0-100)")
    volume_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to set volume for"
    )
    volume_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    volume_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )
    volume_parser.add_argument(
        "--debug", action="store_true", help="Debug volume controls"
    )
    volume_parser.add_argument(
        "--debug-command", action="store_true", help="Debug command URL"
    )

    # Power command
    power_parser = subparsers.add_parser("power", help="Set power state for a player")
    power_parser.add_argument("state", choices=["on", "off"], help="Power state")
    power_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to set power state for"
    )
    power_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    power_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Search command (JSON API only)
    search_parser = subparsers.add_parser(
        "search", help="Search for music in the library (requires JSON API)"
    )
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument(
        "--type",
        choices=["all", "artists", "albums", "tracks"],
        default="all",
        help="Type of items to search for",
    )

    # Server command (JSON API only)
    server_parser = subparsers.add_parser(
        "server", help="Get server status information (requires JSON API)"
    )
    # Add API selection flags explicitly to server subparser
    server_parser.add_argument(
        "--json", action="store_true", help="Use JSON API (default is auto-detect)"
    )
    server_parser.add_argument(
        "--no-json",
        action="store_false",
        dest="json",
        help="Force HTML-based API (don't use JSON API)",
    )

    # Next track command
    next_parser = subparsers.add_parser("next", help="Skip to next track")
    next_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    next_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    next_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Previous track command
    prev_parser = subparsers.add_parser("prev", help="Skip to previous track")
    prev_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    prev_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    prev_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )
    prev_parser.add_argument(
        "--threshold",
        type=int,
        default=5,
        help="Position threshold in seconds (default 5): if track position > threshold, restart current track; otherwise go to previous track",
    )

    # Jump to track command
    jump_parser = subparsers.add_parser(
        "jump", help="Jump to a specific track in the playlist"
    )
    jump_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    jump_parser.add_argument("index", type=int, help="Track index to jump to (0-based)")
    jump_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    jump_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Now Playing command
    now_playing_parser = subparsers.add_parser(
        "now",
        help="Show Now Playing screen on the player (mimics remote control button)",
    )
    now_playing_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    now_playing_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    now_playing_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )
    now_playing_parser.add_argument(
        "--debug-command", action="store_true", help="Debug command URL"
    )

    # Shuffle command
    shuffle_parser = subparsers.add_parser("shuffle", help="Control shuffle mode")
    shuffle_parser.add_argument(
        "mode",
        nargs="?",
        choices=["off", "songs", "albums"],
        help="Shuffle mode to set (if omitted, cycles through modes)",
    )
    shuffle_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    shuffle_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    shuffle_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Repeat command
    repeat_parser = subparsers.add_parser("repeat", help="Control repeat mode")
    repeat_parser.add_argument(
        "mode",
        nargs="?",
        choices=["off", "one", "all"],
        help="Repeat mode to set (if omitted, cycles through modes)",
    )
    repeat_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    repeat_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    repeat_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Remote control button command
    remote_parser = subparsers.add_parser(
        "remote", help="Send remote control button presses"
    )
    remote_parser.add_argument(
        "button",
        choices=["up", "down", "left", "right", "select", "browse"],
        help="Button to press",
    )
    remote_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    remote_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    remote_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Display command
    display_parser = subparsers.add_parser(
        "display", help="Display a message on the player's screen"
    )
    display_parser.add_argument(
        "message", help="Message to display (use \\n for line breaks)"
    )
    display_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send message to"
    )
    display_parser.add_argument(
        "--duration", type=int, help="Display duration in seconds"
    )
    display_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    display_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )

    # Seek command
    seek_parser = subparsers.add_parser(
        "seek", help="Seek to a specific position in the current track"
    )
    seek_parser.add_argument(
        "position", help="Position to seek to (seconds or MM:SS format)"
    )
    seek_parser.add_argument(
        "player_id", nargs="?", help="ID of the player to send command to"
    )
    seek_parser.add_argument(
        "--interactive",
        action="store_true",
        dest="interactive",
        help="Use interactive player selection (default when TTY available)",
    )
    seek_parser.add_argument(
        "--no-interactive",
        action="store_true",
        dest="no_interactive",
        help="Disable interactive player selection",
    )
    seek_parser.add_argument(
        "--debug-command", action="store_true", help="Debug command URL"
    )

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument(
        "--set-server", help="Set SqueezeBox server URL in config"
    )

    return parser


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments
    """
    parser = create_parser()
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code
    """
    parsed_args = parse_args(args)

    if not parsed_args.command:
        print("Error: No command specified", file=sys.stderr)
        return 1

    # Convert args to dict for passing to command functions
    args_dict = vars(parsed_args)

    # Dispatch to command function
    if parsed_args.command == "status":
        status_command(args_dict)
    elif parsed_args.command == "players":
        players_command(args_dict)
    elif parsed_args.command == "play":
        play_command(args_dict)
    elif parsed_args.command == "pause":
        pause_command(args_dict)
    elif parsed_args.command == "stop":
        stop_command(args_dict)
    elif parsed_args.command == "volume":
        volume_command(args_dict)
    elif parsed_args.command == "power":
        power_command(args_dict)
    elif parsed_args.command == "config":
        config_command(args_dict)
    elif parsed_args.command == "search":
        search_command(args_dict)
    elif parsed_args.command == "server":
        server_command(args_dict)
    elif parsed_args.command == "next":
        next_command(args_dict)
    elif parsed_args.command == "prev":
        prev_command(args_dict)
    elif parsed_args.command == "jump":
        jump_command(args_dict)
    elif parsed_args.command == "now":
        now_playing_command(args_dict)
    elif parsed_args.command == "shuffle":
        shuffle_command(args_dict)
    elif parsed_args.command == "repeat":
        repeat_command(args_dict)
    elif parsed_args.command == "remote":
        remote_command(args_dict)
    elif parsed_args.command == "display":
        display_command(args_dict)
    elif parsed_args.command == "seek":
        seek_command(args_dict)
    else:
        print(f"Error: Unknown command: {parsed_args.command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
