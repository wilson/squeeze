"""
CLI commands for Squeeze.
"""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from squeeze.client_factory import create_client
from squeeze.config import get_server_url, load_config, save_config
from squeeze.constants import RepeatMode, ShuffleMode
from squeeze.exceptions import (
    APIError,
    CommandError,
    ConnectionError,
    ParseError,
    SqueezeError,
)
from squeeze.json_client import PlayerStatus, SqueezeJsonClient
from squeeze.ui import select_player

# Type alias for the JSON client
ClientType = SqueezeJsonClient


def create_client_with_error_handling(server_url: str) -> SqueezeJsonClient:
    """Create a client with consistent error handling and messaging.

    Args:
        server_url: URL of the SqueezeBox server

    Returns:
        SqueezeJsonClient instance

    Raises:
        SystemExit: If client creation fails
    """
    try:
        return create_client(server_url)
    except ConnectionError as e:
        print(str(e), file=sys.stderr)
        print("\nTips:", file=sys.stderr)
        print("  • Make sure your SqueezeBox server is running", file=sys.stderr)
        print("  • Check the server URL with 'squeeze config'", file=sys.stderr)
        print("  • Try using a direct IP address instead of hostname", file=sys.stderr)
        print("  • Verify network connectivity to the server", file=sys.stderr)
        sys.exit(1)


# Command argument dataclasses for improved type safety
@dataclass
class CommandArgs:
    """Base class for command arguments."""

    server: str | None = None


@dataclass
class PlayerCommandArgs(CommandArgs):
    """Arguments for commands that operate on a player."""

    player_id: str | None = None
    interactive: bool = False
    no_interactive: bool = False


@dataclass
class StatusCommandArgs(PlayerCommandArgs):
    """Arguments for the status command."""

    live: bool = False


@dataclass
class VolumeCommandArgs(PlayerCommandArgs):
    """Arguments for the volume command."""

    volume: int = field(default=0)  # Default needed for dataclass rules


@dataclass
class ShuffleCommandArgs(PlayerCommandArgs):
    """Arguments for the shuffle command."""

    mode: Literal["off", "songs", "albums"] | None = None


@dataclass
class RepeatCommandArgs(PlayerCommandArgs):
    """Arguments for the repeat command."""

    mode: Literal["off", "one", "all"] | None = None


@dataclass
class SeekCommandArgs(PlayerCommandArgs):
    """Arguments for the seek command."""

    position: str = field(default="")  # Default needed for dataclass rules


@dataclass
class PowerCommandArgs(PlayerCommandArgs):
    """Arguments for the power command."""

    state: Literal["on", "off"] = field(default="on")


@dataclass
class RemoteCommandArgs(PlayerCommandArgs):
    """Arguments for the remote control command."""

    button: Literal["up", "down", "left", "right", "select", "browse"] = field(
        default="select"
    )


@dataclass
class DisplayCommandArgs(PlayerCommandArgs):
    """Arguments for the display command."""

    message: str = field(default="")
    duration: int | None = None


@dataclass
class JumpCommandArgs(PlayerCommandArgs):
    """Arguments for the jump command."""

    index: int = field(default=0)


@dataclass
class SearchCommandArgs(CommandArgs):
    """Arguments for the search command."""

    term: str = field(default="")
    type: Literal["all", "artists", "albums", "tracks"] | None = None


@dataclass
class ConfigCommandArgs(CommandArgs):
    """Arguments for the config command."""

    set_server: str | None = None


@dataclass
class PlayersCommandArgs(CommandArgs):
    """Arguments for the players command."""

    pass


@dataclass
class ServerCommandArgs(CommandArgs):
    """Arguments for the server command."""

    pass


