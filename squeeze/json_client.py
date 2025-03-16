"""
SqueezeBox client library for interacting with SqueezeBox server using JSON API.
"""

import http.client
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, NotRequired, Self, TypeAlias, TypedDict

from squeeze.constants import PlayerMode, PowerState, RepeatMode, ShuffleMode
from squeeze.exceptions import (
    APIError,
    CommandError,
    ConnectionError,
    ParseError,
    PlayerNotFoundError,
)
from squeeze.retry import retry_operation

# Track information dictionary
TrackDict: TypeAlias = dict[str, Any]


# TypedDict for player status
class PlayerStatus(TypedDict):
    """Type definition for player status information."""

    player_id: str
    player_name: str
    power: str  # PowerState value
    status: str
    mode: str  # PlayerMode value
    volume: int
    shuffle: int
    repeat: int
    current_track: TrackDict
    playlist_count: int
    playlist_position: int
    shuffle_mode: NotRequired[str]
    repeat_mode: NotRequired[str]
    playlist: NotRequired[list[dict[str, Any]]]


# TypedDict for JSON response
class JsonResponse(TypedDict):
    """Type definition for JSON-RPC response."""

    id: int
    result: dict[str, Any]
    error: NotRequired[dict[str, Any] | str]


# Standard status fields that should be returned by get_player_status
DEFAULT_STATUS: PlayerStatus = {
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


@dataclass
class SqueezeJsonClient:
    """Client for interacting with SqueezeBox server using JSON API."""

    server_url: str
    api_path: str = field(default="/jsonrpc.js")
    next_id: int = field(default=1)
    max_retries: int = field(default=2)
    retry_delay: float = field(default=1.0)

    def __post_init__(self) -> None:
        """Initialize after instance creation."""
        self.server_url = self.server_url.rstrip("/")
        if not self.api_path.startswith("/"):
            self.api_path = f"/{self.api_path}"

    @classmethod
    def create(
        cls,
        server_url: str,
        api_path: str = "/jsonrpc.js",
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> Self:
        """Factory method to create a client instance.

        Args:
            server_url: URL of the SqueezeBox server
            api_path: Path to the JSON API endpoint
            max_retries: Maximum number of request retries for transient errors
            retry_delay: Delay between retries in seconds

        Returns:
            A new client instance
        """
        return cls(
            server_url.rstrip("/"),
            api_path=api_path,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    def _send_request(
        self, player_id: str | None, command: str, *args: Any
    ) -> JsonResponse:
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

        # Set up the request
        url = f"{self.server_url}{self.api_path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        # Define function to execute with retry logic
        def execute_request() -> JsonResponse:
            """Execute the HTTP request with error handling."""
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    response_data = response.read().decode("utf-8")

                    try:
                        result: JsonResponse = json.loads(response_data)
                    except json.JSONDecodeError as e:
                        raise ParseError(f"Failed to parse JSON response: {e}")

                    # Check for error in response using pattern matching
                    if "error" in result:
                        error_info = result["error"]
                        match error_info:
                            # For Python 3.11+, we could use structural pattern matching with attribute patterns
                            # but for better mypy compatibility, we'll use the traditional approach
                            case dict() as error_dict:
                                code = error_dict.get("code", 0)
                                message = error_dict.get("message", "Unknown error")
                                if "player not found" in message.lower():
                                    raise PlayerNotFoundError(player_id or "")
                                # Don't retry application-level errors
                                raise APIError(f"Server error: {message}", code)
                            case str() as error_str:
                                raise APIError(f"Server error: {error_str}")
                            case _:
                                raise APIError(f"Server error: {error_info}")

                    # Success - return the result
                    return result

            except urllib.error.HTTPError as e:
                # Some HTTP errors should not be retried
                match e.code:
                    case 401 | 403:
                        raise APIError(f"Authentication error: HTTP {e.code}")
                    case 404:
                        raise APIError("API endpoint not found")
                    case 429:
                        # Rate limiting error - we'll retry with a longer delay
                        # We're raising a custom error that will be caught and retried
                        # with the backoff factor
                        raise ConnectionError(f"Rate limit exceeded: HTTP {e.code}")
                    case 500 | 502 | 503 | 504:
                        # Server errors are retryable
                        raise ConnectionError(f"Server error: HTTP {e.code}")
                    case _:
                        # Other HTTP errors
                        try:
                            response_body = e.read().decode("utf-8")
                            raise APIError(f"HTTP error {e.code}: {response_body}")
                        except Exception:
                            raise APIError(f"HTTP error {e.code}")

        # Execute the request with retry logic
        try:
            return retry_operation(
                execute_request,
                max_tries=self.max_retries,
                retry_delay=self.retry_delay,
                backoff_factor=2.0,
                retry_exceptions=(
                    urllib.error.URLError,
                    ConnectionError,
                    http.client.RemoteDisconnected,
                ),
                no_retry_exceptions=(APIError, ParseError, PlayerNotFoundError),
            )
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", str(e))
            raise ConnectionError(f"Failed to connect to server: {reason}")
        except http.client.RemoteDisconnected:
            raise ConnectionError(
                "Server closed connection. The server may be busy or behind a firewall."
            )
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
    ) -> PlayerStatus:
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
            # Include important metadata tags:
            # a=artist, b=?, c=coverid, d=duration, e=album_id, i=disc, j=coverart, l=album,
            # m=bpm, N=remote_title, o=type, r=bitrate, t=tracknum, u=url, K=artwork_url,
            # R=rating, Y=replay_gain
            params = [
                "-",
                1,
                "tags:abcdeilmNortuKRYj",
            ]  # Extended tag set for more info

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

            # Volume - ensure it's properly converted to an integer
            if "volume" in result:
                try:
                    # WiiM players may report volume in a different format or range
                    # Make sure we always get a number between 0-100
                    vol_value = result.get("volume", 0)
                    # First convert to integer or float if needed
                    if isinstance(vol_value, str):
                        vol_value = float(vol_value)
                    # Then ensure it's in the 0-100 range
                    status["volume"] = max(0, min(100, int(vol_value)))
                except (ValueError, TypeError):
                    # Fallback to default if conversion fails
                    status["volume"] = 0

            # Current mode
            mode = result.get("mode", PlayerMode.STOP)
            status["mode"] = mode
            status["status"] = PlayerMode.to_string(mode)

            # Playlist info
            if "playlist_loop" in result:
                status["playlist_count"] = int(result.get("playlist_tracks", 0))
                # Ensure playlist_position is always an integer
                try:
                    status["playlist_position"] = int(
                        result.get("playlist_cur_index", 0)
                    )
                except (ValueError, TypeError):
                    status["playlist_position"] = 0

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
            current_track: TrackDict = {}

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
                        # Store other track fields directly
                        current_track[key] = value

                # Add track position if available
                if "time" in result:
                    current_track["position"] = result["time"]

            status["current_track"] = current_track

            # Include the raw playlist data if available
            if "playlist_loop" in result:
                status["playlist"] = result["playlist_loop"]

            # Return the status dictionary
            return status

        except (ConnectionError, APIError, ParseError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to APIError
            raise APIError(f"Failed to get player status: {str(e)}")

    def set_volume(self, player_id: str, volume: int) -> None:
        """Set volume for a player.

        Args:
            player_id: ID of the player to set volume for
            volume: Volume level (0-100)

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        # Ensure volume is in valid range
        volume = max(0, min(100, volume))

        # Use the send_command method which now has built-in retry logic
        # Note: We're bypassing the send_command special case for volume by using _send_request directly
        try:
            # Define function to set volume with automatic retry
            def set_volume_request() -> JsonResponse:
                return self._send_request(player_id, "mixer", "volume", str(volume))

            # Send with automatic retry for transient errors
            try:
                retry_operation(
                    set_volume_request,
                    max_tries=2,
                    retry_delay=self.retry_delay,
                    backoff_factor=2.0,
                    retry_exceptions=(ConnectionError, http.client.RemoteDisconnected),
                    no_retry_exceptions=(APIError, ParseError),
                )
            except Exception as e:
                # Convert any exceptions to CommandError
                raise CommandError(str(e), command=f"mixer volume {volume}")
        except CommandError:
            # Just re-raise command errors
            raise
        except Exception as e:
            # Convert any other exceptions to CommandError
            raise CommandError(str(e), command=f"mixer volume {volume}")

    def seek_to_time(self, player_id: str, seconds: int) -> None:
        """Seek to a specific time in the current track.

        Args:
            player_id: ID of the player
            seconds: Time position in seconds

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        # Use the send_command method which now has built-in retry logic
        self.send_command(player_id, "time", [str(seconds)])

    def show_now_playing(self, player_id: str) -> None:
        """Show the Now Playing screen on the player.

        This mimics pressing the Now Playing button on the remote control,
        displaying the currently playing track in the server-configured format.

        Args:
            player_id: ID of the player

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        # Use the send_command method which now has built-in retry logic
        self.send_command(player_id, "display")

    def send_command(
        self,
        player_id: str,
        command: str,
        params: list[str] | None = None,
    ) -> None:
        """Send a command to a player.

        Args:
            player_id: ID of the player to send command to
            command: Command to send
            params: Optional parameters for the command

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            CommandError: If the command fails to execute
        """
        param_str = " ".join(params) if params else ""
        cmd_str = f"{command} {param_str}".strip()

        # Special handling for common commands
        if command == "mixer" and params and params[0] == "volume" and len(params) > 1:
            try:
                volume = int(params[1])
                self.set_volume(player_id, volume)
                return
            except (ValueError, IndexError) as e:
                raise CommandError(f"Invalid volume parameter: {e}", command=cmd_str)
            except CommandError:
                # Re-raise command errors from set_volume
                raise

        # Convert params to positional args for _send_request
        args = params if params else []

        # Helper function to send a command with automatic retry
        def send_command_request() -> JsonResponse:
            return self._send_request(player_id, command, *args)

        # Send with automatic retry for transient errors
        try:
            retry_operation(
                send_command_request,
                max_tries=2,
                retry_delay=self.retry_delay,
                backoff_factor=2.0,
                retry_exceptions=(ConnectionError, http.client.RemoteDisconnected),
                no_retry_exceptions=(APIError, ParseError, PlayerNotFoundError),
            )
        except (ConnectionError, APIError, ParseError, PlayerNotFoundError) as e:
            # Convert to CommandError
            raise CommandError(str(e), command=cmd_str)
        except CommandError:
            # Just re-raise command errors
            raise
        except Exception as e:
            # Convert any other exceptions to CommandError
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
