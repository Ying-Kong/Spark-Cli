"""Tests for the v2 commands added on top of the frozen v1 surface."""

from __future__ import annotations

import json
import subprocess

import pytest

from sparkcli import config as config_mod
from sparkcli.submit import SubmitSpec, build_argv

from .conftest import invoke


def _v1_argv(cli_module, recorded, args):
    result = invoke(cli_module, args)
    assert result.exit_code == 0, result.output
    assert len(recorded) == 1
    return recorded[0]


def _v2_argv(home, **kwargs):
    return build_argv(SubmitSpec(**kwargs), home)


# --------------------------------------------------------------------------
# differential: the v2 builder must reproduce the v1 argv exactly
# --------------------------------------------------------------------------


def test_argv_matches_v1_for_pi_jar(cli_module, recorded, spark_home):
    assert _v1_argv(cli_module, recorded, ["run", "pi.jar"]) == _v2_argv(spark_home, target="pi.jar")


def test_argv_matches_v1_for_pi_py(cli_module, recorded, spark_home):
    assert _v1_argv(cli_module, recorded, ["run", "pi.py"]) == _v2_argv(spark_home, target="pi.py")


def test_argv_matches_v1_for_df_r(cli_module, recorded, spark_home):
    assert _v1_argv(cli_module, recorded, ["run", "df.r"]) == _v2_argv(spark_home, target="df.r")


def test_argv_matches_v1_for_local_script(cli_module, recorded, spark_home, workdir):
    (workdir / "job.py").write_text("")
    assert _v1_argv(cli_module, recorded, ["run", "job.py", "a", "b"]) == _v2_argv(
        spark_home, target="job.py", app_args=("a", "b")
    )


def test_argv_matches_v1_for_local_flag(cli_module, recorded, spark_home):
    assert _v1_argv(cli_module, recorded, ["--local", "run", "pi.jar"]) == _v2_argv(
        spark_home, target="pi.jar", local=True
    )


def test_argv_matches_v1_for_logs(cli_module, recorded, spark_home):
    assert _v1_argv(cli_module, recorded, ["--logs", "DEBUG", "run", "pi.jar"]) == _v2_argv(
        spark_home, target="pi.jar", logs="DEBUG"
    )


def test_argv_matches_v1_with_yaml_config(cli_module, recorded, spark_home, user_home):
    (user_home / ".spark" / "config.yaml").write_text("spark:\n  driver:\n    cores: 2\n    memory: 4g\n")
    conf = config_mod.load()
    assert _v1_argv(cli_module, recorded, ["run", "pi.jar"]) == _v2_argv(spark_home, target="pi.jar", conf=conf)


def test_argv_matches_v1_for_custom_jar(cli_module, recorded, spark_home, workdir):
    (workdir / "job.jar").write_text("")
    assert _v1_argv(cli_module, recorded, ["run", "job.jar", "-c", "com.acme.Main"]) == _v2_argv(
        spark_home, target="job.jar", main_class="com.acme.Main"
    )


def test_flatten_matches_cli(cli_module):
    data = {"spark": {"driver": {"cores": 2}, "executor": {"instances": 6}}, "flat": 1}
    assert config_mod.flatten(data) == cli_module.flatten_dict(data)


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------


def test_plan_prints_without_running(cli_module, recorded, spark_home):
    result = invoke(cli_module, ["plan", "pi.jar"])

    assert result.exit_code == 0
    assert recorded == []
    assert "spark-submit" in result.output


def test_plan_accepts_v2_only_flags(cli_module, recorded):
    result = invoke(cli_module, ["plan", "pi.jar", "--deploy-mode", "cluster", "--num-executors", "8"])

    assert result.exit_code == 0
    assert "--deploy-mode cluster" in result.output
    assert "--num-executors 8" in result.output
    assert recorded == []


def test_plan_rejects_malformed_conf(cli_module):
    result = invoke(cli_module, ["plan", "pi.jar", "--conf", "novalue"])

    assert result.exit_code != 0


def test_plan_reports_missing_target(cli_module, recorded):
    result = invoke(cli_module, ["plan", "missing.py"])

    assert result.exit_code == 1
    assert "不存在" in result.output
    assert recorded == []


# --------------------------------------------------------------------------
# submit
# --------------------------------------------------------------------------


class _Completed:
    def __init__(self, returncode):
        self.returncode = returncode


