# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Contract test suite pinning the v1 command surface (36 tests, 97% coverage).
- GitHub Actions CI on Python 3.9 – 3.12, plus a packaging job.

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
