# Contributing

Thanks for considering a contribution. This is a small tool and the review bar is
mostly about not breaking the command surface.

## Development setup

```console
$ git clone https://github.com/Ying-Kong/Spark-Cli.git
$ cd Spark-Cli
$ python -m venv .venv && . .venv/bin/activate
$ pip install -e ".[dev]"
$ pre-commit install
```

## Before opening a pull request

```console
$ ruff check . && ruff format --check .
$ pytest
```

Both must pass. CI runs the same commands on Python 3.9, 3.10, 3.11 and 3.12.

## The contract suite

`tests/test_contract_v1.py` pins the exact `spark-submit` argv that the CLI
produces. If your change makes one of those tests fail, you are changing user
visible behaviour. That is allowed, but it needs:

1. a CHANGELOG entry under `[Unreleased]`,
2. a matching update to the test, and
3. a note in the pull request explaining why the old behaviour had to change.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>(<scope>): <summary>

[optional body]
```

Common types: `feat`, `fix`, `docs`, `test`, `build`, `ci`, `chore`, `refactor`.

Examples:

```
feat(cli): add a --dry-run flag
fix(config): quote YAML values that contain spaces
docs: document the exit codes
```

## Branches and releases

Work happens on short-lived branches named `feat/...`, `fix/...` or `docs/...`.
`main` is protected; changes land through pull requests.

Releases are cut by tagging `vX.Y.Z` on `main`. See [README](README.md#releases).

## Code of conduct

Participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
