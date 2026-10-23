# Releasing

One-time setup, done once in the browser:

1. **PyPI trusted publisher** — on <https://pypi.org/manage/account/publishing/>
   add a pending publisher with:
   - project: `spark-cli`
   - owner: `Ying-Kong`
   - repository: `Spark-Cli`
   - workflow: `release.yml`
   - environment: `pypi`
2. **GitHub environment** — repository Settings → Environments → New environment
   named `pypi`. No secrets required; the workflow authenticates with OIDC.

Cutting a release:

```console
$ # make sure main is green and CHANGELOG has a [2.x.y] section
$ git checkout main && git pull
$ git tag -a v2.1.0 -m "v2.1.0"
$ git push origin v2.1.0
```

The `release` workflow then:

1. builds sdist and wheel,
2. signs build provenance (Sigstore attestation),
3. publishes to PyPI via OIDC — no API token is stored anywhere,
4. creates a GitHub Release with generated notes and the artifacts attached.

Afterwards, move the `[Unreleased]` section in `CHANGELOG.md` to a versioned
heading and bump `version` in `pyproject.toml`.
