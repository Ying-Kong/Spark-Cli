"""Edge-case contracts: alias assets missing, and the three legacy helpers.

These pin behaviour that `run` never exercises on a healthy Spark install but
that users still hit (wrong SPARK_HOME, trimmed distributions).
"""

from __future__ import annotations

import pytest

from .conftest import EXAMPLE_JAR_NAME, invoke


def test_missing_python_example(cli_module, spark_home):
    (spark_home / "examples" / "src" / "main" / "python" / "pi.py").unlink()

    result = invoke(cli_module, ["run", "pi.py"])

    assert result.exit_code == 1
    assert "未找到 Python 示例文件" in result.output


def test_missing_r_example(cli_module, spark_home):
    (spark_home / "examples" / "src" / "main" / "r" / "dataframe.R").unlink()

    result = invoke(cli_module, ["run", "df.r"])

    assert result.exit_code == 1
    assert "未找到 R 示例文件" in result.output


def test_missing_examples_jar(cli_module, spark_home):
    (spark_home / "examples" / "jars" / EXAMPLE_JAR_NAME).unlink()

    result = invoke(cli_module, ["run", "pi.jar"])

    assert result.exit_code == 1
    assert "未找到 spark-examples.jar 包于" in result.output


# --------------------------------------------------------------------------
# legacy helpers: still public, still importable, behaviour frozen
# --------------------------------------------------------------------------


def test_flatten_dict_nests_with_dots(cli_module):
    assert cli_module.flatten_dict({"spark": {"driver": {"cores": 2}}}) == {"spark.driver.cores": 2}


def test_flatten_dict_keeps_flat_keys(cli_module):
    assert cli_module.flatten_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_resolve_jar_accepts_existing_relative_path(cli_module, workdir):
    (workdir / "job.jar").write_text("")

    assert cli_module.resolve_jar("job.jar") == str((workdir / "job.jar").resolve())


def test_resolve_jar_searches_spark_home(cli_module, spark_home):
    expected = spark_home / "examples" / "jars" / EXAMPLE_JAR_NAME

    assert cli_module.resolve_jar(EXAMPLE_JAR_NAME) == str(expected)


def test_resolve_jar_exits_when_absent(cli_module):
    with pytest.raises(SystemExit) as excinfo:
        cli_module.resolve_jar("nope.jar")

    assert excinfo.value.code == 1


def test_normalize_url_converts_scheme_to_file_url(cli_module):
    assert cli_module.normalize_url("hdfs:///user/x/job.jar") == "file:///user/x/job.jar"


def test_normalize_url_leaves_plain_paths_alone(cli_module):
    assert cli_module.normalize_url("job.py") == "job.py"