def display_progress_bar(
    position: int | float | str, duration: int | float | str
) -> None:
    """Display a progress bar for track position.

    Args:
        position: Current position in seconds (can be int, float, or string)
        duration: Total duration in seconds (can be int, float, or string)
    """
    # Convert position and duration to float, with careful handling of types
    try:
        pos_float = float(position) if position is not None else 0
    except (ValueError, TypeError):
        pos_float = 0

    try:
        dur_float = float(duration) if duration is not None else 0
    except (ValueError, TypeError):
        dur_float = 0

    # Skip if invalid values
    if pos_float <= 0 or dur_float <= 0:
        return

    progress = min(1.0, pos_float / dur_float)
    bar_width = 40
    filled_width = int(bar_width * progress)
    bar = "█" * filled_width + "░" * (bar_width - filled_width)
    percent = int(progress * 100)
    print(f"  Progress: {bar} {percent}%")


def print_player_status(
    status: PlayerStatus, show_all_track_fields: bool = False
) -> None:
    """Format and print player status information.

    Args:
        status: Player status dictionary
        show_all_track_fields: Whether to display all track fields or only priority ones
    """
    # Basic player information
    print(f"Player: {status['player_name']} ({status['player_id']})")
    print(f"Power: {status['power']}")
    print(f"Status: {status['status']}")
    if status["volume"] is not None:
        print(f"Volume: {status['volume']}")

    # Print shuffle and repeat if available
    if "shuffle_mode" in status:
        print(f"Shuffle: {status['shuffle_mode']}")
    if "repeat_mode" in status:
        print(f"Repeat: {status['repeat_mode']}")

    # Print playlist info if available
    if "playlist_count" in status and status["playlist_count"] > 0:
        position = (
            status.get("playlist_position", 0) + 1
        )  # Convert to 1-based for display
        count = status["playlist_count"]
        print(f"Playlist: {position} of {count}")

    # Display current track information
    current_track = status["current_track"]
    if current_track and isinstance(current_track, dict):
        print("\nCurrent track:")
        # Priority order for fields
        priority_fields = [
            "title",
            "artist",
            "album",
            "position",
            "duration",
            "artwork",
        ]

        # First print priority fields in order
        for field in priority_fields:
            if field in current_track:
                # Format position and duration as time if needed
                if field == "position" or field == "duration":
                    value = format_time(current_track[field])
                else:
                    value = current_track[field]
                print(f"  {field.capitalize()}: {value}")

        # Show progress bar if position and duration are available
        if "position" in current_track and "duration" in current_track:
            display_progress_bar(current_track["position"], current_track["duration"])

        # Then print any remaining fields if requested
        if show_all_track_fields:
            for key, value in current_track.items():
                if key not in priority_fields:
                    print(f"  {key.capitalize()}: {value}")


def display_live_status(client: ClientType, player_id: str) -> None:
    """Display continuously updating status in live mode.

    Args:
        client: Squeeze client instance
        player_id: ID of the player to get status for
    """
    print("Live status mode. Press Ctrl+C to exit.")
    print()

    try:
        while True:
            try:
                # Use subscribe mode to get updates
                status = client.get_player_status(player_id, subscribe=True)

                # Clear the screen for a cleaner display
                # We can't use os.system('clear') because it's not portable
                print("\033[H\033[J", end="")  # ANSI escape code to clear screen

                # Print timestamp
                from datetime import datetime

                print(
                    f"Status as of {datetime.now().strftime('%H:%M:%S')} (Ctrl+C to exit)"
                )
                print()

                # Print the status information
                print_player_status(status)

                # Sleep briefly to handle cases where server doesn't support subscribe mode
                import time

                time.sleep(0.1)

            except (ConnectionError, APIError, ParseError, CommandError) as e:
                print(f"Error in live mode: {e}", file=sys.stderr)
                # In live mode, just print the error and continue
                import time

                time.sleep(5)  # Wait a bit before retrying

    except KeyboardInterrupt:
        print("\nExiting live mode.")


