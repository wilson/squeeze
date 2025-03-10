"""
Configuration module for Squeeze CLI.
"""

import os
from typing import Any

import tomli
import tomli_w

DEFAULT_CONFIG = {"server": {"url": "http://localhost:9000"}}


def get_config_path() -> str:
    """Get path to the config file.

    Returns:
        Path to the config file
    """
    return os.path.expanduser("~/.squeezerc")


def load_config() -> dict[str, Any]:
    """Load configuration from config file.

    Returns:
        Configuration dictionary
    """
    config_path = get_config_path()

    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_path, "rb") as f:
            return tomli.load(f)
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config file.

    Args:
        config: Configuration dictionary to save
    """
    config_path = get_config_path()

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)


def get_server_url(server_url: str | None = None) -> str:
    """Get server URL from config or provided value.

    Args:
        server_url: Server URL provided on command line

    Returns:
        Server URL to use
    """
    if server_url:
        return server_url

    config = load_config()
    server_config = config.get("server", {})
    if isinstance(server_config, dict):
        url = server_config.get("url")
        if isinstance(url, str):
            return url

    # Fall back to default config
    return DEFAULT_CONFIG["server"]["url"]
