"""`~/.spark/config.yaml` handling.

`flatten` mirrors `cli.flatten_dict` (which cannot be imported here without a
cycle). Tests assert both produce identical output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """The YAML file is unreadable or not a mapping."""


def config_path() -> Path:
    return Path.home() / ".spark" / "config.yaml"


def flatten(data: dict[str, Any], parent: str = "", sep: str = ".") -> dict[str, Any]:
    items: list[tuple[str, Any]] = []
    for key, value in data.items():
        new_key = f"{parent}{sep}{key}" if parent else key
        if isinstance(value, dict):
            items.extend(flatten(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        msg = f"{path}: {exc}"
        raise ConfigError(msg) from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        msg = f"{path}: expected a mapping at the top level"
        raise ConfigError(msg)
    return flatten(raw)
