"""
Interactive UI components for the Squeeze CLI.
"""

import curses
import sys


def text_select_player(players: list[dict[str, str]]) -> str | None:
    """Display a simple text-based player selection menu.

    Args:
        players: List of player dictionaries with 'id' and 'name' keys

    Returns:
        Selected player ID or None if no selection was made
    """
    if not players:
        print("No players found", file=sys.stderr)
        return None

    print("\nSelect a SqueezeBox player:")
    print("--------------------------")

    # Display the options
    for i, player in enumerate(players):
        print(f"{i+1}. {player['name']} ({player['id']})")

    print("\nEnter number (or q to quit): ", end="")

    # Get input
    try:
        choice = input().strip().lower()

        if choice == "q":
            return None

        idx = int(choice) - 1
        if 0 <= idx < len(players):
            return players[idx]["id"]
        else:
            print("Invalid selection", file=sys.stderr)
            return None
    except ValueError:
        print("Invalid input", file=sys.stderr)
        return None
    except EOFError:
        return None


def curses_select_player(players: list[dict[str, str]]) -> str | None:
    """Display a curses-based interactive player selection menu.

    Args:
        players: List of player dictionaries with 'id' and 'name' keys

    Returns:
        Selected player ID or None if no selection was made
    """
    if not players:
        print("No players found", file=sys.stderr)
        return None

    # Initialize curses
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    # We'll track the result separately to avoid returning from finally
    result: str | None = None
    try:
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected item
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Normal item

        selected_idx = 0

        # Get screen dimensions
        max_y, max_x = stdscr.getmaxyx()

        # Title text
        title = "Select a SqueezeBox player:"

        # Calculate starting positions
        start_y = max(0, (max_y - len(players) - 4) // 2)
        start_x = max(
            0, (max_x - max(len(title), max(len(p["name"]) for p in players) + 4)) // 2
        )

        # Main loop
        while True:
            stdscr.clear()

            # Draw title
            stdscr.addstr(start_y, start_x, title, curses.A_BOLD)
            stdscr.addstr(start_y + 1, start_x, "─" * len(title))

            # Draw player list
            for i, player in enumerate(players):
                if i == selected_idx:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(start_y + i + 3, start_x, f" > {player['name']} ")
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.attron(curses.color_pair(2))
                    stdscr.addstr(start_y + i + 3, start_x, f"   {player['name']} ")
                    stdscr.attroff(curses.color_pair(2))

            # Draw instructions
            footer = "↑/↓: Navigate | Enter: Select | q: Quit"
            stdscr.addstr(max_y - 2, max(0, (max_x - len(footer)) // 2), footer)

            stdscr.refresh()

            # Handle keyboard input
            key = stdscr.getch()

            if key == curses.KEY_UP:
                selected_idx = (selected_idx - 1) % len(players)
            elif key == curses.KEY_DOWN:
                selected_idx = (selected_idx + 1) % len(players)
            elif key == ord("\n"):  # Enter key
                result = players[selected_idx]["id"]
                break
            elif key == ord("q"):
                result = None
                break

    finally:
        # Clean up curses properly
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    return result


def select_player(players: list[dict[str, str]]) -> str | None:
    """Display an interactive player selection menu, using either
    curses or text-based UI depending on environment.

    Args:
        players: List of player dictionaries with 'id' and 'name' keys

    Returns:
        Selected player ID or None if no selection was made
    """
    if not players:
        print("No players found", file=sys.stderr)
        return None

    print(f"DEBUG: Is TTY: {sys.stdout.isatty()}", file=sys.stderr)

    # Use curses UI if in TTY environment, otherwise fall back to text UI
    try:
        if sys.stdout.isatty():
            print("DEBUG: Using curses UI", file=sys.stderr)
            return curses_select_player(players)
        else:
            print("DEBUG: Using text UI (no TTY)", file=sys.stderr)
            return text_select_player(players)
    except Exception as e:
        print(f"Error displaying interactive menu: {e}", file=sys.stderr)
        # Fall back to text UI on errors
        print("DEBUG: Falling back to text UI due to error", file=sys.stderr)
        return text_select_player(players)
