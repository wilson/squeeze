# Keyboard Controls for Live Status Mode

This feature enhances the `squeeze status --live` command by adding keyboard controls:

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

## Requirements

The keyboard controls feature requires a terminal that supports raw input mode (most normal terminals do).

## How It Works

The implementation uses terminal raw mode to capture keystrokes without requiring the Enter key to be pressed. This allows for interactive control while the status display continuously updates.

- When you start `squeeze status --live`, the program will detect if keyboard controls are available in your terminal
- If available, it will display instructions for using the controls
- If not available, it will fall back to the standard behavior (Ctrl+C to exit)

## Limitations

- The feature requires a real TTY/terminal - it won't work when running through a non-interactive shell
- Some remote terminals or certain terminal emulators might not support all the required features
- Windows support depends on having the msvcrt module available

## Troubleshooting

If you encounter issues with keyboard controls:

1. If your terminal gets into a bad state (not showing input), try running: `reset`
2. Make sure you're running in an interactive terminal, not through a script or remote session
3. Verify that your terminal and environment support raw mode input

## Technical Details

The implementation:

- Uses `termios` and `tty` modules on Unix-like systems (macOS, Linux)
- Attempts to use `msvcrt` on Windows systems
- Automatically detects if these features are available and gracefully falls back
- Preserves all existing functionality when keyboard controls aren't available
