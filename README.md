# Squeeze

A command-line utility for interacting with SqueezeBox players over the network.

## Installation

### Standard Installation
```bash
pip install -e .
```

### Installation on Raspberry Pi / piCorePlayer

piCorePlayer uses a minimal Linux distribution that may not have Python 3.11+ by default. Follow these steps to set up the environment:

1. First, connect to your piCorePlayer device via SSH:
   ```bash
   ssh tc@YOUR_PI_IP_ADDRESS
   ```

2. Install Python 3.11 using piCore's package manager:
   ```bash
   tce-load -wi python3.11
   ```

3. Ensure pip is installed:
   ```bash
   tce-load -wi python3.11-pip
   ```

4. Install the squeeze package:
   ```bash
   pip3 install git+https://github.com/wilson/squeeze.git
   ```

5. Make your changes persistent (so they survive reboots):
   ```bash
   filetool.sh -b
   ```

Note: If you encounter issues with Python version availability, you have a few options:

1. Use a virtual environment with a newer Python version
2. Use Docker to run squeeze in a container
3. For advanced users, you can modify the code to work with an earlier Python version (mainly by changing the type annotations and using `dict` instead of `dict[str, Any]` format)

## Configuration

Squeeze can be configured using a configuration file at `~/.squeezerc` in TOML format:

```toml
[server]
url = "http://your-squeezebox-server:9000"
```

You can set the server URL using the command:

```bash
squeeze config --set-server "http://your-squeezebox-server:9000"
```

## API

Squeeze uses the SqueezeBox server's JSON-RPC API for clean and reliable communication.

## Usage

### List Available Players

```bash
squeeze players
```

### Get Player Status

```bash
squeeze status [player_id]
```

If no player ID is provided, the command will display an interactive selection menu to choose a player. All commands that require a player ID support this feature.

You can control the interactive behavior:
- `--interactive`: Force interactive mode (default when player ID is not provided)
- `--no-interactive`: Disable interactive mode (will just list players if no ID provided)
- `--live`: Show continuously updated live status with keyboard controls

```bash
# Force interactive selection
squeeze status --interactive

# Just list players without interactive selection
squeeze status --no-interactive

# Live status mode with real-time updates and keyboard controls
squeeze status --live
```

#### Live Status Mode

The `--live` flag activates an enhanced display mode with:
- Real-time status updates
- Rich, formatted terminal UI
- Keyboard controls for common playback functions

| Key           | Action                         |
|---------------|--------------------------------|
| ←  (Left) / p | Previous track or restart track|
| →  (Right) / n| Next track                     |
| ↑  (Up) / +   | Volume up (5%)                 |
| ↓  (Down) / - | Volume down (5%)               |
| v             | Reset volume (special devices) |
| q             | Quit live mode                 |

**Notes**:
- Left arrow/p will restart the current track if more than 5 seconds have elapsed, otherwise it will go to the previous track.
- Volume controls (Up/Down/+/-) will only work for devices that support server-controlled volume.
- The 'v' key is only shown for devices that may have external volume control.

### Player Control

Play:
```bash
squeeze play [player_id]
```

Pause:
```bash
squeeze pause [player_id]
```

Stop:
```bash
squeeze stop [player_id]
```

Set volume:
```bash
squeeze volume <0-100> [player_id]
```

Power on/off:
```bash
squeeze power on [player_id]
squeeze power off [player_id]
```

Shuffle mode:
```bash
# Set a specific shuffle mode
squeeze shuffle off [player_id]
squeeze shuffle songs [player_id]
squeeze shuffle albums [player_id]

# Cycle through shuffle modes (off -> songs -> albums -> off)
squeeze shuffle [player_id]
```

Repeat mode:
```bash
# Set a specific repeat mode
squeeze repeat off [player_id]
squeeze repeat one [player_id]
squeeze repeat all [player_id]

# Cycle through repeat modes (off -> all -> one -> off)
squeeze repeat [player_id]
```

Now Playing screen:
```bash
# Activate the Now Playing screen (like pressing the 'Now Playing' button on the remote)
squeeze now [player_id]
```

Remote control navigation:
```bash
# Arrow buttons
squeeze remote up [player_id]
squeeze remote down [player_id]
squeeze remote left [player_id]
squeeze remote right [player_id]

# Select/OK button
squeeze remote select [player_id]

# Browse music library
squeeze remote browse [player_id]
```

Note: Square brackets `[]` indicate optional parameters. If omitted, you'll get an interactive player selection.

### Additional Commands

Search for music:
```bash
squeeze search "search term"
squeeze search --type artists "Beatles"
squeeze search --type albums "Abbey Road"
squeeze search --type tracks "Yesterday"
```

Get server status:
```bash
squeeze server
```

## Development

This project requires Python 3.11 or higher and has the following dependencies:
- tomli-w: For TOML file handling
- rich: For enhanced terminal UI in live status mode

### Platform-Specific Notes

#### Raspberry Pi / piCorePlayer

- piCorePlayer is designed to be minimalist, so it may not have all dependencies by default
- Python packages installed with pip may not persist across reboots unless you run `filetool.sh -b`
- For performance reasons, consider setting up a lightweight caching mechanism if you're polling server status frequently
- Terminal capabilities may be limited, so certain UI features might not work as expected

### Version History

- v0.3.0:
  - Breaking changes:
    - Removed HTML API support, now exclusively uses JSON API
    - Simplified client factory to only create JSON clients
  - Benefits:
    - Reduced code complexity
    - More consistent behavior

- v0.2.0:
  - Added new commands:
    - `shuffle` - Control shuffle mode (off/songs/albums)
    - `repeat` - Control repeat mode (off/one/all)
    - `now` - Show Now Playing screen
    - `remote` - Send remote control button presses (up/down/left/right/select)
  - Breaking changes:
    - Removed backward compatibility layer (`client.py`)
    - Direct imports from `squeeze.client` should be changed to `squeeze.html_client`
    - Renamed `SqueezeClient` to `SqueezeHtmlClient` for clarity
  - Added pre-commit hooks for code quality (black, isort, ruff, mypy)

- v0.1.0 - Initial release

### Code Style and Linting

We use pre-commit hooks to maintain code quality. To set up the pre-commit hooks, run:

```bash
pip install pre-commit
pre-commit install
```

The pre-commit hooks enforce:
- Black for code formatting
- isort for import sorting
- ruff for linting
- mypy for type checking

You can manually run all checks with:

```bash
pre-commit run --all-files
```

Or check specific files:

```bash
pre-commit run --files file1.py file2.py
```

## License

MIT
