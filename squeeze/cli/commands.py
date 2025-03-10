"""
CLI commands for Squeeze.
"""

import json
import sys
from typing import Any

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
from squeeze.json_client import SqueezeJsonClient
from squeeze.ui import select_player

# Type alias for client type
ClientType = SqueezeJsonClient

# Type alias for command arguments
ArgsDict = dict[str, Any]


def status_command(args: ArgsDict) -> None:
    """Show status of a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    live_mode = args.get("live", False)

    try:
        client = create_client(server_url)
    except ConnectionError as e:
        print(f"Error connecting to server: {e}", file=sys.stderr)
        sys.exit(1)

    # Use the common get_player_id helper
    try:
        player_id = get_player_id(args, client)
        if not player_id:
            return
    except SqueezeError as e:
        print(f"Error getting player ID: {e}", file=sys.stderr)
        sys.exit(1)

    # For live mode, we need to handle interrupts gracefully
    if live_mode:
        try:
            print("Live status mode. Press Ctrl+C to exit.")
            print()
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

                    # Format and print status
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

                        # Show progress bar for position if both position and duration are available
                        if "position" in current_track and "duration" in current_track:
                            position = current_track["position"]
                            duration = current_track["duration"]
                            if (
                                position is not None
                                and duration is not None
                                and duration > 0
                            ):
                                progress = min(1.0, position / duration)
                                bar_width = 40
                                filled_width = int(bar_width * progress)
                                bar = "█" * filled_width + "░" * (
                                    bar_width - filled_width
                                )
                                percent = int(progress * 100)
                                print(f"  Progress: {bar} {percent}%")

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
            return
    else:
        # Single status display (not live mode)
        try:
            status = client.get_player_status(player_id)

            # Format and print status
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

                # Then print any remaining fields
                for key, value in current_track.items():
                    if key not in priority_fields:
                        print(f"  {key.capitalize()}: {value}")

        except (ConnectionError, APIError, ParseError, CommandError) as e:
            print(f"Error getting player status: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            sys.exit(1)


def format_time(seconds: int) -> str:
    """Format seconds as mm:ss or hh:mm:ss.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"


def players_command(args: ArgsDict) -> None:
    """List available players.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
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


def get_player_id(args: ArgsDict, client: ClientType) -> str | None:
    """Get player ID from arguments or interactive selection.

    Args:
        args: Command-line arguments
        client: SqueezeClient or SqueezeJsonClient instance

    Returns:
        Player ID or None if no selection was made
    """
    player_id = args.get("player_id")

    # Force interactive mode if --interactive is set
    force_interactive = args.get("interactive", False)

    # Disable interactive mode if --no-interactive is set
    disable_interactive = args.get("no_interactive", False)

    # Interactive selection is needed if:
    # 1. Player ID is not provided, or
    # 2. Interactive mode is explicitly forced
    if not player_id or force_interactive:
        players = client.get_players()
        if not players:
            print("No players found")
            return None

        # Use interactive selection unless explicitly disabled
        if not disable_interactive:
            print("DEBUG: About to run interactive selection", file=sys.stderr)
            player_id = select_player(players)
            if player_id:
                print(f"DEBUG: Selected player: {player_id}", file=sys.stderr)
            else:
                print("DEBUG: No player selected", file=sys.stderr)
        else:
            # Just list players if interactive mode is disabled
            print("Available players:")
            for player in players:
                print(f"  {player['id']}: {player['name']}")
            return None

    return player_id


def play_command(args: ArgsDict) -> None:
    """Send play command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "play")
        print(f"Play command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending play command: {e}", file=sys.stderr)
        sys.exit(1)


def pause_command(args: ArgsDict) -> None:
    """Send pause command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "pause")
        print(f"Pause command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending pause command: {e}", file=sys.stderr)
        sys.exit(1)


def stop_command(args: ArgsDict) -> None:
    """Send stop command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "stop")
        print(f"Stop command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending stop command: {e}", file=sys.stderr)
        sys.exit(1)


