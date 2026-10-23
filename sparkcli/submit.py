"""Build the `spark-submit` argv. Pure: no I/O, no process spawning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .targets import resolve


@dataclass(frozen=True)
class SubmitSpec:
    target: str
    conf: Mapping[str, object] = field(default_factory=dict)
    local: bool = False
    logs: str = "WARN"
    main_class: str | None = None
    app_args: Sequence[str] = ()
    deploy_mode: str | None = None
    num_executors: str | None = None
    driver_memory: str | None = None
    jars: str | None = None
    files: str | None = None


def build_argv(spec: SubmitSpec, home: Path) -> list[str]:
    """Return the argv a v1 `run` with the same inputs would produce."""
    level = spec.logs.upper()
    argv = [
        "spark-submit",
        "--master",
        "local[*]" if spec.local else "yarn",
        "--conf",
        f"spark.driver.extraJavaOptions=-DLOG_LEVEL={level}",
        "--conf",
        f"spark.executor.extraJavaOptions=-DLOG_LEVEL={level}",
    ]
    for key, value in spec.conf.items():
        argv.extend(["--conf", f"{key}={value}"])
    if spec.deploy_mode:
        argv.extend(["--deploy-mode", spec.deploy_mode])
    if spec.num_executors:
        argv.extend(["--num-executors", spec.num_executors])
    if spec.driver_memory:
        argv.extend(["--driver-memory", spec.driver_memory])
    if spec.jars:
        argv.extend(["--jars", spec.jars])
    if spec.files:
        argv.extend(["--files", spec.files])

    resolved = resolve(spec.target, home, main_class=spec.main_class)
    if resolved.is_jar and resolved.main_class:
        argv.extend(["--class", resolved.main_class])
    argv.append(resolved.path)
    argv.extend(spec.app_args)
    return argv
