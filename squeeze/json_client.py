"""
SqueezeBox client library for interacting with SqueezeBox server using JSON API.
"""

import http.client
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, NotRequired, Self, TypeAlias, TypedDict

from squeeze.constants import PlayerMode, PowerState, RepeatMode, ShuffleMode
from squeeze.exceptions import APIError, CommandError, ConnectionError, ParseError

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

        # Send the request with retry logic
        url = f"{self.server_url}{self.api_path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        last_error: Exception | None = None

        # Implement retry logic
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    response_data = response.read().decode("utf-8")

                    try:
                        result: JsonResponse = json.loads(response_data)
                    except json.JSONDecodeError as e:
                        # Don't retry JSON parsing errors
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
                                # Don't retry application-level errors
                                raise APIError(f"Server error: {message}", code)
                            case str() as error_str:
                                raise APIError(f"Server error: {error_str}")
                            case _:
                                raise APIError(f"Server error: {error_info}")

                    # Success - return result without retrying
                    return result

            except urllib.error.HTTPError as e:
                # Some HTTP errors should not be retried
                match e.code:
                    case 401 | 403:
                        raise APIError(f"Authentication error: HTTP {e.code}")
                    case 404:
                        raise APIError("API endpoint not found")
                    case 429:
                        # Rate limiting - add extra delay before retry
                        last_error = e
                        # Wait longer for rate limit errors
                        time.sleep(self.retry_delay * 2)
                        continue
                    case 500 | 502 | 503 | 504:
                        # Server errors are retryable
                        last_error = e
                    case _:
                        # Other HTTP errors
                        try:
                            response_body = e.read().decode("utf-8")
                            last_error = APIError(
                                f"HTTP error {e.code}: {response_body}"
                            )
                        except Exception:
                            last_error = APIError(f"HTTP error {e.code}")

            except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
                # Network errors are retryable
                last_error = e

            except Exception as e:
                # Other unexpected errors
                last_error = e

            # Only sleep if more retries coming
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        # If we've exhausted all retries, raise the appropriate error
        if isinstance(last_error, urllib.error.HTTPError):
            match last_error.code:
                case 500 | 502 | 503 | 504:
                    raise APIError(
                        f"Server error after {self.max_retries} attempts: HTTP {last_error.code}"
                    )
                case _:
                    raise APIError(
                        f"HTTP error {last_error.code} after {self.max_retries} attempts"
                    )

        elif isinstance(last_error, urllib.error.URLError):
            reason = (
                str(last_error.reason)
                if hasattr(last_error, "reason")
                else str(last_error)
            )
            raise ConnectionError(
                f"Failed to connect to server after {self.max_retries} attempts: {reason}"
            )

        elif isinstance(last_error, http.client.RemoteDisconnected):
            raise ConnectionError(
                f"Server closed connection after {self.max_retries} attempts. "
                "The server may be busy or behind a firewall."
            )

        elif isinstance(last_error, APIError):
            # Re-raise API errors with retry context
            raise APIError(f"{str(last_error)} (after {self.max_retries} attempts)")

        elif last_error:
            # Catch-all for any other unexpected errors
            raise ConnectionError(
                f"Unexpected error after {self.max_retries} attempts: {str(last_error)}"
            )

        else:
            # This should never happen, but just in case
            raise ConnectionError(
                f"Failed to connect to server after {self.max_retries} attempts"
            )

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

            # Volume
            if "volume" in result:
                status["volume"] = result.get("volume", 0)

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
            # Helper function to send with retry logic
            def send_with_retry(max_attempts: int = 2) -> JsonResponse:
                """Send volume command with automatic retry on transient errors."""
                last_error = None

                for attempt in range(max_attempts):
                    try:
                        result = self._send_request(
                            player_id, "mixer", "volume", str(volume)
                        )
                        return result
                    except (ConnectionError, http.client.RemoteDisconnected) as e:
                        # Only retry network errors
                        last_error = e
                        if attempt < max_attempts - 1:
                            import time

                            # Exponential backoff
                            time.sleep(self.retry_delay * (2**attempt))
                        else:
                            # On last attempt, convert to CommandError
                            raise CommandError(str(e), command=f"mixer volume {volume}")
                    except (APIError, ParseError) as e:
                        # Don't retry application errors
                        raise CommandError(str(e), command=f"mixer volume {volume}")
                    except Exception as e:
                        # Don't retry other exceptions
                        raise CommandError(str(e), command=f"mixer volume {volume}")

                # This should never be reached if max_attempts > 0
                if last_error:
                    raise CommandError(
                        str(last_error), command=f"mixer volume {volume}"
                    )

                # This is just to satisfy mypy - this line will never be reached
                # because we either return or raise an exception above
                raise CommandError(
                    "Failed to set volume", command=f"mixer volume {volume}"
                )

            # Send with automatic retry for transient errors
            send_with_retry()
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

        # Helper function to send with retry logic
        def send_with_retry(
            base_command: str, command_args: list[str], max_attempts: int = 2
        ) -> JsonResponse:
            """Send a command with automatic retry on transient errors."""
            last_error = None

            for attempt in range(max_attempts):
                try:
                    # Don't return None from functions with return type annotation
                    result = self._send_request(player_id, base_command, *command_args)
                    return result
                except (ConnectionError, http.client.RemoteDisconnected) as e:
                    # Only retry network errors
                    last_error = e
                    if attempt < max_attempts - 1:
                        import time

                        # Exponential backoff
                        time.sleep(self.retry_delay * (2**attempt))
                    else:
                        # On last attempt, convert to CommandError
                        raise CommandError(str(e), command=cmd_str)
                except (APIError, ParseError) as e:
                    # Don't retry application errors
                    raise CommandError(str(e), command=cmd_str)
                except Exception as e:
                    # Don't retry other exceptions
                    raise CommandError(str(e), command=cmd_str)

            # This should never be reached if max_attempts > 0
            if last_error:
                raise CommandError(str(last_error), command=cmd_str)

            # This is just to satisfy mypy - this line will never be reached
            # because we either return or raise an exception above
            raise CommandError("Failed to send command", command=cmd_str)

        # Send with automatic retry for transient errors
        try:
            send_with_retry(command, args)
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