def volume_command(args: ArgsDict) -> None:
    """Set volume for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    volume = args.get("volume")
    if volume is None:
        print("Error: Volume is required", file=sys.stderr)
        sys.exit(1)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    # Validate volume (0-100)
    try:
        volume_int = int(volume)
        if volume_int < 0 or volume_int > 100:
            print("Error: Volume must be between 0 and 100", file=sys.stderr)
            sys.exit(1)
    except ValueError:
        print("Error: Volume must be a number", file=sys.stderr)
        sys.exit(1)

    debug = args.get("debug_command", False)

    try:
        client.send_command(player_id, "mixer", ["volume", volume], debug=debug)
        print(f"Volume set to {volume} for player {player_id}")
    except Exception as e:
        print(f"Error setting volume: {e}", file=sys.stderr)
        sys.exit(1)


def power_command(args: ArgsDict) -> None:
    """Set power state for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    state = args.get("state")
    if state not in ["on", "off"]:
        print("Error: State must be 'on' or 'off'", file=sys.stderr)
        sys.exit(1)

    # Convert to 1/0
    state_value = "1" if state == "on" else "0"

    try:
        client.send_command(player_id, "power", [state_value])
        print(f"Power set to {state} for player {player_id}")
    except Exception as e:
        print(f"Error setting power: {e}", file=sys.stderr)
        sys.exit(1)


