"""
SqueezeBox client library for interacting with SqueezeBox server using JSON API.
"""

import json
import urllib.parse
import urllib.request
from typing import Any

from squeeze.constants import PlayerMode, PowerState, RepeatMode, ShuffleMode
from squeeze.exceptions import APIError, CommandError, ConnectionError, ParseError

# Type alias for JSON response
JsonDict = dict[str, Any]

# Standard status fields that should be returned by get_player_status
DEFAULT_STATUS = {
    "player_id": "",
    "player_name": "Unknown",
    "power": PowerState.OFF,
    "status": PlayerMode.to_string(PlayerMode.STOP),
    "mode": PlayerMode.STOP,
    "volume": 0,
    "shuffle": ShuffleMode.OFF,
    "repeat": RepeatMode.OFF,
    "current_track": {},
    "playlist_count": 0,
    "playlist_position": 0,
}


class SqueezeJsonClient:
    """Client for interacting with SqueezeBox server using JSON API."""

    def __init__(self, server_url: str):
        """Initialize the SqueezeBox client.

        Args:
            server_url: URL of the SqueezeBox server
        """
        self.server_url = server_url.rstrip("/")
        self.next_id = 1  # Counter for JSON-RPC request IDs

    def _send_request(
        self, player_id: str | None, command: str, *args: Any
    ) -> JsonDict:
        """Send a JSON-RPC request to the server.

        Args:
            player_id: Player ID or None for server commands
            command: Command to send
            *args: Additional command arguments

        Returns:
            JSON response as dictionary

        Raises:
            ConnectionError: If unable to connect to the server
            APIError: If the server returns an error response
            ParseError: If the response is not valid JSON
        """
        # Prepare the JSON-RPC request
        request_id = self.next_id
        self.next_id += 1

        # Construct the params array with command and args
        cmd_params = [command]
        cmd_params.extend(args)

        # Create the full request
        request = {
            "id": request_id,
            "method": "slim.request",
            "params": [player_id if player_id else "", cmd_params],
        }

        # Encode the request as JSON
        try:
            data = json.dumps(request).encode("utf-8")
        except (TypeError, ValueError) as e:
            raise ParseError(f"Failed to encode request: {e}")

        # Send the request
        url = f"{self.server_url}/jsonrpc.js"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")

                try:
                    result: dict[str, Any] = json.loads(response_data)
                except json.JSONDecodeError as e:
                    raise ParseError(f"Failed to parse JSON response: {e}")

                # Check for error in response
                if "error" in result:
                    error_info = result["error"]
                    if isinstance(error_info, dict):
                        code = error_info.get("code", 0)
                        message = error_info.get("message", "Unknown error")
                        raise APIError(f"Server error: {message}", code)
                    else:
                        raise APIError(f"Server error: {error_info}")

                return result

        except urllib.error.HTTPError as e:
            try:
                response_body = e.read().decode("utf-8")
                raise APIError(f"HTTP error {e.code}: {response_body}")
            except Exception:
                raise APIError(f"HTTP error {e.code}")

        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, "reason") else str(e)
            raise ConnectionError(f"Failed to connect to server: {reason}")

        except Exception as e:
            # Catch-all for any other unexpected errors
            raise ConnectionError(f"Unexpected error: {str(e)}")

    def get_players(self) -> list[dict[str, str]]:
        """Get list of available players.

        Returns:
            List of player information dictionaries with 'id' and 'name' keys

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        try:
            # Use the 'players' command to get all connected players
            response = self._send_request(None, "players", 0, 100)

            if "result" not in response:
                raise ParseError("Invalid response from server: missing 'result' field")

            if "players_loop" not in response["result"]:
                # No players found or invalid response format
                return []

            # Extract player information
            players = []
            for player in response["result"]["players_loop"]:
                player_info = {
                    "id": player.get("playerid", ""),
                    "name": player.get("name", "Unknown Player"),
                }
                # Optional additional info
                if "ip" in player:
                    player_info["ip"] = player["ip"]
                if "model" in player:
                    player_info["model"] = player["model"]
                if "connected" in player:
                    player_info["connected"] = str(player["connected"])
                if "canpoweroff" in player:
                    player_info["can_power_off"] = str(player["canpoweroff"])

                players.append(player_info)

            return players

        except (ConnectionError, APIError, ParseError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to APIError
            raise APIError(f"Failed to get players: {str(e)}")

    def get_player_status(
        self, player_id: str, subscribe: bool = False
    ) -> dict[str, Any]:
        """Get detailed status for a specific player.

        Args:
            player_id: ID of the player to get status for
            subscribe: Whether to subscribe to status updates

        Returns:
            Dictionary containing player status information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        try:
            # Build parameters for the status command
            params = ["-", 1, "tags:abcdeilNortuK"]  # Extended tag set for more info

            # Add subscribe parameter if requested
            if subscribe:
                params.append("subscribe:1")
            else:
                params.append("subscribe:0")

            # Use the 'status' command to get player status
            response = self._send_request(player_id, "status", *params)

            if "result" not in response:
                raise ParseError("Invalid response from server: missing 'result' field")

            result = response["result"]

            # Start with default status, then fill in actual values
            status = DEFAULT_STATUS.copy()
            status["player_id"] = player_id

            # Basic player info
            if "player_name" in result:
                status["player_name"] = result["player_name"]

            # Power state
            if "power" in result:
                status["power"] = PowerState.from_int(result.get("power", 0))

            # Volume
            if "volume" in result:
                status["volume"] = result.get("volume", 0)

            # Current mode
            mode = result.get("mode", PlayerMode.STOP)
            status["mode"] = mode
            status["status"] = PlayerMode.to_string(mode)

            # Playlist info
            if "playlist_loop" in result:
                status["playlist_count"] = result.get("playlist_tracks", 0)
                status["playlist_position"] = result.get("playlist_cur_index", 0)

            # Shuffle and repeat mode
            if "playlist_shuffle" in result:
                status["shuffle"] = result["playlist_shuffle"]
                status["shuffle_mode"] = ShuffleMode.to_string(
                    result["playlist_shuffle"]
                )

            if "playlist_repeat" in result:
                status["repeat"] = result["playlist_repeat"]
                status["repeat_mode"] = RepeatMode.to_string(result["playlist_repeat"])

            # Current track info
            current_track = {}
            if "playlist_loop" in result and result["playlist_loop"]:
                track = result["playlist_loop"][0]
                # Copy all available track info
                for key, value in track.items():
                    # Convert some keys to more user-friendly names
                    if key == "title":
                        current_track["title"] = value
                    elif key == "artist":
                        current_track["artist"] = value
                    elif key == "album":
                        current_track["album"] = value
                    elif key == "duration":
                        current_track["duration"] = value
                    elif key == "artwork_url":
                        current_track["artwork"] = value
                    else:
                        current_track[key] = value

                # Add track position if available
                if "time" in result:
                    current_track["position"] = result["time"]

            status["current_track"] = current_track

            # Include the raw playlist data if available
            if "playlist_loop" in result:
                status["playlist"] = result["playlist_loop"]

            return status

        except (ConnectionError, APIError, ParseError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to APIError
            raise APIError(f"Failed to get player status: {str(e)}")

    def set_volume(self, player_id: str, volume: int, debug: bool = False) -> None:
        """Set volume for a player.

        Args:
            player_id: ID of the player to set volume for
            volume: Volume level (0-100)
            debug: Optional flag to print debugging information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        # Ensure volume is in valid range
        volume = max(0, min(100, volume))

        if debug:
            print(f"Debug: Setting volume to {volume} for player {player_id}")

        try:
            self._send_request(player_id, "mixer", "volume", str(volume))
        except (ConnectionError, APIError, ParseError) as e:
            # Re-raise with more context
            raise CommandError(str(e), command=f"mixer volume {volume}")
        except Exception as e:
            # Convert generic exceptions to CommandError
            raise CommandError(str(e), command=f"mixer volume {volume}")

    def seek_to_time(self, player_id: str, seconds: int, debug: bool = False) -> None:
        """Seek to a specific time in the current track.

        Args:
            player_id: ID of the player
            seconds: Time position in seconds
            debug: Optional flag to print debugging information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        if debug:
            print(f"Debug: Seeking to {seconds} seconds for player {player_id}")

        try:
            # According to the API reference, 'time' is the command to seek within a track
            # Simply send the time command with the seconds value
            self._send_request(player_id, "time", str(seconds))
        except (ConnectionError, APIError, ParseError) as e:
            # Re-raise with more context
            raise CommandError(str(e), command=f"seek to {seconds}")
        except Exception as e:
            # Convert generic exceptions to CommandError
            raise CommandError(str(e), command=f"seek to {seconds}")

    def show_now_playing(self, player_id: str, debug: bool = False) -> None:
        """Show the Now Playing screen on the player.

        This mimics pressing the Now Playing button on the remote control,
        displaying the currently playing track in the server-configured format.

        Args:
            player_id: ID of the player
            debug: Optional flag to print debugging information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        if debug:
            print(f"Debug: Showing Now Playing screen for player {player_id}")

        try:
            self._send_request(player_id, "display")
        except (ConnectionError, APIError, ParseError) as e:
            # Re-raise with more context
            raise CommandError(str(e), command="display")
        except Exception as e:
            # Convert generic exceptions to CommandError
            raise CommandError(str(e), command="display")

    def send_command(
        self,
        player_id: str,
        command: str,
        params: list[str] | None = None,
        debug: bool = False,
    ) -> None:
        """Send a command to a player.

        Args:
            player_id: ID of the player to send command to
            command: Command to send
            params: Optional parameters for the command
            debug: Optional flag to print debugging information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        param_str = " ".join(params) if params else ""
        cmd_str = f"{command} {param_str}".strip()

        if debug:
            print(f"Debug: Sending command {cmd_str} to player {player_id}")

        # Special handling for common commands
        if command == "mixer" and params and params[0] == "volume" and len(params) > 1:
            try:
                volume = int(params[1])
                self.set_volume(player_id, volume, debug)
                return
            except (ValueError, IndexError) as e:
                raise CommandError(f"Invalid volume parameter: {e}", command=cmd_str)
            except CommandError:
                # Re-raise command errors from set_volume
                raise

        # Convert params to positional args for _send_request
        args = params if params else []
        try:
            self._send_request(player_id, command, *args)
        except (ConnectionError, APIError, ParseError) as e:
            # Re-raise with more context
            raise CommandError(str(e), command=cmd_str)
        except Exception as e:
            # Convert generic exceptions to CommandError
            raise CommandError(str(e), command=cmd_str)

    def get_server_status(self) -> dict[str, Any]:
        """Get server status.

        Returns:
            Dictionary containing server status information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        try:
            response = self._send_request(None, "serverstatus", 0, 100)

            if "result" not in response:
                raise ParseError("Invalid response from server: missing 'result' field")

            result: dict[str, Any] = response["result"]

            # Add some derived fields for convenience
            if "players_loop" in result:
                result["player_count"] = len(result["players_loop"])

            # Add total counts if available
            if "info" in result:
                info = result["info"]
                for key, value in info.items():
                    if key.startswith("total_"):
                        result[key] = value

            return result

        except (ConnectionError, APIError, ParseError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to APIError
            raise APIError(f"Failed to get server status: {str(e)}")

    def get_library_info(
        self, command: str, start: int = 0, count: int = 100, **kwargs: str
    ) -> list[dict[str, Any]]:
        """Get library information (artists, albums, tracks, etc).

        Args:
            command: Library command (artists, albums, tracks, etc)
            start: Starting index
            count: Number of items to return
            **kwargs: Additional parameters for the command

        Returns:
            List of items

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        try:
            # Convert kwargs to command arguments
            args = [str(start), str(count)]
            for key, value in kwargs.items():
                args.append(f"{key}:{value}")

            response = self._send_request(None, command, *args)

            if "result" not in response:
                raise ParseError("Invalid response from server: missing 'result' field")

            # Most library commands return a loop with the command name plus "_loop"
            # e.g., "artists" returns "artists_loop"
            loop_key = f"{command}_loop"
            if loop_key in response["result"]:
                result: list[dict[str, Any]] = response["result"][loop_key]
                return result

            # No results found
            return []

        except (ConnectionError, APIError, ParseError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to APIError
            raise APIError(f"Failed to get {command}: {str(e)}")

    def get_artists(
        self, start: int = 0, count: int = 100, search: str | None = None
    ) -> list[dict[str, Any]]:
        """Get list of artists.

        Args:
            start: Starting index
            count: Number of items to return
            search: Optional search term

        Returns:
            List of artists

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        kwargs = {}
        if search:
            kwargs["search"] = search

        return self.get_library_info("artists", start, count, **kwargs)

    def get_albums(
        self,
        start: int = 0,
        count: int = 100,
        artist_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of albums.

        Args:
            start: Starting index
            count: Number of items to return
            artist_id: Optional artist ID to filter by
            search: Optional search term

        Returns:
            List of albums

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        kwargs = {}
        if artist_id:
            kwargs["artist_id"] = artist_id
        if search:
            kwargs["search"] = search

        return self.get_library_info("albums", start, count, **kwargs)

    def get_tracks(
        self,
        start: int = 0,
        count: int = 100,
        album_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of tracks.

        Args:
            start: Starting index
            count: Number of items to return
            album_id: Optional album ID to filter by
            search: Optional search term

        Returns:
            List of tracks

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        kwargs = {}
        if album_id:
            kwargs["album_id"] = album_id
        if search:
            kwargs["search"] = search

        return self.get_library_info("tracks", start, count, **kwargs)
