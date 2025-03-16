"""
Exception classes for Squeeze.
"""


class SqueezeError(Exception):
    """Base class for Squeeze errors."""

    def __init__(self, message: str, code: int = 0) -> None:
        self.message = message
        self.code = code
        super().__init__(message)

    def __str__(self) -> str:
        if self.code:
            return f"Error {self.code}: {self.message}"
        return self.message


class ConnectionError(SqueezeError):
    """Raised when a connection to the server fails."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message, code)


class APIError(SqueezeError):
    """Raised when an API request fails."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message, code)


class CommandError(SqueezeError):
    """Raised when a command fails to execute."""

    def __init__(self, message: str, command: str = "", code: int = 3):
        self.command = command
        error_msg = f"Command '{command}' failed: {message}" if command else message
        super().__init__(error_msg, code)


class PlayerNotFoundError(SqueezeError):
    """Raised when a player is not found."""

    def __init__(self, player_id: str = "", code: int = 4):
        message = f"Player not found: {player_id}" if player_id else "Player not found"
        super().__init__(message, code)


class ParseError(SqueezeError):
    """Raised when response parsing fails."""

    def __init__(self, message: str, code: int = 5):
        super().__init__(message, code)


class ConfigError(SqueezeError):
    """Raised when there's a configuration error."""

    def __init__(self, message: str, code: int = 6):
        super().__init__(message, code)
