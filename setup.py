#!/usr/bin/env python3
"""Setup script for the Squeeze package."""

import re

from setuptools import find_packages, setup

# Get the version from __init__.py to avoid duplication
with open("squeeze/__init__.py", encoding="utf-8") as f:
    version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', f.read())
    if not version_match:
        raise RuntimeError("Version string not found in __init__.py")
    VERSION = version_match.group(1)

setup(
    name="squeeze",
    version=VERSION,
    description="CLI for interacting with SqueezeBox players over the network",
    author="Wilson Bilkovich",
    author_email="wilsonb@gmail.com",
    url="https://github.com/wilson/squeeze",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "squeeze=squeeze.cli.main:main",
        ],
    },
    install_requires=[
        "tomli>=2.0.0",
        "tomli-w>=1.0.0",
        # curses is part of the standard library for most Python installations
    ],
    package_data={
        "squeeze": ["py.typed"],  # Indicate the package is typed
        "tests": ["py.typed"],  # Also mark tests as typed
    },
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=6.0.0",
            "pytest-mypy>=0.10.0",
            "black",
            "isort",
            "mypy",
            "ruff",
            "types-setuptools",
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Topic :: Utilities",
    ],
)
