"""
SqueezeBox client library for interacting with SqueezeBox server using HTML API.
"""

import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from squeeze.constants import PlayerMode, PowerState, RepeatMode, ShuffleMode
from squeeze.exceptions import APIError, CommandError, ConnectionError, ParseError

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


class PlayerOptionParser(HTMLParser):
    """Parser for extracting player options from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.players: list[dict[str, str]] = []
        self.in_select = False
        self.current_option: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "select" and any(
            attr[0] == "name" and attr[1] == "player" for attr in attrs
        ):
            self.in_select = True
        elif self.in_select and tag == "option":
            self.current_option = {}
            for attr in attrs:
                if attr[0] == "value" and attr[1] is not None:
                    self.current_option["id"] = attr[1]

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.in_select = False
        elif (
            self.in_select
            and tag == "option"
            and "id" in self.current_option
            and "name" in self.current_option
        ):
            self.players.append(self.current_option)
            self.current_option = {}

    def handle_data(self, data: str) -> None:
        if self.in_select and self.current_option and "id" in self.current_option:
            self.current_option["name"] = data.strip()


class SqueezeHtmlClient:
    """Client for interacting with SqueezeBox server using HTML API."""

    def __init__(self, server_url: str):
        """Initialize the SqueezeBox HTML client.

        Args:
            server_url: URL of the SqueezeBox server
        """
        self.server_url = server_url.rstrip("/")

    def get_html(
        self, path: str, player_id: str | None = None, debug: bool = False
    ) -> bytes:
        """Get HTML content from the server.

        Args:
            path: Path to request
            player_id: Optional player ID to filter by
            debug: Optional flag to print the URL for debugging

        Returns:
            HTML content as bytes

        Raises:
            ConnectionError: If unable to connect to the server
            APIError: If the server returns an error response
        """
        url = f"{self.server_url}/{path}"
        if player_id:
            url = f"{url}?player={player_id}"

        if debug:
            print(f"Debug: Requesting URL: {url}")

        try:
            with urllib.request.urlopen(url) as response:
                result: bytes = response.read()
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
            html_content = self.get_html("status.html")

            # Use our HTML parser to extract player options
            parser = PlayerOptionParser()
            parser.feed(html_content.decode("utf-8", errors="replace"))

            return parser.players

        except (ConnectionError, APIError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to ParseError
            raise ParseError(f"Failed to parse player list: {str(e)}")

    def get_player_status(self, player_id: str) -> dict[str, Any]:
        """Get detailed status for a specific player.

        Args:
            player_id: ID of the player to get status for

        Returns:
            Dictionary containing player status information

        Raises:
            APIError: If the server returns an error response
            ConnectionError: If unable to connect to the server
            ParseError: If the response cannot be parsed
        """
        try:
            html_content = self.get_html("status.html", player_id).decode(
                "utf-8", errors="replace"
            )

            # Start with default status, then fill in actual values
            status = DEFAULT_STATUS.copy()
            status["player_id"] = player_id

            # Extract player name from title
            title_match = re.search(
                r"<title>Squeezebox Music Player\s+(.+?)\s*</title>", html_content
            )
            if title_match:
                status["player_name"] = title_match.group(1)

            # Extract current status
            status_match = re.search(
                r'<div id="playingStatus">\s*(.+?)\s*</div>', html_content, re.DOTALL
            )
            if status_match:
                status_text = re.sub(r"<[^>]+>", "", status_match.group(1)).strip()
                status["status"] = status_text

                # Try to determine the mode from the status text
                if "playing" in status_text.lower():
                    status["mode"] = PlayerMode.PLAY
                elif "pause" in status_text.lower():
                    status["mode"] = PlayerMode.PAUSE
                else:
                    status["mode"] = PlayerMode.STOP

            # Extract current track info
            current_track = {}
            song_match = re.search(
                r'<div class="playingSong"><a[^>]*>([^<]+)</a>', html_content
            )
            if song_match:
                current_track["title"] = song_match.group(1)

            artist_match = re.search(
                r'<span style="display:inline">([^<]+)</span>', html_content
            )
            if artist_match:
                current_track["artist"] = artist_match.group(1)

            # Extract track position if available
            if isinstance(status["status"], str):
                position_match = re.search(r"(\d+)\s+of\s+(\d+)", status["status"])
                if position_match:
                    try:
                        position = int(position_match.group(1))
                        total = int(position_match.group(2))
                        current_track["position"] = position
                        current_track["duration"] = total
                    except (ValueError, IndexError):
                        pass

            status["current_track"] = current_track

            # Extract volume
            # For volume extraction, we'll use the pattern of volume links in the page
            # The server uses a 1-11 scale (corresponding to 0-100)
            volume_links = re.findall(
                r'<a href="[^"]*mixer&amp;p1=volume&amp;p2=(\d+)[^"]*"[^>]*>([^<]+)</a>',
                html_content,
            )
            value_to_number = {}
            for value, number in volume_links:
                try:
                    value_to_number[int(number)] = int(value)
                except ValueError:
                    pass

            # Find the bold number that should be the current volume
            volume_bold = re.findall(r"<b>(\d+)</b>", html_content)
            if volume_bold:
                for bold_value in volume_bold:
                    try:
                        bold_num = int(bold_value)
                        # If this number is in the range 1-11, it's likely our volume indicator
                        if 1 <= bold_num <= 11:
                            # Map to 0-100 scale
                            volume_map = {
                                1: 0,
                                2: 10,
                                3: 20,
                                4: 30,
                                5: 40,
                                6: 50,
                                7: 60,
                                8: 70,
                                9: 80,
                                10: 90,
                                11: 100,
                            }
                            status["volume"] = volume_map.get(
                                bold_num, (bold_num - 1) * 10
                            )
                            break
                    except ValueError:
                        pass

            # Extract power status
            if "<b>on</b>" in html_content or (
                "/<b>off</b>" in html_content and "<b>on</b>/" not in html_content
            ):
                status["power"] = PowerState.ON
            elif "<b>off</b>" in html_content:
                status["power"] = PowerState.OFF

            # Try to extract shuffle and repeat modes (limited in HTML interface)
            # These are often not available in the HTML interface, so we set defaults

            # Shuffle detection (very basic - might not be reliable)
            if "shuffle" in html_content.lower():
                status["shuffle"] = ShuffleMode.SONGS
                status["shuffle_mode"] = ShuffleMode.to_string(ShuffleMode.SONGS)

            # Repeat detection (very basic - might not be reliable)
            if "repeat" in html_content.lower():
                status["repeat"] = RepeatMode.ALL
                status["repeat_mode"] = RepeatMode.to_string(RepeatMode.ALL)

            return status

        except (ConnectionError, APIError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            # Convert generic exceptions to ParseError
            raise ParseError(f"Failed to parse player status: {str(e)}")

    def debug_volume_controls(self, player_id: str) -> None:
        """Debug function to print all volume control elements in the HTML.

        Args:
            player_id: ID of the player to analyze
        """
        html_content = self.get_html("status.html", player_id).decode(
            "utf-8", errors="replace"
        )

        # Extract volume links
        volume_links = re.findall(
            r'<a href="[^"]*mixer&amp;p1=volume&amp;p2=(\d+)[^"]*"[^>]*>([^<]+)</a>',
            html_content,
        )
        print("Volume links found:")
        for value, text in volume_links:
            print(f"  Value: {value}, Text: {text}")

        # Extract current volume indicator
        volume_bold = re.findall(r"<b>(\d+)</b>", html_content)
        print("Bold numbers found (could be any bold number in the page):")
        for value in volume_bold:
            print(f"  Value: {value}")

        # Look for any volume regions
        volume_section = re.search(r"Volume:.*?<br>", html_content, re.DOTALL)
        if volume_section:
            print("\nVolume section found:")
            section_text = volume_section.group(0)
            print(section_text.replace("\n", " ").strip())

            # Find the bold number in the section
            bold_match = re.search(r"<b>(\d+)</b>", section_text)
            if bold_match:
                volume_num = int(bold_match.group(1))
                print(f"\nVolume bold number in section: {volume_num}")
                # Map to 0-100 scale
                volume_map = {
                    1: 0,
                    2: 10,
                    3: 20,
                    4: 30,
                    5: 40,
                    6: 50,
                    7: 60,
                    8: 70,
                    9: 80,
                    10: 90,
                    11: 100,
                }
                volume = volume_map.get(volume_num, (volume_num - 1) * 10)
                print(f"Mapped to 0-100 scale: {volume}")
            else:
                print("\nNo bold number found in volume section")

        else:
            print("\nNo volume section found. Searching for alternative patterns...")
            # Try different patterns
            volume_alt = re.search(r"Volume:.*?(\d+)", html_content)
            if volume_alt:
                print(f"Found alternative volume: {volume_alt.group(1)}")
                print(f"Context: {volume_alt.group(0)}")

        # Print a larger chunk around Volume: for manual inspection
        volume_context = re.search(r".{0,100}Volume:.{0,200}", html_content)
        if volume_context:
            print("\nVolume context (200 chars around 'Volume:'):")
            print(volume_context.group(0).replace("\n", " "))

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
        # Map 0-100 scale to SqueezeBox server values
        # Server uses 0, 10, 20, ..., 100
        volume = max(0, min(100, volume))  # Ensure within range
        # Round to nearest 10
        volume = round(volume / 10) * 10

        path = "status.html"
        query = f"player={urllib.parse.quote(player_id)}&p0=mixer&p1=volume&p2={volume}"

        url = f"{self.server_url}/{path}?{query}"

        if debug:
            print(f"Debug: Sending volume command URL: {url}")

        try:
            urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            try:
                response_body = e.read().decode("utf-8")
                raise CommandError(
                    f"HTTP error {e.code}: {response_body}",
                    command=f"mixer volume {volume}",
                )
            except Exception:
                raise CommandError(
                    f"HTTP error {e.code}", command=f"mixer volume {volume}"
                )
        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, "reason") else str(e)
            raise CommandError(
                f"Failed to connect to server: {reason}",
                command=f"mixer volume {volume}",
            )
        except Exception as e:
            # Catch-all for any other unexpected errors
            raise CommandError(
                f"Failed to set volume: {str(e)}", command=f"mixer volume {volume}"
            )

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
        # Use the direct player API format that works more reliably
        path = "status.html"
        cmd_str = f"seek to {seconds}"

        try:
            # Use different command based on whether we're restarting or seeking
            if seconds == 0:
                # For restart, use jump command
                query = (
                    f"player={urllib.parse.quote(player_id)}&p0=playlist&p1=jump&p2=0"
                )
            else:
                # For specific time, use time command
                query = f"player={urllib.parse.quote(player_id)}&p0=time&p1={seconds}"

            url = f"{self.server_url}/{path}?{query}"

            if debug:
                print(f"Debug: Sending seek command URL: {url}")

            urllib.request.urlopen(url)

        except urllib.error.HTTPError as e:
            try:
                response_body = e.read().decode("utf-8")
                # Try fallback method
                try:
                    if seconds == 0:
                        query = f"player={urllib.parse.quote(player_id)}&p0=time&p1=0"
                    else:
                        query = f"player={urllib.parse.quote(player_id)}&p0=playlist&p1=index&p2=0"

                    url = f"{self.server_url}/{path}?{query}"
                    urllib.request.urlopen(url)
                except Exception as e2:
                    raise CommandError(
                        f"HTTP error {e.code}: {response_body} (fallback failed: {e2})",
                        command=cmd_str,
                    )
            except Exception:
                raise CommandError(f"HTTP error {e.code}", command=cmd_str)

        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, "reason") else str(e)
            raise CommandError(
                f"Failed to connect to server: {reason}", command=cmd_str
            )

        except Exception as e:
            # Catch-all for any other unexpected errors
            raise CommandError(f"Failed to seek to position: {str(e)}", command=cmd_str)

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
        # Use the direct player API format
        path = "status.html"
        cmd_str = "display"

        try:
            # Send the display command
            query = f"player={urllib.parse.quote(player_id)}&p0=display"
            url = f"{self.server_url}/{path}?{query}"

            if debug:
                print(f"Debug: Sending display command URL: {url}")

            urllib.request.urlopen(url)

        except urllib.error.HTTPError as e:
            try:
                response_body = e.read().decode("utf-8")
                raise CommandError(
                    f"HTTP error {e.code}: {response_body}", command=cmd_str
                )
            except Exception:
                raise CommandError(f"HTTP error {e.code}", command=cmd_str)

        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, "reason") else str(e)
            raise CommandError(
                f"Failed to connect to server: {reason}", command=cmd_str
            )

        except Exception as e:
            # Catch-all for any other unexpected errors
            raise CommandError(
                f"Failed to show Now Playing screen: {str(e)}", command=cmd_str
            )

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

        # Special handling for volume command
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

        # Special handling for time command (seeking)
        if command == "time" and params and len(params) > 0:
            try:
                seconds = int(params[0])
                self.seek_to_time(player_id, seconds, debug)
                return
            except (ValueError, IndexError) as e:
                raise CommandError(f"Invalid time parameter: {e}", command=cmd_str)
            except CommandError:
                # Re-raise command errors from seek_to_time
                raise

        # General command handling
        path = "status.html"
        query = (
            f"player={urllib.parse.quote(player_id)}&p0={urllib.parse.quote(command)}"
        )

        if params:
            for i, param in enumerate(params, 1):
                query += f"&p{i}={urllib.parse.quote(str(param))}"

        url = f"{self.server_url}/{path}?{query}"

        if debug:
            print(f"Debug: Sending command URL: {url}")

        try:
            urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            try:
                response_body = e.read().decode("utf-8")
                raise CommandError(
                    f"HTTP error {e.code}: {response_body}", command=cmd_str
                )
            except Exception:
                raise CommandError(f"HTTP error {e.code}", command=cmd_str)
        except urllib.error.URLError as e:
            reason = str(e.reason) if hasattr(e, "reason") else str(e)
            raise CommandError(
                f"Failed to connect to server: {reason}", command=cmd_str
            )
        except Exception as e:
            # Catch-all for any other unexpected errors
            raise CommandError(f"Failed to send command: {str(e)}", command=cmd_str)
