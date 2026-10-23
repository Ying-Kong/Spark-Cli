import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
import yaml

SPARK_HOME = os.environ.get("SPARK_HOME")
if not SPARK_HOME:
    click.secho("SPARK_HOME environment variable not found")
    sys.exit(1)

SEARCH_DIRS = [Path(SPARK_HOME) / "examples" / "jars", Path.cwd()]


def flatten_dict(d, parent_key="", sep=".") -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def resolve_jar(source_name: str) -> str:
    source_path = Path(source_name)
    # 提供绝对路径或当前目录存在的相对路径，直接引用
    if source_path.is_absolute() and source_path.exists():
        return str(source_path)
    if source_path.exists():
        return str(source_path.resolve())

    for search_dir in SEARCH_DIRS:
        target_file = search_dir / source_name
        if target_file.exists():
            click.secho(f"{search_dir}{source_name}", fg="blue")
            return str(target_file)

    click.secho(f"'{source_name}'", fg="red", bold=True)
    sys.exit(1)


def normalize_url(path_str: str) -> str:
    parsed = urlparse(path_str)
    if parsed.scheme:
        abs_path = Path(parsed.path).resolve()
        normalize = f"file://{abs_path}"
        return normalize
    return path_str


def spark_submit(cmd_list: list) -> None:
    cmd_str = " ".join(cmd_list)
    click.secho("\nsubmitting spark job", fg="cyan", bold=True)
    click.secho(f"{cmd_str}\n", fg="cyan")

    try:
        subprocess.run(cmd_list, check=True)
    except subprocess.CalledProcessError as e:
        click.secho(f"\n{e.returncode}\n", fg="red", bold=True)

        if any(str(arg).endswith(".py") for arg in cmd_list):
            diagnostic_document()
        sys.exit(e.returncode)
    except FileNotFoundError:
        click.secho("No spark-submit", fg="red", bold=True)
        sys.exit(1)


def diagnostic_document() -> None:
    doc = (
        "【版本兼容性硬性指标对照表】\n"
        "    ------------------------------------------------\n"
        "    | Spark 核心版本      | 官方支持的最高 Python 版本  |\n"
        "    ------------------------------------------------\n"
        "    | Spark 3.3.x 及以下 | Python 3.10              |\n"
        "    | Spark 3.4.x       | Python 3.11              |\n"
        "    | Spark 3.5.x 及以上 | Python 3.12              |\n"
        "    ------------------------------------------------\n"
        "\n"
        "\n"
        "   「由于当前集群未开启环境自动强行同步，请执行以下手动修复步骤」\n"
        "    1. 检查本地环境：执行 python --version 查看当前激活的 conda 环境。\n"
        "    2. 选择合适环境：查看正在使用的 Spark 版本，对应列表，请在当前 Conda 环境中执行：conda install python（对应版本）\n"
        "    3. 检查远程节点：请确保 YARN NodeManager 机器上的全局 Python 路径与本地保持绝对一致。"
    )
    click.secho(doc, fg="yellow")


# LOG4J_CATEGORY = "rootCategory"
# LOG4J_APPENDER = "console"
# LOG4J2_LEVEL_PROPERTY = "rootLogger.level"


# CLICK 路由层
@click.group()
@click.option(
    "--logs",
    default="WARN",
    show_default=True,
    type=click.Choice(["WARN", "INFO", "DEBUG", "ERROR"], case_sensitive=False),
    help="Logging level",
)
@click.option("--local", is_flag=True, help="Run in local mode (default: YARN)")
@click.pass_context
def cli(ctx, logs, local):
    ctx.ensure_object(dict)  # type: ignore
    ctx.obj["LOG_LEVEL"] = logs.lower()  # type: ignore
    ctx.obj["LOCAL_MODE"] = local  # type: ignore

    # Spark 的 YAML 配置文件必须位于 /home/user_name/.spark 的隐藏目录下，此处同理进行目录检查，无结果直接抛出错误
    config_path = Path.home() / ".spark" / "config.yaml"
    ctx.obj["YAML_ERROR"] = None  # type: ignore
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            ctx.obj["YAML_CONF"] = flatten_dict(config)  # type: ignore
        except (OSError, yaml.YAMLError, AttributeError, TypeError) as exc:
            # 结构非法的配置不应该以 traceback 收场。doctor / config 需要读得到这个
            # 错误才能报告它，其余命令直接失败，行为与之前一致（exit 1）。
            ctx.obj["YAML_CONF"] = {}  # type: ignore
            ctx.obj["YAML_ERROR"] = f"{config_path}: {exc}"  # type: ignore
            if ctx.invoked_subcommand not in ("doctor", "config"):
                click.secho(f"配置文件无法解析: {ctx.obj['YAML_ERROR']}", fg="red")  # type: ignore
                sys.exit(1)
    else:
        ctx.obj["YAML_CONF"] = {}  # type: ignore


