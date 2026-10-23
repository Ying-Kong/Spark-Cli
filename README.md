# spark-cli

[![ci](https://github.com/Ying-Kong/Spark-Cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Ying-Kong/Spark-Cli/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A thin, opinionated wrapper around `spark-submit`.

Instead of remembering six `--conf` flags and the exact class name of the bundled
example, you run one command:

```console
$ spark-cli run pi.py
submitting spark job
spark-submit --master yarn --conf spark.driver.extraJavaOptions=-DLOG_LEVEL=WARN \
  --conf spark.executor.extraJavaOptions=-DLOG_LEVEL=WARN \
  /opt/spark/examples/src/main/python/pi.py
```

The full command line is always printed before it runs, so you can copy it out and
debug by hand whenever something goes wrong.

## Requirements

- `SPARK_HOME` set to a Spark distribution that ships `examples/`
- `spark-submit` on `PATH`
- Python 3.10 – 3.13 (see [compatibility](#compatibility))

## Install

```console
$ pip install git+https://github.com/Ying-Kong/Spark-Cli.git
```

or, for development:

```console
$ git clone https://github.com/Ying-Kong/Spark-Cli.git
$ cd Spark-Cli
$ python -m venv .venv && . .venv/bin/activate
$ pip install -e ".[dev]"
```

## Usage

```console
$ spark-cli [--local] [--logs LEVEL] run <target> [ARGS...]
```

| Target | Resolves to |
| --- | --- |
| `pi.jar` | `$SPARK_HOME/examples/jars/spark-examples*.jar` + `--class org.apache.spark.examples.SparkPi` |
| `pi.py` | `$SPARK_HOME/examples/src/main/python/pi.py` |
| `df.r` | `$SPARK_HOME/examples/src/main/r/dataframe.R` |
| any path | A local `.jar`, `.py` or `.r` file. `.jar` requires `-c/--main-class`. |

Aliases win over local files with the same name. To run a local `pi.py`, pass a
path: `spark-cli run ./pi.py`.

### Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--master` | `yarn`, or `local[*]` with `--local` | Where the job runs |
| `--logs LEVEL` | `WARN` | Injected as `-DLOG_LEVEL` into driver and executor JVM options |
| `-c, --main-class` | – | Required for custom jars |

Everything after the target is passed to the job untouched:

```console
$ spark-cli run ./wordcount.py hdfs:///in hdfs:///out --num-reducers 4
```

### Optional config: `~/.spark/config.yaml`

If the file exists, it is flattened into `--conf` pairs. Nested keys become dotted
keys:

```yaml
spark:
  driver:
    cores: 2
    memory: 4g
  executor:
    instances: 6
```

becomes `--conf spark.driver.cores=2 --conf spark.driver.memory=4g --conf spark.executor.instances=6`.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Job succeeded |
| *n* | The job's own exit code, passed through unchanged |
| `1` | Local error: `SPARK_HOME` unset, target missing, unsupported extension, jar without `--main-class`, `spark-submit` not found |

## More commands

`run` is the v1 surface and stays frozen. Everything below is additive.

| Command | What it does |
| --- | --- |
| `spark-cli plan <target>` | Print the `spark-submit` command without running it |
| `spark-cli submit <target>` | Like `run`, but also accepts `--deploy-mode`, `--num-executors`, `--driver-memory`, `--jars`, `--files` and repeated `--conf KEY=VALUE` |
| `spark-cli doctor` | Check `SPARK_HOME`, `spark-submit`, Spark and Python versions, the log4j2 template, and `config.yaml` |
| `spark-cli config show` | Print `~/.spark/config.yaml` flattened into `key=value` |
| `spark-cli config validate` | Parse the YAML and report structural problems |
| `spark-cli history` | Show submissions recorded by `submit` (`~/.spark/history.jsonl`) |

```console
$ spark-cli plan ./etl.py --deploy-mode cluster --num-executors 20 \
    --conf spark.sql.shuffle.partitions=400
spark-submit --master yarn --conf ... --deploy-mode cluster --num-executors 20 \
  --conf spark.sql.shuffle.partitions=400 ... /home/me/etl.py
```

`doctor` is the fastest way to answer "why did my job fail before it started?":

```console
$ spark-cli doctor
[ok  ] SPARK_HOME       /opt/spark
[ok  ] spark-submit     /opt/spark/bin/spark-submit
[ok  ] Spark version    3.3.0
[warn] Python           3.13.12 (Spark 3.3.0 supports up to 3.10)
[warn] log4j2 LOG_LEVEL not read by the cluster template; --logs will be ignored
[ok  ] config.yaml      /home/me/.spark/config.yaml (3 keys)
```

## Compatibility

| Spark | Highest supported Python |
| --- | --- |
| 3.3.x and below | 3.10 |
| 3.4.x | 3.11 |
| 3.5.x and above | 3.12 |

When a Python job fails, `spark-cli` prints this table — a version mismatch
between the driver and the YARN NodeManagers is the most common cause.

## Development

```console
$ pip install -e ".[dev]"
$ pytest
$ ruff check . && ruff format --check .
```

The contract suite in `tests/` pins the CLI surface. If a test changes, that is a
breaking change and needs a CHANGELOG entry.

## License

MIT — see [LICENSE](LICENSE).
