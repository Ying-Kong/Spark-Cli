"""Unit tests for the pure helpers behind the v2 commands."""

from __future__ import annotations

import sys

import pytest

from sparkcli import config as config_mod
from sparkcli import env
from sparkcli.submit import SubmitSpec, build_argv
from sparkcli.targets import TargetError, resolve

# --------------------------------------------------------------------------
# env
# --------------------------------------------------------------------------


def test_spark_home_raises_when_unset(monkeypatch):
    monkeypatch.delenv("SPARK_HOME", raising=False)
    with pytest.raises(env.EnvError):
        env.spark_home()


def test_spark_home_reads_the_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("SPARK_HOME", str(tmp_path))
    assert env.spark_home() == tmp_path


def test_spark_version_parses_release(tmp_path):
    (tmp_path / "RELEASE").write_text("Spark 3.4.1 (git revision abc) built for Hadoop 3.3.4\n")
    assert env.spark_version(tmp_path) == "3.4.1"


def test_spark_version_without_release(tmp_path):
    assert env.spark_version(tmp_path) is None


def test_spark_version_with_unparseable_release(tmp_path):
    (tmp_path / "RELEASE").write_text("nonsense\n")
    assert env.spark_version(tmp_path) is None


@pytest.mark.parametrize(
    ("spark", "expected"),
    [("3.3.0", "3.10"), ("3.4.2", "3.11"), ("3.5.0", "3.12"), ("4.0.0", "3.12"), (None, None), ("garbage", None)],
)
def test_max_python_for(spark, expected):
    assert env.max_python_for(spark) == expected


def test_python_supported_for_old_spark():
    # The test interpreter is newer than 3.10, so a 3.3 cluster is unsupported.
    assert env.python_supported("3.3.0") is (sys.version_info.minor <= 10)


def test_log_level_supported_reads_the_template(tmp_path):
    conf = tmp_path / "conf"
    conf.mkdir()
    (conf / "log4j2.properties").write_text("rootLogger.level = ${sys:LOG_LEVEL:-WARN}\n")
    assert env.log_level_supported(tmp_path) is True


def test_log_level_unsupported_without_the_property(tmp_path):
    conf = tmp_path / "conf"
    conf.mkdir()
    (conf / "log4j2.properties").write_text("rootLogger.level = info\n")
    assert env.log_level_supported(tmp_path) is False


def test_log_level_unsupported_without_the_file(tmp_path):
    assert env.log_level_supported(tmp_path) is False


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------


def test_load_missing_file_returns_empty(tmp_path):
    assert config_mod.load(tmp_path / "nope.yaml") == {}