def status_command(args: StatusCommandArgs) -> None:
    """Show status of a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    live_mode = args.live
    client = create_client_with_error_handling(server_url)

    # Use the common get_player_id helper
    try:
        player_id = get_player_id(args, client)
        if not player_id:
            return
    except SqueezeError as e:
        print(f"Error getting player ID: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle live mode vs. one-time status display
    if live_mode:
        display_live_status(client, player_id)
    else:
        # Single status display
        try:
            status = client.get_player_status(player_id)
            print_player_status(status, show_all_track_fields=True)
        except (ConnectionError, APIError, ParseError, CommandError) as e:
            print(f"Error getting player status: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            sys.exit(1)


def format_time(seconds: int | str | float) -> str:
    """Format seconds as mm:ss or hh:mm:ss.

    Args:
        seconds: Time in seconds (supports int, float, or str)

    Returns:
        Formatted time string
    """
    try:
        # Convert to int to handle various input types
        if isinstance(seconds, str):
            seconds = int(float(seconds))
        else:
            seconds = int(seconds)

        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
    except (ValueError, TypeError):
        # Handle invalid input
        return "0:00"

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def players_command(args: PlayersCommandArgs) -> None:
    """List available players.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client(server_url)

    try:
        players = client.get_players()

        if not players:
            print("No players found")
            return

        print("Available players:")
        for player in players:
            print(f"  {player['id']}: {player['name']}")
    except Exception as e:
        print(f"Error getting players: {e}", file=sys.stderr)
        sys.exit(1)


def get_player_id(args: PlayerCommandArgs, client: ClientType) -> str | None:
    """Get player ID from arguments or interactive selection.

    Args:
        args: Command-line arguments as PlayerCommandArgs
        client: SqueezeJsonClient instance

    Returns:
        Player ID or None if no selection was made
    """
    player_id = args.player_id
    force_interactive = args.interactive
    disable_interactive = args.no_interactive

    # Interactive selection is needed if:
    # 1. Player ID is not provided, or
    # 2. Interactive mode is explicitly forced
    if not player_id or force_interactive:
        players = client.get_players()
        if not players:
            print("No players found")
            return None

        # Use pattern matching to handle the player selection flow
        match (disable_interactive, players):
            case (True, _):
                # Interactive mode disabled, just list players
                print("Available players:")
                for player in players:
                    print(f"  {player['id']}: {player['name']}")
                return None
            case (False, _):
                # Use interactive selection
                player_id = select_player(players)
                return player_id

    return player_id


def play_command(args: PlayerCommandArgs) -> None:
    """Send play command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "play")
        print(f"Play command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending play command: {e}", file=sys.stderr)
        sys.exit(1)


def pause_command(args: PlayerCommandArgs) -> None:
    """Send pause command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "pause")
        print(f"Pause command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending pause command: {e}", file=sys.stderr)
        sys.exit(1)


def stop_command(args: PlayerCommandArgs) -> None:
    """Send stop command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "stop")
        print(f"Stop command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending stop command: {e}", file=sys.stderr)
        sys.exit(1)


def volume_command(args: VolumeCommandArgs) -> None:
    """Set volume for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    volume = args.volume

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    # Validate volume (0-100)
    if volume < 0 or volume > 100:
        print("Error: Volume must be between 0 and 100", file=sys.stderr)
        sys.exit(1)

    try:
        client.send_command(player_id, "mixer", ["volume", str(volume)])
        print(f"Volume set to {volume} for player {player_id}")
    except Exception as e:
        print(f"Error setting volume: {e}", file=sys.stderr)
        sys.exit(1)


