Issue: #236

## Why

Someone who tries `main` before a release cannot tell which prepush-ci a hook runs: a build from git reports the same version as the last release (`prepush-ci 0.1.2` for both), so neither the user nor a report of a trial can say what was tested (#236, found in the trial of `main` before 0.2.0, #232; wanted before 0.2.0, #227).

## What Changes

- `prepush-ci --version` appends what the installation records about where it came from. An install from a git URL (`uvx --from git+https://… prepush-ci`) prints `prepush-ci 0.1.2 (git 7a42451df0fd)`: the first 12 characters of the commit. Another install that names a path or a URL (a checkout, `uv sync`, a wheel file) prints `prepush-ci 0.1.2 (direct install)`. An install from a package index prints what it prints today.
- The source is the installation record every installer writes next to the package (`direct_url.json` of the distribution, PEP 610); nothing is read from git at run time, and a record that cannot be read counts as none.
- The version in `pyproject.toml` and the way a release is made stay as they are.

## Capabilities

### New Capabilities

- `version`: what `prepush-ci --version` prints and what it does with a record it cannot read.

## Impact

- `cli.py` reads the record and prints the line; a function in `core/` turns the text of the record into the suffix. No config key, no new dependency, no change to a hook, to the run cache or to `doctor` (naming the prepush-ci that a pre-commit hook runs is #237 and builds on this line).
