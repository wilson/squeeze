# Keyboard Controls for Live Status Mode

This feature enhances the `squeeze status --live` command by adding keyboard controls and a rich terminal UI:

- **Left/Right arrows**: Navigate between tracks (previous/next)
- **Up/Down arrows**: Adjust volume (up/down by 5%)
- **Q key**: Quit live mode

## Usage

When using `squeeze status --live`, you can control your player with keyboard shortcuts:

| Key           | Action                         |
|---------------|--------------------------------|
| ←  (Left)     | Previous track or restart track|
| →  (Right)    | Next track                     |
| ↑  (Up)       | Volume up (5%)                 |
| ↓  (Down)     | Volume down (5%)               |
| q             | Quit live mode                 |

**Note**: Left arrow will restart the current track if more than 5 seconds have elapsed, otherwise it will go to the previous track.

## New Features

The live mode display has been completely reimplemented with:

- Improved layout with separate panels for player info and track details
- Real-time progress bar showing track position
- Consistent formatting across terminal types
- Better error handling and recovery
- More reliable keyboard input detection
- Proper terminal cleanup when exiting

## Requirements

The keyboard controls feature requires:
- A terminal that supports raw input mode (most normal terminals do)
- The Rich library, which is automatically installed as a dependency

## How It Works

The implementation now uses the Rich library to create a well-formatted terminal UI with panels, tables, and progress bars. For keyboard input, it continues to use platform-specific methods:

- On Unix/Linux/macOS: Uses termios and tty modules for raw terminal mode
- On Windows: Uses the msvcrt module for direct console input
- Fallback to basic mode if advanced input methods aren't available

## Limitations

- The feature requires a real TTY/terminal - it won't work when running through a non-interactive shell
- Some remote terminals or certain terminal emulators might display the UI differently
- Terminal color support varies across environments

## Troubleshooting

If you encounter issues with keyboard controls:

1. If your terminal gets into a bad state, try running: `reset`
2. Make sure you're running in an interactive terminal, not through a script
3. Update to the latest version of the Rich library (`pip install --upgrade rich`)
4. Try using a different terminal emulator if possible
5. If all else fails, use the standard mode without `--live` flag
