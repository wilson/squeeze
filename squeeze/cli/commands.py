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
    no_color: bool = False


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
class PrevCommandArgs(PlayerCommandArgs):
    """Arguments for the previous track command."""

    threshold: int = field(default=5)


@dataclass
class PlayersCommandArgs(CommandArgs):
    """Arguments for the players command."""

    pass


@dataclass
class ServerCommandArgs(CommandArgs):
    """Arguments for the server command."""

    pass


@dataclass
class JumpCommandArgs(PlayerCommandArgs):
    """Arguments for the jump command."""

    index: int = field(default=0)


@dataclass
class ConfigCommandArgs(CommandArgs):
    """Arguments for the config command."""

    set_server: str | None = None


@dataclass
class SearchCommandArgs(CommandArgs):
    """Arguments for the search command."""

    term: str = field(default="")
    type: str = field(default="all")


def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_tries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 1.5,
    retry_exceptions: tuple[type[Exception], ...] = (ConnectionError,),
    no_retry_exceptions: tuple[type[Exception], ...] = (CommandError,),
    fallback_func: Callable[..., Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute a function with retry logic.

    Args:
        func: Function to call
        *args: Positional arguments to pass to the function
        max_tries: Maximum number of retries
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay on each retry
        retry_exceptions: Exceptions that should trigger a retry
        no_retry_exceptions: Exceptions that should never be retried
        fallback_func: Function to call if all retries fail
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function call

    Raises:
        Exception: The last exception that caused the retry to fail, or a no_retry exception
    """
    import time

    tries = 0
    delay = retry_delay
    last_error = None

    while tries < max_tries:
        try:
            return func(*args, **kwargs)
        except no_retry_exceptions:
            # Don't retry these exceptions
            raise
        except retry_exceptions as e:
            # These are the exceptions we'll retry
            last_error = e
            tries += 1
            if tries >= max_tries:
                break
            time.sleep(delay)
            delay *= backoff_factor
        except Exception as e:
            # Other exceptions - capture but don't retry
            last_error = e
            break

    # If we've exhausted retries or got an unexpected exception, call fallback if provided
    if fallback_func:
        return fallback_func(*args, **kwargs)

    # Otherwise raise the last error
    if last_error:
        raise last_error

    # This should not be reachable
    raise RuntimeError("Unexpected error in retry logic")


def extract_track_position(status: PlayerStatus) -> int:
    """Extract current track position in seconds from player status.

    Args:
        status: Player status dictionary from get_player_status

    Returns:
        Current track position in seconds, or 0 if not available
    """
    try:
        current_track = status.get("current_track", {})
        if not current_track:
            return 0

        position = current_track.get("position", 0)
        return int(float(position))
    except (ValueError, TypeError):
        return 0


def restart_track(client: ClientType, player_id: str) -> None:
    """Restart the current track (seek to position 0).

    Args:
        client: Client instance
        player_id: ID of the player to control

    Raises:
        Exception: If the command fails
    """
    try:
        # Define a function to restart track with retry
        def restart_track_retry(client_obj: ClientType, pid: str) -> None:
            client_obj.send_command(pid, "time", ["0"])

        # Use with_retry to handle transient errors
        with_retry(
            restart_track_retry,
            client,
            player_id,
            max_tries=2,
            retry_delay=0.5,
        )
    except Exception:
        # Pass through any exceptions from with_retry
        raise


def display_progress_bar(
    position: int | str, duration: int | str, width: int = 40
) -> None:
    """Display a simple ASCII progress bar.

    Args:
        position: Current position in seconds
        duration: Track duration in seconds
        width: Width of the progress bar in characters
    """
    try:
        # Convert to float to handle various input types
        if isinstance(position, str):
            position_secs = float(position)
        else:
            position_secs = float(position)

        if isinstance(duration, str):
            duration_secs = float(duration)
        else:
            duration_secs = float(duration)

        # Calculate percentage and number of filled characters
        if duration_secs > 0:
            percent = min(100, int((position_secs / duration_secs) * 100))
            filled_width = int(width * percent / 100)
        else:
            percent = 0
            filled_width = 0

        # Create the bar display
        bar = "█" * filled_width + "░" * (width - filled_width)
        print(f"Progress: [{bar}] {percent}%")

    except (ValueError, TypeError, ZeroDivisionError):
        # If there's an error, don't show anything
        pass


# Define ANSI color codes - safe for most terminals including MacOS Terminal
# Using more subdued colors for a professional look
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"  # Dimmed text, more subtle
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
# Avoid the bright colors as they can be garish
LIGHT_GREEN = "\033[92m"  # Renamed for clarity about usage
LIGHT_YELLOW = "\033[93m"  # Renamed for clarity about usage
LIGHT_BLUE = "\033[94m"  # Renamed for clarity about usage


def format_player_status(
    status: PlayerStatus, show_all_track_fields: bool = False, use_color: bool = True
) -> list[str]:
    """Format player status into a list of strings.

    Args:
        status: Player status dictionary
        show_all_track_fields: Whether to display all track fields or only priority ones
        use_color: Whether to use ANSI colors in the output

    Returns:
        List of formatted strings representing the player status
    """
    # Initialize the result list
    lines = []

    # Helper function to apply color conditionally
    def colorize(text: str, color: str) -> str:
        if use_color:
            return f"{color}{text}{RESET}"
        return text

    # Extract basic player information
    player_name = status.get("player_name", "Unknown")
    player_id_str = status.get("player_id", "")
    power = "on" if str(status.get("power", "0")) == "1" else "off"
    play_status = status.get("status", "Unknown")
    volume = status.get("volume", "?")

    # Fix power display - if it's playing music, it must be on regardless of what API says
    if play_status in ["playing", "Now Playing"] and power == "off":
        power = "on"

    # When the server reports a volume of 0 but the player is playing,
    # it may be a WiiM or another device with external volume control
    if (volume == 0 or volume == "0") and play_status in ["playing", "Now Playing"]:
        volume_display = "external control"  # WiiM likely has its own volume control
    else:
        volume_display = f"{volume}%"

    # Format values with colors based on their status - using more subtle colors
    player_name_display = colorize(player_name, BOLD)  # Just bold, no color

    if power == "on":
        power_display = colorize(power, GREEN)
    else:
        power_display = colorize(power, RED)

    if play_status.lower() == "playing" or play_status == "Now Playing":
        status_display = colorize(
            play_status, GREEN
        )  # Regular green instead of bright green
    elif play_status.lower() == "paused":
        status_display = colorize(play_status, YELLOW)
    elif play_status.lower() == "stopped":
        status_display = colorize(play_status, RED)
    else:
        status_display = colorize(play_status, RESET)

    # Use consistent field width for all player information (10 chars)
    player_label = colorize("PLAYER:".ljust(10), BOLD)
    id_label = colorize("ID:".ljust(10), BOLD)
    power_label = colorize("POWER:".ljust(10), BOLD)
    status_label = colorize("STATUS:".ljust(10), BOLD)
    volume_label = colorize("VOLUME:".ljust(10), BOLD)

    # Add basic player information
    lines.append(f"{player_label} {player_name_display}")
    lines.append(f"{id_label} {player_id_str}")
    lines.append(f"{power_label} {power_display}")
    lines.append(f"{status_label} {status_display}")
    lines.append(f"{volume_label} {colorize(volume_display, DIM)}")

    # Print shuffle and repeat if available - with more subtle coloring
    if "shuffle_mode" in status:
        shuffle_value = status["shuffle_mode"]
        # Only colorize if it's enabled (not "off")
        if shuffle_value != "off":
            shuffle_display = colorize(shuffle_value, DIM + GREEN)
        else:
            shuffle_display = colorize(shuffle_value, DIM)
        shuffle_label = colorize("SHUFFLE:".ljust(10), BOLD)
        lines.append(f"{shuffle_label} {shuffle_display}")

    if "repeat_mode" in status:
        repeat_value = status["repeat_mode"]
        # Only colorize if it's enabled (not "off")
        if repeat_value != "off":
            repeat_display = colorize(repeat_value, DIM + GREEN)
        else:
            repeat_display = colorize(repeat_value, DIM)
        repeat_label = colorize("REPEAT:".ljust(10), BOLD)
        lines.append(f"{repeat_label} {repeat_display}")

    # Print playlist info if available - more subtle coloring
    if "playlist_count" in status and status["playlist_count"] > 0:
        playlist_pos = status.get("playlist_position", 0) + 1
        playlist_count = status.get("playlist_count", 0)
        position_display = colorize(str(playlist_pos), BOLD)  # Just bold the position
        count_display = colorize(str(playlist_count), DIM)  # Dim the total count
        playlist_label = colorize("PLAYLIST:".ljust(10), BOLD)
        lines.append(f"{playlist_label} {position_display} of {count_display}")

    # Add separator for current track
    lines.append("")
    lines.append(colorize("------ CURRENT TRACK ------", BOLD))
    lines.append("")

    # Display current track information
    current_track = status.get("current_track", {})
    if current_track and isinstance(current_track, dict):
        # Priority fields to display in order
        priority_fields = [
            "title",
            "artist",
            "album",
            "position",
            "duration",
        ]

        # Process each priority field
        for field in priority_fields:
            if field in current_track:
                # Format position and duration as time if needed
                if field == "position" or field == "duration":
                    try:
                        value = format_time_simple(float(current_track[field]))
                    except (ValueError, TypeError):
                        value = "0:00"
                else:
                    value = current_track[field]

                # Apply color based on field type - more subtle now
                if field == "title":
                    value_display = colorize(
                        value, BOLD + YELLOW
                    )  # Bold yellow instead of bright yellow
                elif field == "artist":
                    value_display = colorize(
                        value, GREEN
                    )  # Standard green instead of bright green
                elif field == "album":
                    value_display = colorize(
                        value, BLUE
                    )  # Standard blue instead of bright blue
                else:
                    value_display = colorize(
                        value, DIM + CYAN
                    )  # Dimmed cyan for less important fields

                # Create field label with consistent width (10 chars)
                field_label = colorize(f"{field.upper()}:".ljust(10), BOLD)
                lines.append(f"{field_label} {value_display}")

        # Add progress bar if position and duration are available
        try:
            position = float(current_track.get("position", 0))
            duration = float(current_track.get("duration", 0))

            if duration > 0:
                # Use subtle formatting for time display
                pos_display = colorize(
                    format_time_simple(position), BOLD
                )  # Bold for current position
                dur_display = colorize(
                    format_time_simple(duration), DIM
                )  # Dim for total duration
                # Use consistent padding for TIME field
                time_label = colorize("TIME:".ljust(10), BOLD)
                lines.append(f"{time_label} {pos_display} / {dur_display}")

                # Simple progress bar with colored components
                percent = min(100, int((position / duration) * 100))
                bar_width = 30
                filled_width = int(bar_width * percent / 100)

                if use_color:
                    # More subtle progress bar: green fill, dimmed unfilled portion, normal percentage
                    bar = f"[{GREEN}{'█' * filled_width}{RESET}{DIM}{'▒' * (bar_width - filled_width)}{RESET}] {percent}%"
                else:
                    bar = f"[{'#' * filled_width}{'-' * (bar_width - filled_width)}] {percent}%"

                # Use consistent padding for PROGRESS field
                progress_label = colorize("PROGRESS:".ljust(10), BOLD)
                lines.append(f"{progress_label} {bar}")
        except (ValueError, TypeError):
            pass

        # Then add any remaining fields if requested
        if show_all_track_fields:
            lines.append("")
            lines.append(colorize("Additional track information:", BOLD))
            for key, value in current_track.items():
                if key not in priority_fields and key != "artwork":
                    lines.append(f"  {colorize(key.capitalize() + ':', CYAN)} {value}")

    return lines


def format_time_simple(seconds: float) -> str:
    """Format a time value in seconds to a string format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (HH:MM:SS or MM:SS)
    """
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def print_player_status(
    status: PlayerStatus, show_all_track_fields: bool = False, use_color: bool = True
) -> None:
    """Print player status in a formatted way.

    Args:
        status: Player status dictionary
        show_all_track_fields: Whether to display all track fields or only priority ones
        use_color: Whether to use ANSI colors in the output
    """
    # Get formatted status as a list of strings
    status_lines = format_player_status(status, show_all_track_fields, use_color)

    # Print the formatted status with color if enabled - more subtle header
    header = (
        f"{BOLD}====== SQUEEZE STATUS ======{RESET}"  # Just bold, no color
        if use_color
        else "====== SQUEEZE STATUS ======"
    )
    print(header)
    print("")
    for line in status_lines:
        print(line)


def is_keystroke_module_available() -> bool:
    """Check if keystroke detection is available on this platform.

    Returns:
        True if keystroke detection modules are available, False otherwise
    """
    import importlib.util
    import os
    import sys

    # Check if we're in an interactive terminal
    if not os.isatty(sys.stdin.fileno()):
        return False

    # Store platform for cleaner code
    platform = sys.platform

    # For macOS and Linux
    if platform == "darwin" or platform.startswith("linux"):
        # Check for termios and tty modules
        has_termios = importlib.util.find_spec("termios") is not None
        has_tty = importlib.util.find_spec("tty") is not None
        return has_termios and has_tty

    # For Windows
    if platform == "win32":
        # Check for msvcrt module
        has_msvcrt = importlib.util.find_spec("msvcrt") is not None
        return has_msvcrt

    # Any other platform is not supported
    return False


# Track when keys were last pressed to avoid duplicates
_last_key_press_time: dict[str, float] = {}


def get_keypress(timeout: float = 0.1) -> str | None:
    """Get a keypress without blocking, with timeout.

    This implementation is simpler and more reliable across different terminals.

    Args:
        timeout: How long to wait for a keypress in seconds

    Returns:
        Key identifier string (e.g., "up", "down", "left", "right", "q") or None if no key pressed
    """
    import os
    import select
    import sys
    import time

    # First check if we can read from stdin within our timeout
    try:
        # Only try to read if stdin has data available
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if not rlist:
            return None  # No input available

        # Current time for debounce checking
        current_time = time.time()

        # Read a single character
        char = os.read(sys.stdin.fileno(), 1)

        # Process standard arrow key sequences (ESC [ A/B/C/D)
        if char == b"\x1b":  # ESC character
            # Check if more input is immediately available
            if select.select([sys.stdin], [], [], 0.02)[0]:  # Short timeout
                next_char = os.read(sys.stdin.fileno(), 1)

                if next_char == b"[" and select.select([sys.stdin], [], [], 0.02)[0]:
                    arrow_char = os.read(sys.stdin.fileno(), 1)

                    # Up arrow - use very minimal debounce for immediate response
                    if arrow_char == b"A":
                        last_time = _last_key_press_time.get("up", 0)
                        if current_time - last_time > 0.05:  # 50ms debounce
                            _last_key_press_time["up"] = current_time
                            return "up"

                    # Down arrow
                    elif arrow_char == b"B":
                        last_time = _last_key_press_time.get("down", 0)
                        if current_time - last_time > 0.05:  # 50ms debounce
                            _last_key_press_time["down"] = current_time
                            return "down"

                    # Right arrow
                    elif arrow_char == b"C":
                        last_time = _last_key_press_time.get("right", 0)
                        if current_time - last_time > 0.05:  # 50ms debounce
                            _last_key_press_time["right"] = current_time
                            return "right"

                    # Left arrow - most important, so give it special treatment
                    elif arrow_char == b"D":
                        last_time = _last_key_press_time.get("left", 0)
                        if current_time - last_time > 0.05:  # 50ms debounce
                            _last_key_press_time["left"] = current_time
                            # Clear any remaining input to avoid double triggering
                            while select.select([sys.stdin], [], [], 0.01)[0]:
                                os.read(sys.stdin.fileno(), 1)  # Discard
                            return "left"

        # Quit command is a simple 'q' key
        elif char in (b"q", b"Q"):
            return "q"

        # Letter keys for navigation - no debounce needed for most
        elif char == b"p":  # Previous track
            return "p"
        elif char == b"n":  # Next track
            return "n"
        elif char == b"s":  # Restart track
            return "s"

        # Volume controls - light debounce
        elif char == b"+":  # Volume up
            last_time = _last_key_press_time.get("vol_up", 0)
            if current_time - last_time > 0.1:  # 100ms debounce
                _last_key_press_time["vol_up"] = current_time
                return "+"
        elif char == b"-":  # Volume down
            last_time = _last_key_press_time.get("vol_down", 0)
            if current_time - last_time > 0.1:  # 100ms debounce
                _last_key_press_time["vol_down"] = current_time
                return "-"

        # Other keys - clear any remaining input
        while select.select([sys.stdin], [], [], 0.01)[0]:
            os.read(sys.stdin.fileno(), 1)  # Discard any remaining input

    except Exception:
        # If anything goes wrong with keyboard handling, just continue
        # This is robust against terminal issues
        pass

    return None


def display_live_status(
    client: ClientType, player_id: str, use_color: bool = True
) -> None:
    """Display continuously updating status with terminal formatting.

    Provides a structured terminal UI that works reliably across different terminal types.
    Uses simple text-based display for maximum compatibility.

    Args:
        client: Squeeze client instance
        player_id: ID of the player to get status for
        use_color: Whether to use ANSI colors in the display
    """
    import os
    import select
    import sys
    import time

    # Only import platform-specific modules when needed
    if sys.platform != "win32":
        import fcntl
        import termios
        import tty

    # Terminal settings backup
    old_settings = None
    fd = None
    is_raw_mode = False

    # We now use the global format_time_simple function

    # Helper to clear the screen in a cross-platform way
    def clear_screen() -> None:
        if sys.platform == "win32":
            os.system("cls")
        else:
            os.system("clear")

    # Display status information in a simple format
    def display_simple_status(status: PlayerStatus, use_color: bool = True) -> None:
        """Display status with simple text formatting."""
        # Clear screen
        clear_screen()

        # Get formatted status lines
        status_lines = format_player_status(
            status, show_all_track_fields=False, use_color=use_color
        )

        # Print header with color if enabled - more subtle header
        header = (
            f"{BOLD}====== SQUEEZE STATUS ====== (q=quit){RESET}"  # Just bold, no color
            if use_color
            else "====== SQUEEZE STATUS ====== (q=quit)"
        )
        print(header)
        print("")

        # Print the formatted status lines
        for line in status_lines:
            print(line)

        # Add keyboard controls info - modify based on volume state
        print("")

        # Determine key controls based on volume
        volume_val = status.get("volume", 0)
        has_volume_control = volume_val != 0

        if use_color:
            # Use different controls based on volume capability
            if has_volume_control:
                # Normal volume controls
                vol_controls = f"{BOLD}+/↑{RESET} (vol+) {BOLD}-/↓{RESET} (vol-)"
            else:
                # For devices with 0 volume (likely external control)
                vol_controls = f"{BOLD}v{RESET} (try vol reset)"

            # Display all controls - removed 's' since left arrow/p already handle restart
            print(
                f"{BOLD}KEYS:{RESET} {BOLD}p/←{RESET} (prev/restart) {BOLD}n/→{RESET} (next) {vol_controls} {BOLD}q{RESET} (quit)"
            )
        else:
            # Plain text controls based on volume capability
            if has_volume_control:
                vol_controls = "+/↑ (vol+) -/↓ (vol-)"
            else:
                vol_controls = "v (try vol reset)"

            print(f"KEYS: p/← (prev/restart) n/→ (next) {vol_controls} q (quit)")
        print("")

    # Setup for keyboard input
    print("Starting Live Status mode...")
    print("Loading player information...")

    # On macOS and Linux, we'll set up cbreak mode (not raw mode)
    if sys.platform != "win32" and sys.stdin.isatty():
        try:
            # Use cbreak mode which allows control characters but doesn't echo
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)

            # Make stdin non-blocking - this is critical
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Successful setup
            is_raw_mode = True

            # Flush any pending input
            time.sleep(0.1)
            while select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.read(1)

        except Exception as e:
            print(f"Keyboard setup error: {e}")
            is_raw_mode = False

    # Main display loop
    try:
        while True:
            try:
                # Get player status
                status = client.get_player_status(player_id)

                # Use the simple display function with color if enabled
                display_simple_status(status, use_color=use_color)

                # Extract data for key handling
                current_track = status.get("current_track", {})
                try:
                    position = float(current_track.get("position", 0))
                    # We don't need volume value for absolute adjustments since we're
                    # using relative volume adjustments for WiiM compatibility
                except (ValueError, TypeError):
                    position = 0

                # Handle keyboard input
                key_pressed = False

                # Windows keyboard handling
                if sys.platform == "win32":
                    import msvcrt

                    # Check for keypress without waiting
                    if msvcrt.kbhit():
                        key = msvcrt.getch()

                        # Process 'q' immediately for responsiveness
                        if key == b"q":
                            break

                        # For arrow keys and letter keys, respond immediately without debounce
                        # to make the interface much more responsive
                        key_pressed = True

                        if key == b"\xe0":  # Special keys
                            arrow = msvcrt.getch()

                            if arrow == b"K":  # Left
                                if position <= 5:
                                    client.send_command(
                                        player_id, "playlist", ["index", "-1"]
                                    )
                                    # Force an immediate status refresh
                                    status = client.get_player_status(player_id)
                                    display_simple_status(status, use_color=use_color)
                                else:
                                    client.send_command(player_id, "time", ["0"])

                            elif arrow == b"M":  # Right
                                client.send_command(
                                    player_id, "playlist", ["index", "+1"]
                                )
                                # Force an immediate status refresh
                                status = client.get_player_status(player_id)
                                display_simple_status(status, use_color=use_color)

                            elif arrow == b"H":  # Up
                                # Only allow volume up if the player reports non-zero volume
                                volume_val = status.get("volume", 0)
                                if volume_val != 0:
                                    # Use relative volume adjustment
                                    client.send_command(
                                        player_id, "mixer", ["volume", "+5"]
                                    )
                                    # Small delay to allow volume to change
                                    time.sleep(0.2)
                                    # Force immediate refresh to show new volume
                                    status = client.get_player_status(player_id)
                                    display_simple_status(status, use_color=use_color)

                            elif arrow == b"P":  # Down
                                # Only allow volume down if the player reports non-zero volume
                                volume_val = status.get("volume", 0)
                                if volume_val != 0:
                                    # Use relative volume adjustment
                                    client.send_command(
                                        player_id, "mixer", ["volume", "-5"]
                                    )
                                    # Small delay to allow volume to change
                                    time.sleep(0.2)
                                    # Force immediate refresh to show new volume
                                    status = client.get_player_status(player_id)
                                    display_simple_status(status, use_color=use_color)

                            # Handle 'v' key for volume reset for WiiM devices
                            elif key == b"v" or key == b"V":  # Volume reset to 100%
                                volume_val = status.get("volume", 0)
                                if (
                                    volume_val == 0
                                ):  # Only for devices with volume issues
                                    # Try to set volume to 100%
                                    client.send_command(
                                        player_id, "mixer", ["volume", "100"]
                                    )
                                    # Allow time for volume change to take effect
                                    time.sleep(0.5)
                                    # Force immediate refresh
                                    status = client.get_player_status(player_id)
                                    display_simple_status(status, use_color=use_color)

                # Unix-like keyboard handling - use the get_keypress function for more reliable detection
                try:
                    key = get_keypress(
                        0.01
                    )  # Use a very short timeout for responsive UI

                    if key == "q":  # Quit immediately
                        break

                    elif (
                        key == "p" or key == "left"
                    ):  # Previous track handling - dual behavior
                        if position <= 5:
                            client.send_command(player_id, "playlist", ["index", "-1"])
                            # Force immediate refresh
                            status = client.get_player_status(player_id)
                            display_simple_status(status, use_color=use_color)
                        else:
                            client.send_command(player_id, "time", ["0"])
                        key_pressed = True

                    elif key == "n" or key == "right":  # Next track
                        client.send_command(player_id, "playlist", ["index", "+1"])
                        # Force immediate refresh
                        status = client.get_player_status(player_id)
                        display_simple_status(status, use_color=use_color)
                        key_pressed = True

                    elif key == "+" or key == "up":  # Volume up
                        # Only allow volume up if the player reports non-zero volume
                        volume_val = status.get("volume", 0)
                        if volume_val != 0:
                            # Use relative volume adjustment
                            client.send_command(player_id, "mixer", ["volume", "+5"])
                            # Small delay to allow volume to change
                            time.sleep(0.2)
                            # Force immediate refresh to show new volume
                            status = client.get_player_status(player_id)
                            display_simple_status(status, use_color=use_color)
                        key_pressed = True

                    elif key == "-" or key == "down":  # Volume down
                        # Only allow volume down if the player reports non-zero volume
                        volume_val = status.get("volume", 0)
                        if volume_val != 0:
                            # Use relative volume adjustment
                            client.send_command(player_id, "mixer", ["volume", "-5"])
                            # Small delay to allow volume to change
                            time.sleep(0.2)
                            # Force immediate refresh to show new volume
                            status = client.get_player_status(player_id)
                            display_simple_status(status, use_color=use_color)
                        key_pressed = True

                    # The 's' key for restart has been removed as redundant
                    # Left arrow/p already handle this functionality

                    elif key == "v":  # Volume reset to 100% for external volume devices
                        volume_val = status.get("volume", 0)
                        if volume_val == 0:  # Only for devices with volume issues
                            # Try to set volume to 100%
                            client.send_command(player_id, "mixer", ["volume", "100"])
                            # Allow time for volume change to take effect
                            time.sleep(0.5)
                            # Force immediate refresh
                            status = client.get_player_status(player_id)
                            display_simple_status(status, use_color=use_color)
                        key_pressed = True
                except Exception:
                    # Ignore keyboard input errors
                    pass

                # Adjust sleep time based on activity for better responsiveness
                if key_pressed:
                    # Short sleep after key press to see the effect quickly
                    # Allow time for the server to update its status
                    time.sleep(0.3)
                else:
                    # Longer sleep when idle to reduce CPU usage
                    time.sleep(0.2)

            except (ConnectionError, APIError, ParseError, CommandError) as e:
                # Show error and retry
                clear_screen()
                print(f"\nError: {e}")
                print("Retrying in 5 seconds...")
                time.sleep(5)

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass

    except Exception as e:
        # Handle any other exceptions
        try:
            print(f"Error in live display: {e}")
        except (OSError, BlockingIOError):
            pass

    finally:
        # Always restore terminal settings
        if is_raw_mode and old_settings is not None and fd is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

        # Final cleanup
        try:
            # Clear screen
            clear_screen()

            # Reset terminal for good measure
            if sys.stdout.isatty() and sys.platform != "win32":
                os.system("stty sane")

            # Final message
            print("Exiting live status mode.")

        except Exception:
            # Last resort - nothing more we can do
            pass


def status_command(args: StatusCommandArgs) -> None:
    """Show status of a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    live_mode = args.live
    use_color = not args.no_color
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
        # Pass no_color option to display_live_status
        display_live_status(client, player_id, use_color=use_color)
    else:
        # Single status display
        try:
            status = client.get_player_status(player_id)
            print_player_status(status, show_all_track_fields=True, use_color=use_color)
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


def play_command(args: PlayerCommandArgs) -> None:
    """Send play command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
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


def pause_command(args: PlayerCommandArgs) -> None:
    """Send pause command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
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


def stop_command(args: PlayerCommandArgs) -> None:
    """Send stop command to a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
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


def volume_command(args: VolumeCommandArgs) -> None:
    """Set volume for a player.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    volume = args.volume
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    try:
        # Ensure volume is in valid range
        volume = max(0, min(100, volume))
        client.set_volume(player_id, volume)
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
    client = create_client(server_url)

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
    if not items:
        print("  No matches found")
        print()
        return

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
    # Define a helper function to extract artist from album
    def format_album(album: dict[str, Any]) -> str:
        # Extract artist from favorites_url if available
        artist = "Unknown"
        favorites_url = album.get("favorites_url", "")
        if favorites_url and "contributor.name=" in favorites_url:
            artist_part = favorites_url.split("contributor.name=")[-1]
            artist = artist_part.split("&")[0] if "&" in artist_part else artist_part
            # URL decode the artist name
            import urllib.parse

            artist = urllib.parse.unquote(artist)
        return f"{album.get('album')} by {artist}"

    formatters = {
        "artists": lambda artist: f"{artist.get('artist')}",
        "albums": format_album,
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

    index = args.index

    try:
        # Send the jump command - index is 0-based
        client.send_command(player_id, "playlist", ["index", str(index)])
        print(f"Jumped to track {index} in playlist for player {player_id}")
    except Exception as e:
        print(f"Error jumping to track: {e}", file=sys.stderr)
        sys.exit(1)


def prev_command(args: PrevCommandArgs) -> None:
    """Send previous track command to a player.

    This has special handling:
    - If the current track position is <= threshold (default 5 seconds),
      it will go to the previous track.
    - Otherwise, it will restart the current track.

    Args:
        args: Command-line arguments
    """
    server_url = get_server_url(args.server)
    client = create_client(server_url)

    player_id = get_player_id(args, client)
    if not player_id:
        sys.exit(1)

    threshold = args.threshold

    try:
        # Get the current track position
        status = client.get_player_status(player_id)
        position = extract_track_position(status)

        # Define separate functions for going to previous track vs. restarting current track
        def go_to_prev_track_absolute(client_obj: ClientType, pid: str) -> None:
            client_obj.send_command(pid, "playlist", ["index", "-1"])

        try:
            # If we're past the threshold, restart the track
            if position > threshold:
                restart_track(client, player_id)
                print(f"Restarted current track for player {player_id}")
            # Otherwise, go to the previous track
            else:
                with_retry(
                    go_to_prev_track_absolute,
                    client,
                    player_id,
                    max_tries=2,
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
                # Simple seconds value
                total_seconds = int(seconds)
            case [minutes, seconds] if minutes.isdigit() and seconds.isdigit():
                # MM:SS format
                total_seconds = int(minutes) * 60 + int(seconds)
            case [hours, minutes, seconds] if (
                hours.isdigit() and minutes.isdigit() and seconds.isdigit()
            ):
                # HH:MM:SS format
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            case _:
                raise ValueError(f"Invalid time format: {position}")

        # Use the seek_to_time method
        client.seek_to_time(player_id, total_seconds)
        print(f"Seeked to {format_time(total_seconds)} in the current track")
    except Exception as e:
        print(f"Error seeking to position: {e}", file=sys.stderr)
        sys.exit(1)