def test_submit_runs_and_records_history(cli_module, user_home, monkeypatch):
    seen = []

    def fake_run(argv, check=False, **kwargs):
        seen.append(list(argv))
        return _Completed(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = invoke(cli_module, ["submit", "pi.jar"])

    assert result.exit_code == 0
    assert seen and seen[0][0] == "spark-submit"
    history = user_home / ".spark" / "history.jsonl"
    assert history.exists()
    entry = json.loads(history.read_text().splitlines()[-1])
    assert entry["returncode"] == 0
    assert entry["argv"] == seen[0]


def test_submit_propagates_exit_code(cli_module, user_home, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda argv, check=False, **kw: _Completed(7))

    result = invoke(cli_module, ["submit", "pi.jar"])

    assert result.exit_code == 7


def test_history_without_file_is_not_an_error(cli_module):
    result = invoke(cli_module, ["history"])

    assert result.exit_code == 0
    assert "无历史记录" in result.output


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------


def test_doctor_reports_the_environment(cli_module, spark_home, user_home, monkeypatch):
    (spark_home / "RELEASE").write_text("Spark 3.3.0 (git revision f74867bddf) built for Hadoop 3.3.2\n")
    monkeypatch.setattr("sparkcli.env.spark_submit_binary", lambda: "/opt/spark/bin/spark-submit")

    result = invoke(cli_module, ["doctor"])

    assert result.exit_code == 0
    assert "[ok" in result.output
    assert "Spark 3.3.0" in result.output
    assert "config.yaml" in result.output


def test_doctor_flags_a_missing_spark_home(cli_module, monkeypatch):
    monkeypatch.delenv("SPARK_HOME", raising=False)

    result = invoke(cli_module, ["doctor"])

    assert result.exit_code == 1
    assert "[fail]" in result.output


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_config_show_flattens(cli_module, user_home):
    (user_home / ".spark" / "config.yaml").write_text("spark:\n  driver:\n    cores: 2\n")

    result = invoke(cli_module, ["config", "show"])

    assert result.exit_code == 0
    assert "spark.driver.cores=2" in result.output


def test_config_validate_accepts_good_yaml(cli_module, user_home):
    (user_home / ".spark" / "config.yaml").write_text("spark:\n  driver:\n    cores: 2\n")

    result = invoke(cli_module, ["config", "validate"])

    assert result.exit_code == 0
    assert "is valid" in result.output


def test_config_loader_rejects_a_list(user_home):
    """A list at the top level is not a valid config; the loader says so.

    Note: today the v1 group callback loads the file before any command runs, so
    a structurally invalid file aborts every command with a traceback. Cleaning
    that up is tracked for 2.1 and must not change working setups.
    """
    path = user_home / ".spark" / "config.yaml"
    path.write_text("- a\n- b\n")

    with pytest.raises(config_mod.ConfigError, match="mapping"):
        config_mod.load(path)


@pytest.mark.parametrize("command", ["plan", "submit", "doctor", "config", "history"])
def test_v2_commands_are_registered(cli_module, command):
    result = invoke(cli_module, ["--help"])

    assert command in result.output


# --------------------------------------------------------------------------
# a malformed ~/.spark/config.yaml must not produce a traceback
# --------------------------------------------------------------------------


def test_broken_config_aborts_run_with_a_clear_message(cli_module, recorded, user_home):
    (user_home / ".spark" / "config.yaml").write_text("- a\n- b\n")

    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 1
    assert "配置文件无法解析" in result.output
    assert "Traceback" not in result.output
    assert recorded == []


def test_malformed_yaml_aborts_run(cli_module, recorded, user_home):
    (user_home / ".spark" / "config.yaml").write_text("spark: [\n")

    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 1
    assert "配置文件无法解析" in result.output
    assert recorded == []


def test_doctor_reports_a_broken_config(cli_module, user_home, monkeypatch):
    (user_home / ".spark" / "config.yaml").write_text("- a\n- b\n")
    monkeypatch.setattr("sparkcli.env.spark_submit_binary", lambda: "/opt/spark/bin/spark-submit")

    result = invoke(cli_module, ["doctor"])

    assert result.exit_code == 1
    assert "config.yaml" in result.output
    assert "mapping" in result.output


def test_config_validate_reports_a_broken_config(cli_module, user_home):
    (user_home / ".spark" / "config.yaml").write_text("- a\n- b\n")

    result = invoke(cli_module, ["config", "validate"])

    assert result.exit_code == 1
    assert "mapping" in result.output