def power_command(args: PowerCommandArgs) -> None:
    """Set power state for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    state = args.state

    # Convert to 1/0
    state_value = "1" if state == "on" else "0"

    try:
        client.send_command(player_id, "power", [state_value])
        print(f"Power set to {state} for player {player_id}")
    except Exception as e:
        print(f"Error setting power: {e}", file=sys.stderr)
        sys.exit(1)


def display_search_results(
    items: list[dict[str, Any]], formatter: Callable[[dict[str, Any]], str]
) -> None:
    """Display search results with consistent formatting.

    Args:
        items: List of items to display
        formatter: Function to format each item for display
    """
    max_display = 10
    for item in items[:max_display]:
        print(f"  {formatter(item)}")

    if len(items) > max_display:
        print(f"  ... and {len(items) - max_display} more")
    print()


def search_command(args: SearchCommandArgs) -> None:
    """Search for music in the library.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    # Verify the client has the required method
    if not hasattr(client, "get_artists"):
        print("Error: Server doesn't support this command", file=sys.stderr)
        sys.exit(1)

    search_term = args.term
    if not search_term:
        print("Error: Search term is required", file=sys.stderr)
        sys.exit(1)

    search_type = args.type if args.type else "all"

    # Define formatters for each result type
    formatters = {
        "artists": lambda artist: f"{artist.get('artist')}",
        "albums": lambda album: f"{album.get('album')} by {album.get('artist', 'Unknown')}",
        "tracks": lambda track: f"{track.get('title')} by {track.get('artist', 'Unknown')} on {track.get('album', 'Unknown')}",
    }

    try:
        # For each type of search, fetch and display results
        for item_type, formatter in formatters.items():
            if search_type not in ["all", item_type]:
                continue

            print(f"{item_type.capitalize()} matching: {search_term}")

            # Get the appropriate method from the client
            search_method = getattr(client, f"get_{item_type}", None)
            if search_method:
                results = search_method(search=search_term)
                display_search_results(results, formatter)
            else:
                print(f"  Search for {item_type} not supported")
                print()

    except Exception as e:
        print(f"Error searching: {e}", file=sys.stderr)
        sys.exit(1)


def config_command(args: ConfigCommandArgs) -> None:
    """Manage configuration.

    Args:
        args: Command-line arguments
    """
    config = load_config()

    # With no arguments, print current config
    if not args.set_server:
        print(json.dumps(config, indent=2))
        return

    # Set server URL
    server_url = args.set_server
    config.setdefault("server", {})["url"] = server_url

    save_config(config)
    print(f"Server URL set to {server_url}")


def server_command(args: ServerCommandArgs) -> None:
    """Get server status information.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)

    try:
        client = create_client(server_url)
    except ConnectionError as e:
        print(f"Error connecting to server: {e}", file=sys.stderr)
        print(
            "Check your server URL or use --server to specify a different server.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Verify the client has the required method
    if not hasattr(client, "get_server_status"):
        print("Error: Server doesn't support this command", file=sys.stderr)
        print(
            "Try checking your server URL or using --server to specify a different server",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        status = client.get_server_status()

        # Print basic server information
        print("Server Information:")
        print(f"  Version: {status.get('version', 'Unknown')}")
        print(f"  Name: {status.get('server_name', 'Unknown')}")
        print(f"  UUID: {status.get('uuid', 'Unknown')}")
        print()

        # Print player count
        player_count = status.get("player_count", len(status.get("players_loop", [])))
        print(f"Connected Players: {player_count}")

        # Print additional info
        if "info" in status:
            info = status["info"]
            print("Library Information:")
            for key, value in info.items():
                if key.startswith("total_"):
                    print(f"  {key.replace('total_', '').capitalize()}: {value}")

        # Or use the direct total fields we added
        elif any(key.startswith("total_") for key in status.keys()):
            print("Library Information:")
            for key, value in status.items():
                if key.startswith("total_"):
                    print(f"  {key.replace('total_', '').capitalize()}: {value}")

    except (ConnectionError, APIError, ParseError) as e:
        print(f"Error getting server status: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def next_command(args: PlayerCommandArgs) -> None:
    """Send next track command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "playlist", ["index", "+1"])
        print(f"Next track command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending next track command: {e}", file=sys.stderr)
        sys.exit(1)


