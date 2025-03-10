"""
Constants used throughout the application.
"""

from enum import IntEnum, StrEnum


# Player modes
class PlayerMode(StrEnum):
    """Player mode constants."""

    STOP = "stop"
    PLAY = "play"
    PAUSE = "pause"

    @classmethod
    def to_string(cls, mode: str) -> str:
        """Convert mode to a user-friendly string."""
        match mode:
            case cls.PLAY:
                return "Now Playing"
            case cls.PAUSE:
                return "Now Paused"
            case cls.STOP:
                return "Stopped"
            case _:
                return "Unknown"


# Shuffle modes
class ShuffleMode(IntEnum):
    """Shuffle mode constants."""

    OFF = 0
    SONGS = 1
    ALBUMS = 2

    @classmethod
    def to_string(cls, mode: int) -> str:
        """Convert shuffle mode to a user-friendly string."""
        match mode:
            case cls.OFF:
                return "Off"
            case cls.SONGS:
                return "Songs"
            case cls.ALBUMS:
                return "Albums"
            case _:
                return "Unknown"


# Repeat modes
class RepeatMode(IntEnum):
    """Repeat mode constants."""

    OFF = 0
    ONE = 1
    ALL = 2

    @classmethod
    def to_string(cls, mode: int) -> str:
        """Convert repeat mode to a user-friendly string."""
        match mode:
            case cls.OFF:
                return "Off"
            case cls.ONE:
                return "One"
            case cls.ALL:
                return "All"
            case _:
                return "Unknown"


# Power states
class PowerState(StrEnum):
    """Power state constants."""

    OFF = "off"
    ON = "on"

    @classmethod
    def from_int(cls, state: int) -> str:
        """Convert numeric power state to string."""
        return cls.ON if state == 1 else cls.OFF
