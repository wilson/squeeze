"""
Constants used throughout the application.
"""


# Player modes
class PlayerMode:
    """Player mode constants."""

    STOP = "stop"
    PLAY = "play"
    PAUSE = "pause"

    @classmethod
    def to_string(cls, mode: str) -> str:
        """Convert mode to a user-friendly string."""
        if mode == cls.PLAY:
            return "Now Playing"
        elif mode == cls.PAUSE:
            return "Now Paused"
        elif mode == cls.STOP:
            return "Stopped"
        return "Unknown"


# Shuffle modes
class ShuffleMode:
    """Shuffle mode constants."""

    OFF = 0
    SONGS = 1
    ALBUMS = 2

    @classmethod
    def to_string(cls, mode: int) -> str:
        """Convert shuffle mode to a user-friendly string."""
        if mode == cls.OFF:
            return "Off"
        elif mode == cls.SONGS:
            return "Songs"
        elif mode == cls.ALBUMS:
            return "Albums"
        return "Unknown"


# Repeat modes
class RepeatMode:
    """Repeat mode constants."""

    OFF = 0
    ONE = 1
    ALL = 2

    @classmethod
    def to_string(cls, mode: int) -> str:
        """Convert repeat mode to a user-friendly string."""
        if mode == cls.OFF:
            return "Off"
        elif mode == cls.ONE:
            return "One"
        elif mode == cls.ALL:
            return "All"
        return "Unknown"


# Power states
class PowerState:
    """Power state constants."""

    OFF = "off"
    ON = "on"

    @classmethod
    def from_int(cls, state: int) -> str:
        """Convert numeric power state to string."""
        return cls.ON if state == 1 else cls.OFF
