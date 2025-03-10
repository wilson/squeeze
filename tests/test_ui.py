"""Tests for the UI components."""

import io
from unittest.mock import patch

import pytest

from squeeze.ui import select_player, text_select_player


class TestTextSelectPlayer:
    """Tests for the text_select_player function."""

    @pytest.fixture
    def sample_players(self) -> list[dict[str, str]]:
        """Fixture for sample player data."""
        return [
            {"id": "00:11:22:33:44:55", "name": "Living Room"},
            {"id": "aa:bb:cc:dd:ee:ff", "name": "Kitchen"},
        ]

    def test_empty_players(self) -> None:
        """Test when player list is empty."""
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            result = text_select_player([])
            assert result is None
            assert "No players found" in mock_stderr.getvalue()

    def test_valid_selection(self, sample_players: list[dict[str, str]]) -> None:
        """Test valid player selection."""
        with patch("builtins.input", return_value="1"):
            result = text_select_player(sample_players)
            assert result == "00:11:22:33:44:55"

        with patch("builtins.input", return_value="2"):
            result = text_select_player(sample_players)
            assert result == "aa:bb:cc:dd:ee:ff"

    def test_quit_selection(self, sample_players: list[dict[str, str]]) -> None:
        """Test quitting the selection."""
        with patch("builtins.input", return_value="q"):
            result = text_select_player(sample_players)
            assert result is None

    def test_invalid_number(self, sample_players: list[dict[str, str]]) -> None:
        """Test invalid number selection."""
        with (
            patch("builtins.input", return_value="3"),
            patch("sys.stderr", new=io.StringIO()) as mock_stderr,
        ):
            result = text_select_player(sample_players)
            assert result is None
            assert "Invalid selection" in mock_stderr.getvalue()

    def test_non_numeric_input(self, sample_players: list[dict[str, str]]) -> None:
        """Test non-numeric input."""
        with (
            patch("builtins.input", return_value="abc"),
            patch("sys.stderr", new=io.StringIO()) as mock_stderr,
        ):
            result = text_select_player(sample_players)
            assert result is None
            assert "Invalid input" in mock_stderr.getvalue()

    def test_eof_error(self, sample_players: list[dict[str, str]]) -> None:
        """Test EOFError handling."""
        with patch("builtins.input", side_effect=EOFError()):
            result = text_select_player(sample_players)
            assert result is None


class TestSelectPlayer:
    """Tests for the select_player function."""

    @pytest.fixture
    def sample_players(self) -> list[dict[str, str]]:
        """Fixture for sample player data."""
        return [
            {"id": "00:11:22:33:44:55", "name": "Living Room"},
            {"id": "aa:bb:cc:dd:ee:ff", "name": "Kitchen"},
        ]

    def test_empty_players(self) -> None:
        """Test when player list is empty."""
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            result = select_player([])
            assert result is None
            assert "No players found" in mock_stderr.getvalue()

    def test_tty_curses_ui(self, sample_players: list[dict[str, str]]) -> None:
        """Test selecting player in a TTY environment with curses."""
        with (
            patch("sys.stdout.isatty", return_value=True),
            patch(
                "squeeze.ui.curses_select_player", return_value="00:11:22:33:44:55"
            ) as mock_curses,
        ):
            result = select_player(sample_players)
            assert result == "00:11:22:33:44:55"
            mock_curses.assert_called_once_with(sample_players)

    def test_non_tty_text_ui(self, sample_players: list[dict[str, str]]) -> None:
        """Test selecting player in a non-TTY environment with text UI."""
        with (
            patch("sys.stdout.isatty", return_value=False),
            patch(
                "squeeze.ui.text_select_player", return_value="aa:bb:cc:dd:ee:ff"
            ) as mock_text,
        ):
            result = select_player(sample_players)
            assert result == "aa:bb:cc:dd:ee:ff"
            mock_text.assert_called_once_with(sample_players)

    def test_curses_error_fallback(self, sample_players: list[dict[str, str]]) -> None:
        """Test fallback to text UI when curses fails."""
        with (
            patch("sys.stdout.isatty", return_value=True),
            patch(
                "squeeze.ui.curses_select_player", side_effect=Exception("Curses error")
            ),
            patch(
                "squeeze.ui.text_select_player", return_value="aa:bb:cc:dd:ee:ff"
            ) as mock_text,
            patch("sys.stderr", new=io.StringIO()) as mock_stderr,
        ):
            result = select_player(sample_players)
            assert result == "aa:bb:cc:dd:ee:ff"
            mock_text.assert_called_once_with(sample_players)
            assert "Error displaying interactive menu" in mock_stderr.getvalue()
            assert "Falling back to text UI" in mock_stderr.getvalue()
