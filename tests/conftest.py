"""Shared fixtures for the spark-cli contract suite.

The suite is intentionally minimal: it does not import `pytest-click` or any
third-party helper, so it runs on a bare `python -m pytest` install.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXAMPLE_JAR_NAME = "spark-examples_2.12-3.3.0.jar"


@pytest.fixture()
def spark_home(tmp_path: Path) -> Path:
    """A minimal $SPARK_HOME with the three files cli.py knows how to alias."""
    home = tmp_path / "spark"
    (home / "examples" / "jars").mkdir(parents=True)
    (home / "examples" / "jars" / EXAMPLE_JAR_NAME).write_text("")
    (home / "examples" / "src" / "main" / "python").mkdir(parents=True)
    (home / "examples" / "src" / "main" / "python" / "pi.py").write_text("")
    (home / "examples" / "src" / "main" / "r").mkdir(parents=True)
    (home / "examples" / "src" / "main" / "r" / "dataframe.R").write_text("")
    return home


@pytest.fixture()
def user_home(tmp_path: Path) -> Path:
    """An isolated $HOME whose ~/.spark/config.yaml can be created per test."""
    home = tmp_path / "home"
    (home / ".spark").mkdir(parents=True)
    return home


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    return work


@pytest.fixture()
def cli_module(spark_home, user_home, workdir, monkeypatch):
    """Import `cli` fresh so module-level SPARK_HOME/SEARCH_DIRS pick up the fixture."""
    monkeypatch.setenv("SPARK_HOME", str(spark_home))
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.chdir(workdir)
    sys.modules.pop("cli", None)
    import cli as module  # noqa: PLC0415 - deliberate late import

    return module


@pytest.fixture()
def recorded(cli_module, monkeypatch) -> list[list[str]]:
    """Replace subprocess.run with a recorder; nothing is ever executed."""
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    return calls


def invoke(cli_module, args: list[str]):
    from click.testing import CliRunner

    return CliRunner().invoke(cli_module.cli, args, catch_exceptions=False)
