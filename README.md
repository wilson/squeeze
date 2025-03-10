# Squeeze

A command-line utility for interacting with SqueezeBox players over the network.

## Installation

```bash
pip install -e .
```

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

## API Options

Squeeze supports two different APIs for communicating with the SqueezeBox server:

1. **JSON API** (default) - Uses the JSON-RPC API for cleaner and more reliable communication
2. **HTML API** (fallback) - Uses HTML scraping when JSON API is not available

You can control which API to use with these flags:
- `--json` - Force the use of JSON API
- `--no-json` - Force the use of HTML API

By default, Squeeze will auto-detect which API is available and use the JSON API if possible.

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

```bash
# Force interactive selection
squeeze status --interactive

# Just list players without interactive selection
squeeze status --no-interactive
```

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

Note: Square brackets `[]` indicate optional parameters. If omitted, you'll get an interactive player selection.

### JSON API Only Commands

The following commands require the JSON API:

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

This project requires Python 3.11 or higher.

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
- mypy for type checking (currently disabled in pre-commit hooks)

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