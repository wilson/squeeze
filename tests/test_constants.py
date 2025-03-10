"""Tests for the constants module."""

from squeeze.constants import PlayerMode, PowerState, RepeatMode, ShuffleMode


def test_player_mode_values() -> None:
    """Test PlayerMode enum values."""
    assert str(PlayerMode.STOP) == "stop"
    assert str(PlayerMode.PLAY) == "play"
    assert str(PlayerMode.PAUSE) == "pause"


def test_player_mode_to_string() -> None:
    """Test PlayerMode.to_string conversion."""
    assert PlayerMode.to_string(PlayerMode.PLAY) == "Now Playing"
    assert PlayerMode.to_string(PlayerMode.PAUSE) == "Now Paused"
    assert PlayerMode.to_string(PlayerMode.STOP) == "Stopped"
    assert PlayerMode.to_string("unknown") == "Unknown"


def test_shuffle_mode_values() -> None:
    """Test ShuffleMode enum values."""
    assert int(ShuffleMode.OFF) == 0
    assert int(ShuffleMode.SONGS) == 1
    assert int(ShuffleMode.ALBUMS) == 2


def test_shuffle_mode_to_string() -> None:
    """Test ShuffleMode.to_string conversion."""
    assert ShuffleMode.to_string(ShuffleMode.OFF) == "Off"
    assert ShuffleMode.to_string(ShuffleMode.SONGS) == "Songs"
    assert ShuffleMode.to_string(ShuffleMode.ALBUMS) == "Albums"
    assert ShuffleMode.to_string(99) == "Unknown"


def test_repeat_mode_values() -> None:
    """Test RepeatMode enum values."""
    assert int(RepeatMode.OFF) == 0
    assert int(RepeatMode.ONE) == 1
    assert int(RepeatMode.ALL) == 2


def test_repeat_mode_to_string() -> None:
    """Test RepeatMode.to_string conversion."""
    assert RepeatMode.to_string(RepeatMode.OFF) == "Off"
    assert RepeatMode.to_string(RepeatMode.ONE) == "One"
    assert RepeatMode.to_string(RepeatMode.ALL) == "All"
    assert RepeatMode.to_string(99) == "Unknown"


def test_power_state_values() -> None:
    """Test PowerState enum values."""
    assert str(PowerState.OFF) == "off"
    assert str(PowerState.ON) == "on"


def test_power_state_from_int() -> None:
    """Test PowerState.from_int conversion."""
    assert PowerState.from_int(0) == PowerState.OFF
    assert PowerState.from_int(1) == PowerState.ON
    # Test with non-standard values
    assert PowerState.from_int(100) == PowerState.OFF  # Only 1 is considered "on"
    assert PowerState.from_int(-1) == PowerState.OFF