def test_load_none_document_returns_empty(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("# only a comment\n")
    assert config_mod.load(path) == {}


def test_load_rejects_broken_yaml(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("spark: [\n")
    with pytest.raises(config_mod.ConfigError):
        config_mod.load(path)


def test_load_flattens_nested_keys(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("spark:\n  driver:\n    cores: 2\n")
    assert config_mod.load(path) == {"spark.driver.cores": 2}


def test_flatten_keeps_flat_keys():
    assert config_mod.flatten({"a": 1}) == {"a": 1}


# --------------------------------------------------------------------------
# targets
# --------------------------------------------------------------------------


def test_alias_pi_jar_missing(spark_home):
    (spark_home / "examples" / "jars" / "spark-examples_2.12-3.3.0.jar").unlink()
    with pytest.raises(TargetError, match="spark-examples"):
        resolve("pi.jar", spark_home)


def test_alias_pi_py_missing(spark_home):
    (spark_home / "examples" / "src" / "main" / "python" / "pi.py").unlink()
    with pytest.raises(TargetError, match="Python"):
        resolve("pi.py", spark_home)


def test_alias_df_r_missing(spark_home):
    (spark_home / "examples" / "src" / "main" / "r" / "dataframe.R").unlink()
    with pytest.raises(TargetError, match="R"):
        resolve("df.r", spark_home)


def test_unsupported_extension(spark_home, workdir):
    path = workdir / "job.txt"
    path.write_text("")
    with pytest.raises(TargetError, match="不支持的文件类型"):
        resolve(str(path), spark_home)


def test_jar_requires_main_class(spark_home, workdir):
    path = workdir / "job.jar"
    path.write_text("")
    with pytest.raises(TargetError, match="main-class"):
        resolve(str(path), spark_home)


def test_jar_with_main_class(spark_home, workdir):
    path = workdir / "job.jar"
    path.write_text("")
    target = resolve(str(path), spark_home, main_class="com.acme.Main")
    assert target.is_jar
    assert target.main_class == "com.acme.Main"


def test_missing_local_file(spark_home):
    with pytest.raises(TargetError, match="不存在"):
        resolve("nope.py", spark_home)


# --------------------------------------------------------------------------
# submit builder
# --------------------------------------------------------------------------


def test_builder_emits_v2_flags_in_order(spark_home):
    argv = build_argv(
        SubmitSpec(
            target="pi.jar",
            deploy_mode="cluster",
            num_executors="8",
            driver_memory="2g",
            jars="a.jar,b.jar",
            files="f.txt",
        ),
        spark_home,
    )

    tail = argv[argv.index("--deploy-mode") :]
    assert tail == [
        "--deploy-mode",
        "cluster",
        "--num-executors",
        "8",
        "--driver-memory",
        "2g",
        "--jars",
        "a.jar,b.jar",
        "--files",
        "f.txt",
        "--class",
        "org.apache.spark.examples.SparkPi",
        argv[-1],
    ]


def test_builder_used_by_cli_submit(cli_module, monkeypatch):
    import subprocess

    seen = []

    class Done:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda argv, check=False, **kw: (seen.append(argv), Done())[1])

    from .conftest import invoke

    outcome = invoke(cli_module, ["submit", "pi.jar", "--num-executors", "4"])
    assert outcome.exit_code == 0
    assert "--num-executors" in seen[0]


# --------------------------------------------------------------------------
# extra edge cases that keep the command layer honest
# --------------------------------------------------------------------------


def test_doctor_reports_a_bad_spark_home(cli_module, monkeypatch, tmp_path):
    from .conftest import invoke

    missing = tmp_path / "not-there"
    monkeypatch.setenv("SPARK_HOME", str(missing))

    result = invoke(cli_module, ["doctor"])

    assert result.exit_code == 1
    assert "is not a directory" in result.output


def test_submit_reports_a_missing_spark_submit(cli_module, monkeypatch):
    import subprocess

    from .conftest import invoke

    def boom(argv, check=False, **kwargs):
        raise FileNotFoundError("spark-submit")

    monkeypatch.setattr(subprocess, "run", boom)

    result = invoke(cli_module, ["submit", "pi.jar"])

    assert result.exit_code == 1
    assert "No spark-submit" in result.output


def test_submit_survives_an_unwritable_history(cli_module, user_home, monkeypatch):
    import subprocess

    from .conftest import invoke

    (user_home / ".spark").rmdir()
    (user_home / ".spark").write_text("")  # a file where a directory is expected

    class Done:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda argv, check=False, **kw: Done())

    result = invoke(cli_module, ["submit", "pi.jar"])

    assert result.exit_code == 0


def test_history_skips_corrupt_lines(cli_module, user_home):
    from .conftest import invoke

    history = user_home / ".spark" / "history.jsonl"
    history.write_text('{"argv": ["spark-submit"], "returncode": 0, "seconds": 1}\nnot json\n')

    result = invoke(cli_module, ["history"])

    assert result.exit_code == 0
    assert "spark-submit" in result.output


def test_config_show_without_a_file(cli_module):
    from .conftest import invoke

    result = invoke(cli_module, ["config", "show"])

    assert result.exit_code == 0
    assert "config.yaml" in result.output


def test_plan_merges_extra_conf(cli_module):
    from .conftest import invoke

    result = invoke(cli_module, ["plan", "pi.jar", "--conf", "spark.sql.shuffle.partitions=200"])

    assert result.exit_code == 0
    assert "spark.sql.shuffle.partitions=200" in result.output


def test_plan_requires_spark_home(cli_module, monkeypatch):
    from .conftest import invoke

    monkeypatch.delenv("SPARK_HOME", raising=False)

    result = invoke(cli_module, ["plan", "pi.jar"])

    assert result.exit_code == 1
    assert "SPARK_HOME" in result.output


def test_submit_requires_spark_home(cli_module, monkeypatch):
    from .conftest import invoke

    monkeypatch.delenv("SPARK_HOME", raising=False)

    result = invoke(cli_module, ["submit", "pi.jar"])

    assert result.exit_code == 1
    assert "SPARK_HOME" in result.output
