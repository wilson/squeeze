"""
CLI commands for Squeeze.
"""

import json
import sys

from squeeze.client_factory import create_client
from squeeze.config import get_server_url, load_config, save_config
from squeeze.exceptions import (
    APIError,
    CommandError,
    ConnectionError,
    ParseError,
    SqueezeError,
)
from squeeze.html_client import SqueezeHtmlClient
from squeeze.json_client import SqueezeJsonClient
from squeeze.ui import select_player

# Type alias for either client type
ClientType = SqueezeHtmlClient | SqueezeJsonClient


def status_command(args: dict) -> None:
    """Show status of a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)

    try:
        client = create_client(server_url, prefer_json=use_json)
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


def players_command(args: dict) -> None:
    """List available players.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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


def get_player_id(args: dict, client: ClientType) -> str | None:
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


def play_command(args: dict) -> None:
    """Send play command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "play")
        print(f"Play command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending play command: {e}", file=sys.stderr)
        sys.exit(1)


def pause_command(args: dict) -> None:
    """Send pause command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "pause")
        print(f"Pause command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending pause command: {e}", file=sys.stderr)
        sys.exit(1)


def stop_command(args: dict) -> None:
    """Send stop command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "stop")
        print(f"Stop command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending stop command: {e}", file=sys.stderr)
        sys.exit(1)


def volume_command(args: dict) -> None:
    """Set volume for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

    volume = args.get("volume")
    if volume is None:
        print("Error: Volume is required", file=sys.stderr)
        sys.exit(1)

    # Debug mode can be used without a player ID
    if args.get("debug") and args.get("player_id"):
        player_id_arg = args.get("player_id")
        if isinstance(player_id_arg, str) and isinstance(client, SqueezeHtmlClient):
            client.debug_volume_controls(player_id_arg)
            return
        elif isinstance(player_id_arg, str):
            print(
                "Debug volume controls only available for HTML client", file=sys.stderr
            )
            return

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    # Debug mode requires player ID
    if args.get("debug"):
        if isinstance(client, SqueezeHtmlClient):
            client.debug_volume_controls(player_id)
        else:
            print(
                "Debug volume controls only available for HTML client", file=sys.stderr
            )
        return

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


def power_command(args: dict) -> None:
    """Set power state for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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


def search_command(args: dict) -> None:
    """Search for music in the library.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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
            artists = client.get_artists(search=search_term)  # type: ignore
            for artist in artists[:10]:  # Limit to 10 results
                print(f"  {artist.get('artist')}")
            if len(artists) > 10:
                print(f"  ... and {len(artists) - 10} more")
            print()

        if search_type in ["all", "albums"]:
            print("Albums matching:", search_term)
            albums = client.get_albums(search=search_term)  # type: ignore
            for album in albums[:10]:  # Limit to 10 results
                print(f"  {album.get('album')} by {album.get('artist', 'Unknown')}")
            if len(albums) > 10:
                print(f"  ... and {len(albums) - 10} more")
            print()

        if search_type in ["all", "tracks"]:
            print("Tracks matching:", search_term)
            tracks = client.get_tracks(search=search_term)  # type: ignore
            for track in tracks[:10]:  # Limit to 10 results
                print(
                    f"  {track.get('title')} by {track.get('artist', 'Unknown')} on {track.get('album', 'Unknown')}"
                )
            if len(tracks) > 10:
                print(f"  ... and {len(tracks) - 10} more")

    except Exception as e:
        print(f"Error searching: {e}", file=sys.stderr)
        sys.exit(1)


def config_command(args: dict) -> None:
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


def server_command(args: dict) -> None:
    """Get server status information.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))

    # Always force JSON for server command - it requires JSON API
    try:
        client = create_client(server_url, prefer_json=True)
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
        status = client.get_server_status()  # type: ignore

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


def next_command(args: dict) -> None:
    """Send next track command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        client.send_command(player_id, "playlist", ["index", "+1"])
        print(f"Next track command sent to player {player_id}")
    except Exception as e:
        print(f"Error sending next track command: {e}", file=sys.stderr)
        sys.exit(1)


def jump_command(args: dict) -> None:
    """Jump to a specific track in the playlist.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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
        client.send_command(player_id, "playlist", ["index", str(track_index)])
        print(f"Jumped to track {track_index} for player {player_id}")
    except Exception as e:
        print(f"Error jumping to track: {e}", file=sys.stderr)
        sys.exit(1)


def prev_command(args: dict) -> None:
    """Send previous track command to a player.

    Mimics the behavior of remote controls:
    - If current track position is > 5 seconds, go to the beginning of the current track
    - If current track position is <= 5 seconds, go to the previous track

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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
                # Use the new seek_to_time method for both client types
                client.seek_to_time(player_id, 0, debug=False)
                print(f"Restarted current track for player {player_id}")
            except Exception as e:
                print(f"Error seeking to start of track: {e}", file=sys.stderr)
                # Fallback to previous method
                try:
                    client.send_command(player_id, "time", ["0"])
                    print(f"Restarted current track for player {player_id}")
                except Exception:
                    print("Failed to restart track", file=sys.stderr)
        else:
            # Otherwise, go to the previous track
            client.send_command(player_id, "playlist", ["index", "-1"])
            print(f"Previous track command sent to player {player_id}")

    except Exception as e:
        print(f"Error sending previous track command: {e}", file=sys.stderr)
        sys.exit(1)


def now_playing_command(args: dict) -> None:
    """Show Now Playing screen on a player.

    This mimics pressing the Now Playing button on the official remote control,
    displaying the currently playing track in the server-configured format.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.get("server"))
    use_json = args.get("json", True)
    client = create_client(server_url, prefer_json=use_json)

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
