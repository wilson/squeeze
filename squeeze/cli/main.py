"""
Main CLI entry point for Squeeze.
"""

import argparse
import sys

from squeeze import __version__
from squeeze.cli.commands import (  # Command functions; Command argument classes
    ConfigCommandArgs,
    DisplayCommandArgs,
    JumpCommandArgs,
    PlayerCommandArgs,
    PlayersCommandArgs,
    PowerCommandArgs,
    PrevCommandArgs,
    RemoteCommandArgs,
    RepeatCommandArgs,
    SearchCommandArgs,
    SeekCommandArgs,
    ServerCommandArgs,
    ShuffleCommandArgs,
    StatusCommandArgs,
    VolumeCommandArgs,
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

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server commands (first group - server-related)
    subparsers.add_parser("server", help="Get server status information")

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument(
        "--set-server", help="Set SqueezeBox server URL in config"
    )

    # Players command
    subparsers.add_parser("players", help="List available players")

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

    # Search command
    search_parser = subparsers.add_parser(
        "search", help="Search for music in the library"
    )
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument(
        "--type",
        choices=["all", "artists", "albums", "tracks"],
        default="all",
        help="Type of items to search for",
    )

    # === Playback Control Commands ===

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

    # === Playback Settings Commands ===

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

    # === Display and Remote Control Commands ===

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

    # Get args as a dictionary
    args_dict = vars(parsed_args)

    # Common arguments for all commands
    server = args_dict.get("server")

    # Player command common arguments
    player_id = args_dict.get("player_id")
    interactive = args_dict.get("interactive", False)
    no_interactive = args_dict.get("no_interactive", False)

    # Create the appropriate dataclass based on the command and dispatch
    if parsed_args.command == "status":
        live = args_dict.get("live", False)
        status_args = StatusCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            live=live,
        )
        status_command(status_args)
    elif parsed_args.command == "players":
        players_args = PlayersCommandArgs(server=server)
        players_command(players_args)
    elif parsed_args.command in ("play", "pause", "stop", "now"):
        player_args = PlayerCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
        )
        if parsed_args.command == "play":
            play_command(player_args)
        elif parsed_args.command == "pause":
            pause_command(player_args)
        elif parsed_args.command == "stop":
            stop_command(player_args)
        else:  # "now"
            now_playing_command(player_args)
    elif parsed_args.command == "volume":
        volume_str = args_dict.get("volume", "0")
        # Convert to int for the dataclass
        try:
            volume = int(volume_str)
        except (TypeError, ValueError):
            volume = 0

        volume_args = VolumeCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            volume=volume,
        )
        volume_command(volume_args)
    elif parsed_args.command == "power":
        state = args_dict.get("state", "on")
        power_args = PowerCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            state=state,
        )
        power_command(power_args)
    elif parsed_args.command == "config":
        set_server = args_dict.get("set_server")
        config_args = ConfigCommandArgs(server=server, set_server=set_server)
        config_command(config_args)
    elif parsed_args.command == "search":
        term = args_dict.get("term", "")
        search_type = args_dict.get("type")
        search_args = SearchCommandArgs(server=server, term=term, type=search_type)
        search_command(search_args)
    elif parsed_args.command == "server":
        server_args = ServerCommandArgs(server=server)
        server_command(server_args)
    elif parsed_args.command == "next":
        next_args = PlayerCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
        )
        next_command(next_args)
    elif parsed_args.command == "prev":
        threshold = args_dict.get("threshold", 5)
        prev_args = PrevCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            threshold=threshold,
        )
        prev_command(prev_args)
    elif parsed_args.command == "jump":
        index_str = args_dict.get("index", "0")
        # Convert to int for the dataclass
        try:
            index = int(index_str)
        except (TypeError, ValueError):
            index = 0

        jump_args = JumpCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            index=index,
        )
        jump_command(jump_args)
    elif parsed_args.command == "shuffle":
        mode = args_dict.get("mode")
        shuffle_args = ShuffleCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            mode=mode,
        )
        shuffle_command(shuffle_args)
    elif parsed_args.command == "repeat":
        mode = args_dict.get("mode")
        repeat_args = RepeatCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            mode=mode,
        )
        repeat_command(repeat_args)
    elif parsed_args.command == "remote":
        button = args_dict.get("button", "select")
        remote_args = RemoteCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            button=button,
        )
        remote_command(remote_args)
    elif parsed_args.command == "display":
        message = args_dict.get("message", "")
        duration = args_dict.get("duration")
        display_args = DisplayCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            message=message,
            duration=duration,
        )
        display_command(display_args)
    elif parsed_args.command == "seek":
        position = args_dict.get("position", "")
        seek_args = SeekCommandArgs(
            server=server,
            player_id=player_id,
            interactive=interactive,
            no_interactive=no_interactive,
            position=position,
        )
        seek_command(seek_args)
    else:
        print(f"Error: Unknown command: {parsed_args.command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
