# Security policy

prepush-ci installs git hooks and runs your checks, so a flaw in it can matter beyond the repository it is in. Please report one privately.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: [report a vulnerability](https://github.com/CapeOfGoodCode/prepush-ci/security/advisories/new). Do not open a public issue or pull request for it.

Please include:

- the prepush-ci version (`prepush-ci --version`);
- your environment: OS, git version, Python version, and the hook manager in use;
- a reproduction from a fresh repository (`git init`), with the commands and their output;
- what an attacker gains.

Never include a real credential or token; if one is needed to show the problem, quote at most its first eight characters.

## Supported versions

Until 1.0.0, only the latest release gets fixes.

## What happens next

The maintainer reads the report and decides how to fix it. The fix ships in a release the maintainer decides ([`AGENTS.md`](AGENTS.md), Versioning).
