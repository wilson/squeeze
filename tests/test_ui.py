"""Tests for the UI components."""

import io
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from squeeze.ui import curses_select_player, select_player, text_select_player


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


class TestCursesSelectPlayer:
    """Tests for the curses_select_player function."""

    @pytest.fixture
    def sample_players(self) -> list[dict[str, str]]:
        """Fixture for sample player data."""
        return [
            {"id": "00:11:22:33:44:55", "name": "Living Room"},
            {"id": "aa:bb:cc:dd:ee:ff", "name": "Kitchen"},
        ]

    @pytest.fixture
    def mock_curses(self) -> Generator[tuple[MagicMock, MagicMock], None, None]:
        """Fixture to mock the curses module."""
        with patch("squeeze.ui.curses") as mock_curses:
            # Set up key constants
            mock_curses.KEY_UP = 259
            mock_curses.KEY_DOWN = 258

            # Set up color pair constants
            mock_curses.COLOR_BLACK = 0
            mock_curses.COLOR_WHITE = 7
            mock_curses.A_BOLD = 2097152

            # Mock the screen
            mock_stdscr = MagicMock()
            mock_stdscr.getmaxyx.return_value = (24, 80)  # Standard terminal size
            mock_curses.initscr.return_value = mock_stdscr

            yield mock_curses, mock_stdscr

    def test_empty_players(self) -> None:
        """Test when player list is empty."""
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            result = curses_select_player([])
            assert result is None
            assert "No players found" in mock_stderr.getvalue()

    def test_select_player_with_enter(
        self,
        sample_players: list[dict[str, str]],
        mock_curses: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test selecting a player by pressing Enter."""
        mock_curses_module, mock_stdscr = mock_curses

        # Simulate pressing Enter on first selection
        mock_stdscr.getch.return_value = ord("\n")

        result = curses_select_player(sample_players)

        # Verify the correct cleanup
        mock_curses_module.nocbreak.assert_called_once()
        mock_stdscr.keypad.assert_called_with(False)
        mock_curses_module.echo.assert_called_once()
        mock_curses_module.endwin.assert_called_once()

        # Verify the result
        assert result == "00:11:22:33:44:55"  # First player should be selected

    def test_select_player_with_navigation(
        self,
        sample_players: list[dict[str, str]],
        mock_curses: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test navigating and selecting a player."""
        mock_curses_module, mock_stdscr = mock_curses

        # Simulate pressing Down Arrow and then Enter to select the second player
        mock_stdscr.getch.side_effect = [
            mock_curses_module.KEY_DOWN,  # Navigate down
            ord("\n"),  # Press Enter
        ]

        result = curses_select_player(sample_players)

        # Verify the result
        assert result == "aa:bb:cc:dd:ee:ff"  # Second player should be selected

    def test_quit_with_q(
        self,
        sample_players: list[dict[str, str]],
        mock_curses: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test quitting the selection with 'q'."""
        mock_curses_module, mock_stdscr = mock_curses

        # Simulate pressing 'q'
        mock_stdscr.getch.return_value = ord("q")

        result = curses_select_player(sample_players)

        # Verify the result
        assert result is None

    def test_navigate_wrapping(
        self,
        sample_players: list[dict[str, str]],
        mock_curses: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that navigation wraps around the list."""
        mock_curses_module, mock_stdscr = mock_curses

        # Simulate pressing Up Arrow (which should wrap to the last item) and then Enter
        mock_stdscr.getch.side_effect = [
            mock_curses_module.KEY_UP,  # Navigate up (wraps to bottom)
            ord("\n"),  # Press Enter
        ]

        result = curses_select_player(sample_players)

        # Verify the result
        assert result == "aa:bb:cc:dd:ee:ff"  # Last player should be selected

    # Testing cleanup in the finally block is complex due to how pytest handles exceptions
    # For full coverage, we'd need integration testing with curses but for now we'll skip this test
