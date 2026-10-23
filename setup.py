"""Shim kept for tooling that still calls `python setup.py`.

All metadata lives in pyproject.toml (PEP 621).
"""

from setuptools import setup

setup()