def search_command(args: ArgsDict) -> None:
    """Search for music in the library.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    # Ensure we have a JSON client
    if not hasattr(client, "get_artists"):
        print("Error: Search requires JSON API support", file=sys.stderr)
        sys.exit(1)

    search_term = args.get("term")
    if not search_term:
        print("Error: Search term is required", file=sys.stderr)
        sys.exit(1)

    search_type = args.get("type", "all")

    try:
        if search_type in ["all", "artists"]:
            print("Artists matching:", search_term)
            # Check if the client has the get_artists method
            if hasattr(client, "get_artists"):
                # We know client is a JSON client if it has get_artists
                from squeeze.json_client import SqueezeJsonClient

                json_client = client
                if isinstance(json_client, SqueezeJsonClient):
                    artists = json_client.get_artists(search=search_term)
                    for artist in artists[:10]:  # Limit to 10 results
                        print(f"  {artist.get('artist')}")
                    if len(artists) > 10:
                        print(f"  ... and {len(artists) - 10} more")
            print()

        if search_type in ["all", "albums"]:
            print("Albums matching:", search_term)
            # Check if the client has the get_albums method
            if hasattr(client, "get_albums"):
                # We know client is a JSON client if it has get_albums
                from squeeze.json_client import SqueezeJsonClient

                json_client = client
                if isinstance(json_client, SqueezeJsonClient):
                    albums = json_client.get_albums(search=search_term)
                    for album in albums[:10]:  # Limit to 10 results
                        print(
                            f"  {album.get('album')} by {album.get('artist', 'Unknown')}"
                        )
                    if len(albums) > 10:
                        print(f"  ... and {len(albums) - 10} more")
            print()

        if search_type in ["all", "tracks"]:
            print("Tracks matching:", search_term)
            # Check if the client has the get_tracks method
            if hasattr(client, "get_tracks"):
                # We know client is a JSON client if it has get_tracks
                from squeeze.json_client import SqueezeJsonClient

                json_client = client
                if isinstance(json_client, SqueezeJsonClient):
                    tracks = json_client.get_tracks(search=search_term)
                    for track in tracks[:10]:  # Limit to 10 results
                        print(
                            f"  {track.get('title')} by {track.get('artist', 'Unknown')} on {track.get('album', 'Unknown')}"
                        )
                    if len(tracks) > 10:
                        print(f"  ... and {len(tracks) - 10} more")

    except Exception as e:
        print(f"Error searching: {e}", file=sys.stderr)
        sys.exit(1)


def config_command(args: ArgsDict) -> None:
    """Manage configuration.

    Args:
        args: Command-line arguments
    """
    config = load_config()

    # With no arguments, print current config
    if not args.get("set_server"):
        print(json.dumps(config, indent=2))
        return

    # Set server URL
    server_url = args.get("set_server")
    config.setdefault("server", {})["url"] = server_url

    save_config(config)
    print(f"Server URL set to {server_url}")


def server_command(args: ArgsDict) -> None:
    """Get server status information.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))

    # Always force JSON for server command - it requires JSON API
    try:
        client = create_client(server_url)
    except ConnectionError as e:
        print(f"Error connecting to server: {e}", file=sys.stderr)
        print("The 'server' command requires JSON API support.", file=sys.stderr)
        print(
            "Check your server URL or use --server to specify a different server.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Double-check we have a JSON client (should never fail with prefer_json=True)
    if not hasattr(client, "get_server_status"):
        print("Error: Server command requires JSON API support", file=sys.stderr)
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


def next_command(args: ArgsDict) -> None:
    """Send next track command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
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


def jump_command(args: ArgsDict) -> None:
    """Jump to a specific track in the playlist.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    track_index = args.get("index")
    if track_index is None:
        print("Error: Track index is required", file=sys.stderr)
        sys.exit(1)

    try:
        # Convert to integer
        track_index = int(track_index)
    except ValueError:
        print("Error: Track index must be a number", file=sys.stderr)
        sys.exit(1)

    try:
        # Use 'playlist jump' instead of 'playlist index' to immediately play the track
        client.send_command(player_id, "playlist", ["jump", str(track_index)])
        print(
            f"Jumped to and started playing track {track_index} for player {player_id}"
        )
    except Exception as e:
        print(f"Error jumping to track: {e}", file=sys.stderr)
        sys.exit(1)


def prev_command(args: ArgsDict) -> None:
    """Send previous track command to a player.

    Mimics the behavior of remote controls:
    - If current track position is > 5 seconds, go to the beginning of the current track
    - If current track position is <= 5 seconds, go to the previous track

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        # Get custom threshold from args or use default of 5 seconds
        threshold = args.get("threshold", 5)
        try:
            threshold = int(threshold)
        except (TypeError, ValueError):
            threshold = 5

        # First check the current track position
        status = client.get_player_status(player_id)
        position = 0

        # Extract position from status text (format like "2174 of 3562:")
        status_text = status.get("status", "")
        if isinstance(status_text, str) and "of" in status_text:
            # Try to extract the position from status text
            import re

            match = re.search(r"(\d+)\s+of\s+(\d+)", status_text)
            if match:
                try:
                    position = int(match.group(1))
                    # total is available but not used
                    _ = int(match.group(2))
                    # Convert to seconds if position is in time units (e.g., milliseconds)
                    # This is a heuristic - if position is very large (>1000), assume it's in milliseconds
                    if position > 1000:
                        position = position // 1000  # Convert to seconds
                except (ValueError, IndexError):
                    position = 0

        # If we're past the threshold, go to the beginning of the current track
        if position > threshold:
            try:
                # Use seek_to_time or direct time command
                if hasattr(client, "seek_to_time"):
                    client.seek_to_time(player_id, 0, debug=False)
                else:
                    # Simplified fallback - just use the 'time' command directly
                    client.send_command(player_id, "time", ["0"])
                print(f"Restarted current track for player {player_id}")
            except Exception as e:
                print(f"Error seeking to start of track: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Otherwise, go to the previous track
            client.send_command(player_id, "playlist", ["index", "-1"])
            print(f"Previous track command sent to player {player_id}")

    except Exception as e:
        print(f"Error sending previous track command: {e}", file=sys.stderr)
        sys.exit(1)


def now_playing_command(args: ArgsDict) -> None:
    """Show Now Playing screen on a player.

    This mimics pressing the Now Playing button on the official remote control,
    displaying the currently playing track in the server-configured format.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        # Use the new show_now_playing method for both client types
        client.show_now_playing(player_id, debug=args.get("debug_command", False))
        print(f"Now Playing screen activated for player {player_id}")
    except Exception as e:
        print(f"Error showing Now Playing screen: {e}", file=sys.stderr)
        sys.exit(1)


def shuffle_command(args: ArgsDict) -> None:
    """Set or cycle through shuffle modes.

    Supported modes:
    - off: No shuffling
    - songs: Shuffle songs
    - albums: Shuffle albums

    If no mode is specified, cycle through modes in the order: off -> songs -> albums -> off.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    mode = args.get("mode")

    # If no mode specified, we need to get current state to cycle
    if not mode:
        try:
            status = client.get_player_status(player_id)
            current_mode = status.get("shuffle", 0)

            # Cycle to next mode (0 -> 1 -> 2 -> 0)
            next_mode = (current_mode + 1) % 3
            mode_value = str(next_mode)

            # Get human-readable mode name for display
            mode_name = ShuffleMode.to_string(next_mode)
        except Exception as e:
            print(f"Error getting current shuffle mode: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Convert named mode to value
        mode_map = {
            "off": ShuffleMode.OFF,
            "songs": ShuffleMode.SONGS,
            "albums": ShuffleMode.ALBUMS,
        }

        if mode not in mode_map:
            print(
                f"Error: Invalid shuffle mode '{mode}'. Must be one of: off, songs, albums",
                file=sys.stderr,
            )
            sys.exit(1)

        mode_value = str(mode_map[mode])
        mode_name = ShuffleMode.to_string(mode_map[mode])

    try:
        client.send_command(player_id, "playlist", ["shuffle", mode_value])
        print(f"Shuffle mode set to '{mode_name}' for player {player_id}")
    except Exception as e:
        print(f"Error setting shuffle mode: {e}", file=sys.stderr)
        sys.exit(1)


def repeat_command(args: ArgsDict) -> None:
    """Set or cycle through repeat modes.

    Supported modes:
    - off: No repeat
    - one: Repeat current track
    - all: Repeat entire playlist

    If no mode is specified, cycle through modes in the order: off -> all -> one -> off.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    mode = args.get("mode")

    # If no mode specified, we need to get current state to cycle
    if not mode:
        try:
            status = client.get_player_status(player_id)
            current_mode = status.get("repeat", 0)

            # Define the cycle order: 0 (off) -> 2 (all) -> 1 (one) -> 0 (off)
            # This order matches how most music players cycle through repeat modes
            if current_mode == RepeatMode.OFF:
                next_mode = RepeatMode.ALL
            elif current_mode == RepeatMode.ALL:
                next_mode = RepeatMode.ONE
            else:  # RepeatMode.ONE
                next_mode = RepeatMode.OFF

            mode_value = str(next_mode)

            # Get human-readable mode name for display
            mode_name = RepeatMode.to_string(next_mode)
        except Exception as e:
            print(f"Error getting current repeat mode: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Convert named mode to value
        mode_map = {
            "off": RepeatMode.OFF,
            "one": RepeatMode.ONE,
            "all": RepeatMode.ALL,
        }

        if mode not in mode_map:
            print(
                f"Error: Invalid repeat mode '{mode}'. Must be one of: off, one, all",
                file=sys.stderr,
            )
            sys.exit(1)

        mode_value = str(mode_map[mode])
        mode_name = RepeatMode.to_string(mode_map[mode])

    try:
        client.send_command(player_id, "playlist", ["repeat", mode_value])
        print(f"Repeat mode set to '{mode_name}' for player {player_id}")
    except Exception as e:
        print(f"Error setting repeat mode: {e}", file=sys.stderr)
        sys.exit(1)


def remote_command(args: ArgsDict) -> None:
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
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    button = args.get("button")

    # Map friendly button names to IR codes
    button_map = {
        "up": "up",
        "down": "down",
        "left": "left",
        "right": "right",
        "select": "center",  # Also known as "ok" or "enter"
        "browse": "browse",  # Browse music library
    }

    if button not in button_map:
        print(
            f"Error: Unknown button '{button}'. Must be one of: {', '.join(button_map.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)

    command_name = button_map[button]

    try:
        # Send the IR code to simulate the button press
        client.send_command(player_id, "button", [command_name])
        print(f"Sent '{button}' button press to player {player_id}")
    except Exception as e:
        print(f"Error sending button command: {e}", file=sys.stderr)
        sys.exit(1)


def display_command(args: ArgsDict) -> None:
    """Display a message on a player's screen.

    This sends a custom message to the player's display. The message can include
    line breaks using '\n' to split text across multiple lines on the display.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    message = args.get("message")
    if not message:
        print("Error: Message is required", file=sys.stderr)
        sys.exit(1)

    # Handle line breaks - different players may have varying display capabilities
    lines = message.split("\\n")

    # Get optional duration
    duration = args.get("duration")
    if duration:
        try:
            duration = int(duration)
        except ValueError:
            print("Error: Duration must be a number (seconds)", file=sys.stderr)
            sys.exit(1)

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


def seek_command(args: ArgsDict) -> None:
    """Seek to a specific position in the current track.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    position = args.get("position")
    if position is None:
        print("Error: Position is required", file=sys.stderr)
        sys.exit(1)

    # Parse time value which can be in seconds or MM:SS format
    try:
        if ":" in position:
            # Parse MM:SS or HH:MM:SS format
            parts = position.split(":")
            if len(parts) == 2:
                # MM:SS format
                minutes, seconds = parts
                total_seconds = int(minutes) * 60 + int(seconds)
            elif len(parts) == 3:
                # HH:MM:SS format
                hours, minutes, seconds = parts
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            else:
                raise ValueError("Invalid time format")
        else:
            # Simple seconds format
            total_seconds = int(position)
    except ValueError:
        print("Error: Position must be in seconds or MM:SS format", file=sys.stderr)
        sys.exit(1)

    try:
        # Use the seek_to_time method from the JSON client
        if hasattr(client, "seek_to_time"):
            client.seek_to_time(
                player_id, total_seconds, debug=args.get("debug_command", False)
            )
        else:
            # Fallback for clients that don't have seek_to_time
            client.send_command(player_id, "time", [str(total_seconds)])

        print(f"Seeked to {format_time(total_seconds)} in the current track")
    except Exception as e:
        print(f"Error seeking to position: {e}", file=sys.stderr)
        sys.exit(1)
