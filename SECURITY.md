# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 2.x | Yes |
| < 2.0 | No |

## Reporting a vulnerability

Please **do not** open a public issue.

Use GitHub's private vulnerability reporting:
<https://github.com/Ying-Kong/Spark-Cli/security/advisories/new>

You can expect an acknowledgement within 72 hours and a decision on the report
within 7 days. If the issue is confirmed, a patched release is published as soon as
practical and the reporter is credited unless they prefer otherwise.

## Scope

`spark-cli` executes `spark-submit` with arguments derived from user input and from
`~/.spark/config.yaml`. Areas of interest:

- argument injection through file names or trailing job arguments
- values from `~/.spark/config.yaml` reaching the JVM command line unescaped
- anything that lets a job escalate privileges through the wrapper

The tool does not handle credentials and does not talk to cluster APIs directly.
