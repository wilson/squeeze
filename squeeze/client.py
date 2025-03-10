"""
SqueezeBox client library for interacting with SqueezeBox server.

This module is provided for backward compatibility only.
New code should import from squeeze.html_client or squeeze.json_client directly.

DEPRECATED: This module will be removed in a future version.
"""

import warnings

from squeeze.html_client import SqueezeHtmlClient

# Display deprecation warning
warnings.warn(
    "squeeze.client is deprecated. Use html_client or json_client instead.",
    DeprecationWarning,
    stacklevel=2,
)

# For backwards compatibility, alias SqueezeHtmlClient as SqueezeClient
SqueezeClient = SqueezeHtmlClient
