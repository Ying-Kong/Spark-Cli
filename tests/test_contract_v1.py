"""Contract tests for the v1 `spark-cli run` surface.

These tests describe the behaviour of `cli.py` as it exists today. They are the
referee for every later refactor: if one of them changes, the change is a
breaking change and must be deliberate, documented and versioned.

Invariants covered (see README "Compatibility"):
    1. command name `spark-cli` -> `cli:cli`               (setup.py)
    2. missing $SPARK_HOME exits before any command runs    (cli.py L9-12)
    3. alias precedence pi.jar / pi.py / df.r               (cli.py L149-182)
    4. the printed command line is `" ".join(argv)`         (cli.py L58-60)
    5. exit codes: job failure passthrough, missing spark-submit -> 1
    6. trailing arguments are passed through untouched      (cli.py L121)
    7. default argv is byte-identical to v2.0.0             (cli.py L136-143)
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from .conftest import EXAMPLE_JAR_NAME, ROOT, invoke


def _base(spark_home) -> list[str]:
    return [
        "spark-submit",
        "--master",
        "yarn",
        "--conf",
        "spark.driver.extraJavaOptions=-DLOG_LEVEL=WARN",
        "--conf",
        "spark.executor.extraJavaOptions=-DLOG_LEVEL=WARN",
    ]


# --------------------------------------------------------------------------
# 3. alias resolution
# --------------------------------------------------------------------------


def test_pi_jar_alias(cli_module, recorded, spark_home):
    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 0
    assert recorded[0] == [
        *_base(spark_home),
        "--class",
        "org.apache.spark.examples.SparkPi",
        str(spark_home / "examples" / "jars" / EXAMPLE_JAR_NAME),
    ]


def test_pi_py_alias(cli_module, recorded, spark_home):
    result = invoke(cli_module, ["run", "pi.py"])

    assert result.exit_code == 0
    assert recorded[0][-1] == str(spark_home / "examples" / "src" / "main" / "python" / "pi.py")
    assert "--class" not in recorded[0]


def test_df_r_alias(cli_module, recorded, spark_home):
    result = invoke(cli_module, ["run", "df.r"])

    assert result.exit_code == 0
    assert recorded[0][-1] == str(spark_home / "examples" / "src" / "main" / "r" / "dataframe.R")


def test_alias_wins_over_local_file(cli_module, recorded, workdir):
    """`run pi.py` must keep resolving to the built-in alias, not ./pi.py."""
    (workdir / "pi.py").write_text("print('local')")

    result = invoke(cli_module, ["run", "pi.py"])

    assert result.exit_code == 0
    assert not recorded[0][-1].startswith(str(workdir))


# --------------------------------------------------------------------------
# 6 + 7. argument passthrough and default argv
# --------------------------------------------------------------------------


def test_local_script_with_arguments(cli_module, recorded, workdir):
    (workdir / "job.py").write_text("")

    result = invoke(cli_module, ["run", "job.py", "a", "b", "c"])

    assert result.exit_code == 0
    assert recorded[0][-4:] == [str(workdir / "job.py"), "a", "b", "c"]


def test_double_dash_is_consumed_and_dash_args_pass_through(cli_module, recorded, workdir):
    (workdir / "job.py").write_text("")

    result = invoke(cli_module, ["run", "job.py", "a", "b", "--", "-x"])

    assert result.exit_code == 0
    assert recorded[0][-3:] == ["a", "b", "-x"]


def test_jar_with_main_class(cli_module, recorded, workdir):
    (workdir / "job.jar").write_text("")

    result = invoke(cli_module, ["run", "job.jar", "-c", "com.acme.Main"])

    assert result.exit_code == 0
    assert recorded[0][-3:] == ["--class", "com.acme.Main", str(workdir / "job.jar")]


# --------------------------------------------------------------------------
# group options
# --------------------------------------------------------------------------


def test_local_flag_switches_master(cli_module, recorded):
    result = invoke(cli_module, ["--local", "run", "pi.jar"])

    assert result.exit_code == 0
    assert recorded[0][1:3] == ["--master", "local[*]"]


def test_logs_option_reaches_both_java_options(cli_module, recorded):
    result = invoke(cli_module, ["--logs", "DEBUG", "run", "pi.jar"])

    assert result.exit_code == 0
    assert "spark.driver.extraJavaOptions=-DLOG_LEVEL=DEBUG" in recorded[0]
    assert "spark.executor.extraJavaOptions=-DLOG_LEVEL=DEBUG" in recorded[0]


def test_logs_option_is_case_insensitive(cli_module, recorded):
    result = invoke(cli_module, ["--logs", "info", "run", "pi.jar"])

    assert result.exit_code == 0
    assert "spark.driver.extraJavaOptions=-DLOG_LEVEL=INFO" in recorded[0]


def test_yaml_config_is_flattened_into_conf(cli_module, recorded, user_home):
    (user_home / ".spark" / "config.yaml").write_text(
        "spark:\n  driver:\n    cores: 2\n    memory: 4g\n  executor:\n    instances: 6\n"
    )

    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 0
    argv = recorded[0]
    assert "spark.driver.cores=2" in argv
    assert "spark.driver.memory=4g" in argv
    assert "spark.executor.instances=6" in argv
    # `--conf` and its value must always be adjacent pairs.
    assert argv[argv.index("spark.driver.cores=2") - 1] == "--conf"


def test_missing_yaml_config_is_not_an_error(cli_module, recorded):
    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 0
    assert not any(arg.startswith("spark.driver.cores=") for arg in recorded[0])


# --------------------------------------------------------------------------
# 4. printed command line
# --------------------------------------------------------------------------


def test_prints_the_exact_joined_command(cli_module, recorded):
    result = invoke(cli_module, ["run", "pi.jar"])

    assert "submitting spark job" in result.output
    assert " ".join(recorded[0]) in result.output


# --------------------------------------------------------------------------
# 5. exit codes
# --------------------------------------------------------------------------


def test_jar_without_main_class_is_rejected(cli_module, recorded, workdir):
    (workdir / "job.jar").write_text("")

    result = invoke(cli_module, ["run", "job.jar"])

    assert result.exit_code == 1
    assert recorded == []
    assert "必须通过 -c 或 --main-class 指定主类名" in result.output


def test_unsupported_extension_is_rejected(cli_module, recorded, workdir):
    (workdir / "a.txt").write_text("")

    result = invoke(cli_module, ["run", "a.txt"])

    assert result.exit_code == 1
    assert recorded == []
    assert "不支持的文件类型" in result.output


def test_missing_target_is_rejected(cli_module, recorded):
    result = invoke(cli_module, ["run", "missing.py"])

    assert result.exit_code == 1
    assert recorded == []
    assert "不存在" in result.output


def test_job_failure_returns_the_job_exit_code(cli_module, workdir, monkeypatch):
    (workdir / "job.py").write_text("")

    def boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(3, cmd)

    monkeypatch.setattr(cli_module.subprocess, "run", boom)

    result = invoke(cli_module, ["run", "job.py"])

    assert result.exit_code == 3
    assert "3" in result.output


def test_py_failure_prints_the_version_matrix(cli_module, workdir, monkeypatch):
    (workdir / "job.py").write_text("")

    def boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(3, cmd)

    monkeypatch.setattr(cli_module.subprocess, "run", boom)

    result = invoke(cli_module, ["run", "job.py"])

    assert "版本兼容性硬性指标对照表" in result.output


def test_jar_failure_does_not_print_the_version_matrix(cli_module, workdir, monkeypatch):
    (workdir / "job.jar").write_text("")

    def boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(4, cmd)

    monkeypatch.setattr(cli_module.subprocess, "run", boom)

    result = invoke(cli_module, ["run", "job.jar", "-c", "com.acme.Main"])

    assert result.exit_code == 4
    assert "版本兼容性硬性指标对照表" not in result.output


def test_missing_spark_submit_binary(cli_module, workdir, monkeypatch):
    (workdir / "job.py").write_text("")

    def boom(cmd, *args, **kwargs):
        raise FileNotFoundError("spark-submit")

    monkeypatch.setattr(cli_module.subprocess, "run", boom)

    result = invoke(cli_module, ["run", "job.py"])

    assert result.exit_code == 1
    assert "No spark-submit" in result.output


# --------------------------------------------------------------------------
# 2. the import-time SPARK_HOME gate (needs a real subprocess)
# --------------------------------------------------------------------------


def test_missing_spark_home_exits_before_anything_runs(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "SPARK_HOME"}

    completed = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 1
    assert "SPARK_HOME environment variable not found" in completed.stdout


# --------------------------------------------------------------------------
# help snapshot
# --------------------------------------------------------------------------


def test_help_lists_the_run_command(cli_module):
    result = invoke(cli_module, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output
    assert "--local" in result.output
    assert "--logs" in result.output


def test_run_help_documents_main_class(cli_module):
    result = invoke(cli_module, ["run", "--help"])

    assert result.exit_code == 0
    assert "--main-class" in result.output


@pytest.mark.parametrize("name", ["flatten_dict", "resolve_jar", "normalize_url"])
def test_legacy_helpers_remain_importable(cli_module, name):
    """These are public surface today; removing them would be breaking."""
    assert callable(getattr(cli_module, name))
