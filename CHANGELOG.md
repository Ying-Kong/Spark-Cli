# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `plan`, `submit`, `doctor`, `config show|validate` and `history` commands.
  `run` is unchanged; the new builder is proven byte-identical to it by a
  differential test suite.
- `submit` adds `--deploy-mode`, `--num-executors`, `--driver-memory`, `--jars`,
  `--files` and repeated `--conf KEY=VALUE`.
- Contract test suite pinning the v1 command surface (97 tests, 95%+ coverage).
- GitHub Actions CI on Python 3.9 – 3.12, plus a packaging and a mypy job.
- ruff, pre-commit, editorconfig, issue forms, dependabot and a release workflow
  with PyPI trusted publishing.

### Fixed

- A malformed `~/.spark/config.yaml` no longer aborts every command with a
  traceback: `run` fails with a one-line message, while `doctor` and
  `config validate` can now report the problem.
- `spark-cli doctor` reports the Spark/Python compatibility mismatch and the
  log4j2 `-DLOG_LEVEL` caveat instead of leaving them to a failed job.

## [2.0.0] - 2026-06-20

### Added

- `spark-cli run <target>` for `.jar`, `.py` and `.r` jobs.
- Built-in aliases: `pi.jar`, `pi.py`, `df.r`.
- `--local` to switch between YARN and `local[*]`.
- `--logs LEVEL` injected as `-DLOG_LEVEL` into driver and executor JVM options.
- `~/.spark/config.yaml` flattened into `--conf` pairs.
- Version-compatibility diagnostics printed when a Python job fails.

[Unreleased]: https://github.com/Ying-Kong/Spark-Cli/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/Ying-Kong/Spark-Cli/releases/tag/v2.0.0
