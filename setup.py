#!/usr/bin/env python3
"""Setup script for the Squeeze package."""

from setuptools import find_packages, setup

# Use a static version instead of importing from the package
VERSION = "0.2.0"

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
