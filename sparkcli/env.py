"""Read-only probes of the local Spark installation."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from shutil import which


class EnvError(RuntimeError):
    """The Spark installation cannot be used."""


def spark_home() -> Path:
    raw = os.environ.get("SPARK_HOME", "").strip()
    if not raw:
        msg = "SPARK_HOME environment variable not found"
        raise EnvError(msg)
    return Path(raw)


def spark_submit_binary() -> str | None:
    return which("spark-submit")


def spark_version(home: Path) -> str | None:
    try:
        first = (home / "RELEASE").read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return None
    match = re.search(r"\d+\.\d+\.\d+", first)
    return match.group(0) if match else None


def python_version() -> str:
    info = sys.version_info
    return f"{info.major}.{info.minor}.{info.micro}"


def max_python_for(spark: str | None) -> str | None:
    """Return the highest Python a Spark release line officially supports."""
    if not spark:
        return None
    try:
        major, minor = (int(part) for part in spark.split(".")[:2])
    except (ValueError, StopIteration):
        return None
    if major >= 4 or minor >= 5:
        return "3.12"
    if minor == 4:
        return "3.11"
    return "3.10"


def python_supported(spark: str | None) -> bool:
    limit = max_python_for(spark)
    if limit is None:
        return True
    return sys.version_info.minor <= int(limit.split(".")[1])


def log_level_supported(home: Path) -> bool:
    """True when the cluster log4j2 template actually reads ${sys:LOG_LEVEL}."""
    try:
        text = (home / "conf" / "log4j2.properties").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "sys:LOG_LEVEL" in text