def jump_command(args: JumpCommandArgs) -> None:
    """Jump to a specific track in the playlist.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    track_index = args.index

    try:
        # Use 'playlist jump' instead of 'playlist index' to immediately play the track
        client.send_command(player_id, "playlist", ["jump", str(track_index)])
        print(
            f"Jumped to and started playing track {track_index} for player {player_id}"
        )
    except Exception as e:
        print(f"Error jumping to track: {e}", file=sys.stderr)
        sys.exit(1)


def extract_track_position(status: PlayerStatus) -> int:
    """Extract current track position in seconds from player status.

    Args:
        status: Player status dictionary

    Returns:
        Current position in seconds
    """
    import re

    # Use pattern matching to extract position
    match status:
        # Case 1: Position is in current_track dictionary
        case {"current_track": {"position": position}}:
            # Handle any numeric type (int, float, str)
            try:
                if isinstance(position, str):
                    return int(float(position))
                return int(position)
            except (ValueError, TypeError):
                return 0

        # Case 2: Extract from status text if it contains "X of Y" format
        case {"status": status_text} if (
            isinstance(status_text, str) and "of" in status_text
        ):
            if match := re.search(r"(\d+)\s+of\s+(\d+)", status_text):
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    return 0

    # Default case: No position found
    return 0


def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_tries: int = 3,
    retry_delay: float = 1.0,
    fallback_func: Callable[..., Any] | None = None,
) -> Any:
    """Execute a function with retry logic and optional fallback.

    Args:
        func: Function to call
        *args: Arguments to pass to the function
        max_tries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        fallback_func: Optional fallback function to try on second attempt

    Returns:
        Result of the function call if successful

    Raises:
        Exception: The last exception encountered if all attempts fail
    """
    import time

    last_error = None

    for attempt in range(max_tries):
        try:
            result = func(*args)
            return result  # Success, return the result
        except Exception as e:
            last_error = e

            if attempt < max_tries - 1:
                # Wait before retry, with increasing backoff
                time.sleep(retry_delay * (attempt + 1))

                # Try fallback on second attempt if provided
                if attempt == 1 and fallback_func is not None:
                    try:
                        result = fallback_func(*args)
                        return result  # Fallback succeeded
                    except Exception:
                        # Fallback failed, continue with normal retries
                        pass

    # If we get here, all attempts failed
    if last_error:
        raise last_error

    # Shouldn't reach here, but just in case
    raise Exception("All retry attempts failed without a specific error")


def restart_track(client: ClientType, player_id: str) -> None:
    """Seek to the beginning of the current track.

    Args:
        client: Squeeze client instance
        player_id: ID of the player

    Raises:
        Exception: If seeking fails after retry attempts
    """

    # Define the primary and fallback functions
    def primary_seek() -> None:
        return client.seek_to_time(player_id, 0)

    def fallback_seek() -> None:
        return client.send_command(player_id, "time", ["0"])

    # Use the retry wrapper
    with_retry(primary_seek, max_tries=3, retry_delay=0.5, fallback_func=fallback_seek)


@dataclass
class PrevCommandArgs(PlayerCommandArgs):
    """Arguments for the prev command."""

    threshold: int = 5


def prev_command(args: PrevCommandArgs) -> None:
    """Send previous track command to a player.

    Mimics the behavior of remote controls:
    - If current track position is > 5 seconds, go to the beginning of the current track
    - If current track position is <= 5 seconds, go to the previous track

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        # Get threshold from args
        threshold = args.threshold

        # First check the current track position
        status = client.get_player_status(player_id)
        position = extract_track_position(status)

        # If we're past the threshold, go to the beginning of the current track
        if position > threshold:
            try:
                # Use the existing restart_track function which already uses with_retry
                restart_track(client, player_id)
                print(f"Restarted current track for player {player_id}")
            except Exception as e:
                print(f"Error seeking to start of track: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Otherwise, go to the previous track
            try:
                # Define the relative index function (primary method)
                def go_to_prev_track_relative() -> None:
                    # Use "index -1" with no comma between index and -1 for relative positioning
                    return client.send_command(player_id, "playlist", ["index -1"])

                # Define the absolute index function (fallback method)
                def go_to_prev_track_absolute() -> None:
                    # Try with direct playlist index command
                    curr_pos = status.get("playlist_position", 0)
                    if curr_pos > 0:
                        # Go to the previous track by explicit index
                        return client.send_command(
                            player_id, "playlist", ["index", str(curr_pos - 1)]
                        )
                    raise ValueError("Already at first track")

                # Use the retry wrapper
                with_retry(
                    go_to_prev_track_relative,
                    max_tries=3,
                    retry_delay=0.5,
                    fallback_func=go_to_prev_track_absolute,
                )
                print(f"Previous track command sent to player {player_id}")
            except Exception as e:
                print(f"Error sending previous track command: {e}", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error sending previous track command: {e}", file=sys.stderr)
        sys.exit(1)


def now_playing_command(args: PlayerCommandArgs) -> None:
    """Show Now Playing screen on a player.

    This mimics pressing the Now Playing button on the official remote control,
    displaying the currently playing track in the server-configured format.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        # Use the show_now_playing method
        client.show_now_playing(player_id)
        print(f"Now Playing screen activated for player {player_id}")
    except Exception as e:
        print(f"Error showing Now Playing screen: {e}", file=sys.stderr)
        sys.exit(1)


def shuffle_command(args: ShuffleCommandArgs) -> None:
    """Set or cycle through shuffle modes.

    Supported modes:
    - off: No shuffling
    - songs: Shuffle songs
    - albums: Shuffle albums

    If no mode is specified, cycle through modes in the order: off -> songs -> albums -> off.

    Args:
        args: Command-line arguments as ShuffleCommandArgs
    """
    server_url = get_server_url(args.server)
    mode = args.mode

    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    # Use pattern matching for cleaner flow control
    match mode:
        case None:
            # Cycle to next mode if none specified
            try:
                status = client.get_player_status(player_id)
                current_mode = status.get("shuffle", 0)
                next_mode = (current_mode + 1) % 3
                mode_value = str(next_mode)
                mode_name = ShuffleMode.to_string(next_mode)
            except Exception as e:
                print(f"Error getting current shuffle mode: {e}", file=sys.stderr)
                sys.exit(1)
        case "off":
            mode_value = str(ShuffleMode.OFF)
            mode_name = ShuffleMode.to_string(ShuffleMode.OFF)
        case "songs":
            mode_value = str(ShuffleMode.SONGS)
            mode_name = ShuffleMode.to_string(ShuffleMode.SONGS)
        case "albums":
            mode_value = str(ShuffleMode.ALBUMS)
            mode_name = ShuffleMode.to_string(ShuffleMode.ALBUMS)

    try:
        client.send_command(player_id, "playlist", ["shuffle", mode_value])
        print(f"Shuffle mode set to '{mode_name}' for player {player_id}")
    except Exception as e:
        print(f"Error setting shuffle mode: {e}", file=sys.stderr)
        sys.exit(1)


def repeat_command(args: RepeatCommandArgs) -> None:
    """Set or cycle through repeat modes.

    Supported modes:
    - off: No repeat
    - one: Repeat current track
    - all: Repeat entire playlist

    If no mode is specified, cycle through modes in the order: off -> all -> one -> off.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    mode = args.mode

    # Use pattern matching for cleaner flow control
    match mode:
        case None:
            # Cycle to next mode if none specified
            try:
                status = client.get_player_status(player_id)
                current_mode = status.get("repeat", 0)

                # Define the cycle order: 0 (off) -> 2 (all) -> 1 (one) -> 0 (off)
                # This order matches how most music players cycle through repeat modes
                next_mode = (
                    RepeatMode.ALL
                    if current_mode == RepeatMode.OFF
                    else (
                        RepeatMode.ONE
                        if current_mode == RepeatMode.ALL
                        else RepeatMode.OFF
                    )  # RepeatMode.ONE or any other case
                )

                mode_value = str(next_mode)
                mode_name = RepeatMode.to_string(next_mode)
            except Exception as e:
                print(f"Error getting current repeat mode: {e}", file=sys.stderr)
                sys.exit(1)
        case "off":
            mode_value = str(RepeatMode.OFF)
            mode_name = RepeatMode.to_string(RepeatMode.OFF)
        case "one":
            mode_value = str(RepeatMode.ONE)
            mode_name = RepeatMode.to_string(RepeatMode.ONE)
        case "all":
            mode_value = str(RepeatMode.ALL)
            mode_name = RepeatMode.to_string(RepeatMode.ALL)

    try:
        client.send_command(player_id, "playlist", ["repeat", mode_value])
        print(f"Repeat mode set to '{mode_name}' for player {player_id}")
    except Exception as e:
        print(f"Error setting repeat mode: {e}", file=sys.stderr)
        sys.exit(1)


def remote_command(args: RemoteCommandArgs) -> None:
    """Send a remote control button press to a player.

    Simulates pressing a button on the physical SqueezeBox remote control.

    Supported buttons:
    - up: Move up in menu
    - down: Move down in menu
    - left: Move left in menu or go back
    - right: Move right in menu or go forward
    - select: Select current menu item (also called 'center' or 'ok')
    - browse: Enter music library browse mode

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    button = args.button

    # Map friendly button names to IR codes
    button_map = {
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
        "select": "center",  # Also known as "ok" or "enter"
        "browse": "browse",  # Browse music library
    }

    command_name = button_map[button]

    try:
        # Send the IR code to simulate the button press
        client.send_command(player_id, "button", [command_name])
        print(f"Sent '{button}' button press to player {player_id}")
    except Exception as e:
        print(f"Error sending button command: {e}", file=sys.stderr)
        sys.exit(1)


def display_command(args: DisplayCommandArgs) -> None:
    """Display a message on a player's screen.

    This sends a custom message to the player's display. The message can include
    line breaks using '\n' to split text across multiple lines on the display.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    message = args.message
    if not message:
        print("Error: Message is required", file=sys.stderr)
        sys.exit(1)

    # Handle line breaks - different players may have varying display capabilities
    lines = message.split("\\n")

    # Get optional duration
    duration = args.duration

    try:
        # Configure command parameters
        params = ["line1", lines[0]]

        # Add line2 if provided
        if len(lines) > 1:
            params.extend(["line2", lines[1]])

        # Add more lines if needed and supported by the player
        if len(lines) > 2:
            params.extend(["line3", lines[2]])

        if len(lines) > 3:
            params.extend(["line4", lines[3]])

        # Add duration if specified
        if duration:
            params.extend(["duration", str(duration)])

        # Send the display command
        client.send_command(player_id, "display", params)

        if duration:
            print(f"Displayed message on {player_id} for {duration} seconds")
        else:
            print(f"Displayed message on {player_id}")
    except Exception as e:
        print(f"Error displaying message: {e}", file=sys.stderr)
        sys.exit(1)


def seek_command(args: SeekCommandArgs) -> None:
    """Seek to a specific position in the current track.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client_with_error_handling(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    position = args.position

    # Parse time value which can be in seconds or MM:SS format
    try:
        # Match against different time formats
        match position.split(":"):
            case [seconds] if seconds.isdigit():
                # Simple seconds format
                total_seconds = int(seconds)
            case [minutes, seconds] if minutes.isdigit() and seconds.isdigit():
                # MM:SS format
                total_seconds = int(minutes) * 60 + int(seconds)
            case [hours, minutes, seconds] if all(
                part.isdigit() for part in [hours, minutes, seconds]
            ):
                # HH:MM:SS format
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            case _:
                raise ValueError("Invalid time format")
    except ValueError:
        print("Error: Position must be in seconds or MM:SS format", file=sys.stderr)
        sys.exit(1)

    try:
        # Use the seek_to_time method
        client.seek_to_time(player_id, total_seconds)

        print(f"Seeked to {format_time(total_seconds)} in the current track")
    except Exception as e:
        print(f"Error seeking to position: {e}", file=sys.stderr)
        sys.exit(1)
