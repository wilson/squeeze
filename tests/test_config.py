"""Tests for the configuration module."""

import os
import tempfile
from unittest.mock import mock_open, patch

import tomli_w

from squeeze.config import (
    DEFAULT_CONFIG,
    get_config_path,
    get_server_url,
    load_config,
    save_config,
)


class TestConfig:
    """Tests for the configuration module."""

    def test_get_config_path(self) -> None:
        """Test getting the config file path."""
        with patch("os.path.expanduser") as mock_expanduser:
            mock_expanduser.return_value = "/fake/home/.squeezerc"
            config_path = get_config_path()
            assert config_path == "/fake/home/.squeezerc"
            mock_expanduser.assert_called_once_with("~/.squeezerc")

    def test_load_config_not_exists(self) -> None:
        """Test loading config when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            config = load_config()
            assert config == DEFAULT_CONFIG

    def test_load_config_exists(self) -> None:
        """Test loading config when file exists."""
        test_config = {"server": {"url": "http://example.com:9000"}}
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            try:
                # Write test config to temp file
                tomli_w.dump(test_config, temp_file)
                temp_file.flush()
                temp_file.close()

                # Patch get_config_path to return our temp file
                with patch(
                    "squeeze.config.get_config_path", return_value=temp_file.name
                ):
                    config = load_config()
                    assert config == test_config
            finally:
                # Clean up
                os.unlink(temp_file.name)

    def test_load_config_invalid(self) -> None:
        """Test loading config when file is invalid."""
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=b"invalid toml")),
        ):
            config = load_config()
            assert config == DEFAULT_CONFIG

    def test_save_config(self) -> None:
        """Test saving configuration."""
        test_config = {"server": {"url": "http://example.com:9000"}}
        mock_file = mock_open()
        with (
            patch(
                "squeeze.config.get_config_path", return_value="/fake/path/.squeezerc"
            ),
            patch("builtins.open", mock_file),
            patch("tomli_w.dump") as mock_dump,
        ):
            save_config(test_config)
            mock_file.assert_called_once_with("/fake/path/.squeezerc", "wb")
            mock_dump.assert_called_once()
            assert mock_dump.call_args[0][0] == test_config

    def test_get_server_url_provided(self) -> None:
        """Test getting server URL when explicitly provided."""
        url = get_server_url("http://test-server:9000")
        assert url == "http://test-server:9000"

    def test_get_server_url_from_config(self) -> None:
        """Test getting server URL from config."""
        test_config = {"server": {"url": "http://config-server:9000"}}
        with patch("squeeze.config.load_config", return_value=test_config):
            url = get_server_url()
            assert url == "http://config-server:9000"

    def test_get_server_url_missing_url(self) -> None:
        """Test getting server URL when url is missing from config."""
        test_config: dict[str, dict[str, str]] = {"server": {}}  # Missing url key
        with patch("squeeze.config.load_config", return_value=test_config):
            url = get_server_url()
            assert url == DEFAULT_CONFIG["server"]["url"]

    def test_get_server_url_missing_server(self) -> None:
        """Test getting server URL when server section is missing from config."""
        test_config: dict[str, dict[str, str]] = {}  # Missing server section
        with patch("squeeze.config.load_config", return_value=test_config):
            url = get_server_url()
            assert url == DEFAULT_CONFIG["server"]["url"]

    def test_get_server_url_invalid_server_type(self) -> None:
        """Test getting server URL when server is not a dict in config."""
        test_config = {"server": "not-a-dict"}  # Server is not a dict
        with patch("squeeze.config.load_config", return_value=test_config):
            url = get_server_url()
            assert url == DEFAULT_CONFIG["server"]["url"]

    def test_get_server_url_invalid_url_type(self) -> None:
        """Test getting server URL when url is not a string in config."""
        test_config = {"server": {"url": 123}}  # url is not a string
        with patch("squeeze.config.load_config", return_value=test_config):
            url = get_server_url()
            assert url == DEFAULT_CONFIG["server"]["url"]
