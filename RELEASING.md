# Releasing

The `release` workflow runs on every `v*.*.*` tag. It always builds the sdist and
wheel, attests build provenance and creates a GitHub Release. Publishing to PyPI
is **opt-in**.

## Cutting a release

```console
$ git checkout main && git pull
$ git tag -a v2.1.0 -m "spark-cli v2.1.0"
$ git push origin v2.1.0
```

Then move the `[Unreleased]` section in `CHANGELOG.md` to a versioned heading and
bump `version` in `pyproject.toml`.

## Publishing to PyPI (optional, off by default)

### The distribution name is taken

`spark-cli` already exists on PyPI as an unrelated project
(<https://pypi.org/project/spark-cli/>). Pick a free distribution name — for
example `spark-submit-cli` — and change `[project].name` in `pyproject.toml`
before going further. The console command stays `spark-cli`.

### One-time setup

1. **PyPI pending publisher** — <https://pypi.org/manage/account/publishing/>
   with:
   - project: the name chosen above
   - owner: `Ying-Kong`
   - repository: `Spark-Cli`
   - workflow: `release.yml`
   - environment: `pypi`
2. **GitHub environment** — Settings → Environments → New environment named
   `pypi`. No secrets are needed; authentication uses OIDC.
3. **Enable the job** — Settings → Secrets and variables → Actions → Variables →
   add `PUBLISH_TO_PYPI` = `true`.

Once the variable is set, the next tag publishes. To publish a tag that was cut
earlier, re-run the skipped `publish` job from the Actions tab.
