"""The v2 commands, registered onto the frozen v1 Click group."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import click

from . import config as config_mod
from . import env
from .submit import SubmitSpec, build_argv
from .targets import TargetError


def _history_path() -> Path:
    return Path.home() / ".spark" / "history.jsonl"


def _record(argv: list[str], code: int, seconds: float) -> None:
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"argv": argv, "returncode": code, "seconds": round(seconds, 2)}) + "\n")
    except OSError:
        pass  # history is a convenience, never a reason to fail a submission


def _status(tag: str, name: str, detail: str) -> None:
    color = {"ok": "green", "warn": "yellow", "fail": "red"}[tag]
    click.secho(f"[{tag:<4}] ", fg=color, nl=False, bold=True)
    click.secho(f"{name:<16} ", nl=False, bold=True)
    click.echo(detail)


def _submission_options(func):
    for option in reversed(
        [
            click.option("--main-class", "-c", default=None, help="主类名，仅 .jar 需要"),
            click.option("--deploy-mode", type=click.Choice(["client", "cluster"]), default=None),
            click.option("--num-executors", default=None, help="YARN executor 数量"),
            click.option("--driver-memory", default=None, help="例如 2g"),
            click.option("--jars", default=None, help="逗号分隔的额外 jar"),
            click.option("--files", default=None, help="逗号分隔的额外文件"),
            click.option("--conf", "conf_extra", multiple=True, metavar="KEY=VALUE", help="额外 Spark 配置，可重复"),
        ]
    ):
        func = option(func)
    return func


def _make_spec(ctx, target, app_args, main_class, deploy_mode, num_executors, driver_memory, jars, files, conf_extra):
    conf = dict(ctx.obj.get("YAML_CONF", {}))
    for item in conf_extra:
        if "=" not in item:
            msg = f"--conf 需要 KEY=VALUE 形式: {item}"
            raise click.BadParameter(msg)
        key, value = item.split("=", 1)
        conf[key] = value
    return SubmitSpec(
        target=target,
        conf=conf,
        local=bool(ctx.obj.get("LOCAL_MODE")),
        logs=str(ctx.obj.get("LOG_LEVEL", "warn")),
        main_class=main_class,
        app_args=tuple(app_args),
        deploy_mode=deploy_mode,
        num_executors=num_executors,
        driver_memory=driver_memory,
        jars=jars,
        files=files,
    )


@click.command(name="plan")
@click.argument("target")
@_submission_options
@click.argument("app_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def plan_cmd(ctx, target, app_args, main_class, deploy_mode, num_executors, driver_memory, jars, files, conf_extra):
    """只打印将要执行的 spark-submit 命令，不执行。"""
    try:
        argv = build_argv(
            _make_spec(
                ctx, target, app_args, main_class, deploy_mode, num_executors, driver_memory, jars, files, conf_extra
            ),
            env.spark_home(),
        )
    except (env.EnvError, TargetError) as exc:
        click.secho(str(exc), fg="red", err=True)
        sys.exit(1)
    click.echo(" ".join(argv))


@click.command(name="submit")
@click.argument("target")
@_submission_options
@click.argument("app_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def submit_cmd(ctx, target, app_args, main_class, deploy_mode, num_executors, driver_memory, jars, files, conf_extra):
    """提交作业，支持 --deploy-mode / --jars 等 v1 未封装的参数。"""
    try:
        argv = build_argv(
            _make_spec(
                ctx, target, app_args, main_class, deploy_mode, num_executors, driver_memory, jars, files, conf_extra
            ),
            env.spark_home(),
        )
    except (env.EnvError, TargetError) as exc:
        click.secho(str(exc), fg="red", err=True)
        sys.exit(1)

    click.secho("\nsubmitting spark job", fg="cyan", bold=True)
    click.secho(f"{' '.join(argv)}\n", fg="cyan")
    started = time.time()
    try:
        completed = subprocess.run(argv, check=False)
    except FileNotFoundError:
        click.secho("No spark-submit", fg="red", bold=True)
        sys.exit(1)
    code = completed.returncode
    _record(argv, code, time.time() - started)
    sys.exit(code)


@click.command(name="doctor")
def doctor_cmd():
    """检查本地 Spark 环境是否具备运行条件。"""
    healthy = True
    home: Path | None = None

    raw = os.environ.get("SPARK_HOME", "").strip()
    if not raw:
        _status("fail", "SPARK_HOME", "not set")
        healthy = False
    elif not Path(raw).is_dir():
        _status("fail", "SPARK_HOME", f"{raw} is not a directory")
        healthy = False
    else:
        home = Path(raw)
        _status("ok", "SPARK_HOME", str(home))

    binary = env.spark_submit_binary()
    if binary:
        _status("ok", "spark-submit", binary)
    else:
        _status("fail", "spark-submit", "not on PATH")
        healthy = False

    version = env.spark_version(home) if home else None
    if version:
        _status("ok", "Spark version", version)
    else:
        _status("warn", "Spark version", "unknown (no RELEASE file)")

    limit = env.max_python_for(version)
    current = env.python_version()
    if limit and not env.python_supported(version):
        _status("warn", "Python", f"{current} (Spark {version} supports up to {limit})")
    else:
        _status("ok", "Python", current if not limit else f"{current} (<= {limit})")

    if home and env.log_level_supported(home):
        _status("ok", "log4j2 LOG_LEVEL", "supported by conf/log4j2.properties")
    else:
        _status("warn", "log4j2 LOG_LEVEL", "not read by the cluster template; --logs will be ignored")

    try:
        conf = config_mod.load()
    except config_mod.ConfigError as exc:
        _status("fail", "config.yaml", str(exc))
        healthy = False
    else:
        location = config_mod.config_path()
        if conf:
            _status("ok", "config.yaml", f"{location} ({len(conf)} keys)")
        else:
            _status("ok", "config.yaml", f"{location} (absent, no --conf injected)")

    sys.exit(0 if healthy else 1)


@click.group(name="config")
def config_group():
    """查看或校验 ~/.spark/config.yaml。"""


@config_group.command("show")
def config_show():
    """打印拍平后的配置键值。"""
    path = config_mod.config_path()
    try:
        conf = config_mod.load()
    except config_mod.ConfigError as exc:
        click.secho(str(exc), fg="red", err=True)
        sys.exit(1)
    click.secho(f"# {path}", fg="cyan")
    for key, value in conf.items():
        click.echo(f"{key}={value}")


@config_group.command("validate")
def config_validate():
    """校验 YAML 语法与结构。"""
    path = config_mod.config_path()
    try:
        conf = config_mod.load()
    except config_mod.ConfigError as exc:
        click.secho(f"[fail] {exc}", fg="red")
        sys.exit(1)
    click.secho(f"[ok]   {path} is valid ({len(conf)} keys)", fg="green")


@click.command(name="history")
@click.option("--limit", default=10, show_default=True, help="显示最近多少条")
def history_cmd(limit: int):
    """查看由 `submit` 记录的提交历史。"""
    path = _history_path()
    if not path.exists():
        click.secho("(无历史记录，submit 之后才会写入)", fg="yellow")
        return
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        code = entry.get("returncode")
        seconds = entry.get("seconds")
        argv = " ".join(entry.get("argv", []))
        click.echo(f"exit={code:<3} {seconds:>6}s  {argv}")


def register(group: click.Group) -> None:
    """Attach the v2 commands to the existing v1 group."""
    group.add_command(plan_cmd)
    group.add_command(submit_cmd)
    group.add_command(doctor_cmd)
    group.add_command(config_group)
    group.add_command(history_cmd)