@cli.command(name="run")
@click.argument("target", type=str)
@click.option("--main-class", "-c", type=str, help="主类名（仅在运行非官方示例的 JAR 包时需要）")
@click.argument("app_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run_cmd(ctx, target: str, main_class: str, app_args: tuple):
    """
    高度封装的通用执行接口。
    支持官方示例别名: pi.jar, pi.py, df.r
    也支持直接传入本地文件路径: /path/to/job.py
    """
    spark_home = Path(SPARK_HOME)  # type: ignore
    target_lower = target.lower().strip()
    log_level = ctx.obj["LOG_LEVEL"].upper()  # type: ignore
    driver_conf_logs = f"spark.driver.extraJavaOptions=-DLOG_LEVEL={log_level}"
    executor_conf_logs = f"spark.executor.extraJavaOptions=-DLOG_LEVEL={log_level}"
    master_val = "local[*]" if ctx.obj["LOCAL_MODE"] else "yarn"  # type: ignore

    cmd = [
        "spark-submit",
        "--master",
        master_val,
        "--conf",
        driver_conf_logs,
        "--conf",
        executor_conf_logs,
    ]
    for key, value in ctx.obj.get("YAML_CONF", {}).items():  # type: ignore
        cmd.extend(["--conf", f"{key}={value}"])

    target_file_path = ""
    is_jar = False

    # 检查是否为内置官方示例别名
    if target_lower in ["pi.jar"]:
        examples_dir = spark_home / "examples" / "jars"
        try:
            target_file_path = str(next(examples_dir.glob("spark-examples*.jar")))
        except StopIteration:
            click.secho(f"未找到 spark-examples.jar 包于 {examples_dir}", fg="red")
            sys.exit(1)
        cmd.extend(["--class", "org.apache.spark.examples.SparkPi"])
        is_jar = True  # noqa: F841

    elif target_lower == "pi.py":
        """
        进一步修改意见：
        1. LOCAL模式下，无需检查 Python 版本，或者检查也行，但 Yarn 模式运行，则必须检查所有 Nodemanager 的 Python 版本保持一致
        2. spark-3.3.0 最高指定 Python 3.10，spark-3.4.0以上才支持 Python 3.12，需给出显式文档
        """
        py_file = spark_home / "examples" / "src" / "main" / "python" / "pi.py"
        if not py_file.exists():
            click.secho(f"未找到 Python 示例文件: {py_file}", fg="red")
            sys.exit(1)
        target_file_path = str(py_file)

    elif target_lower in ["df.r"]:
        """
        进一步修改意见：
        1. 拼接、运行 dataframe.R 的示例前，必须检查本地有没有 $SPARK_HOME 下的 /examples/src/main/resource/people.json 文件（LOCAL模式）
        2. Yarn 模式下，必须检查 HDFS 上是否有 /home/user_name/spark/spark-*-bin.hadoop3/examples/src/main/resource 目录或者检查目录下有无文件，如没有，及时停止执行，并报错提示创建目录，上传文件
        3. 暂且只考虑此处，但判断为通用逻辑，后续提取为 def 函数 
        """
        r_file = spark_home / "examples" / "src" / "main" / "r" / "dataframe.R"  # 以 dataframe.R 作为 R 项目的示例包
        if not r_file.exists():
            click.secho(f"未找到 R 示例文件: {r_file}", fg="red")
            sys.exit(1)
        target_file_path = str(r_file)

    # 如果不是官方别名，走常规的本地脚本解析逻辑
    else:
        target_path = Path(target)
        if not target_path.exists():
            click.secho(f"错误: 目标文件或别名 '{target}' 不存在。", fg="red")
            sys.exit(1)

        target_file_path = str(target_path.resolve())
        file_ext = target_path.suffix.lower()

        if file_ext == ".jar":
            is_jar = True  # noqa: F841
            if not main_class:
                click.secho("错误: 运行自定义 JAR 包必须通过 -c 或 --main-class 指定主类名。", fg="red")
                sys.exit(1)
            cmd.extend(["--class", main_class])
        elif file_ext not in [".py", ".r"]:
            click.secho(f"错误: 不支持的文件类型 '{file_ext}'。", fg="red")
            sys.exit(1)

    cmd.append(target_file_path)
    if app_args:
        cmd.extend(list(app_args))

    # 执行提交
    spark_submit(cmd)


# --- v2 extensions -------------------------------------------------------
# Kept behind an import guard so `python cli.py` still works when only this
# file was copied. The v1 commands above are unaffected.
try:
    from sparkcli.extras import register as _register_extensions
except ImportError:  # pragma: no cover - standalone cli.py
    pass
else:
    _register_extensions(cli)
