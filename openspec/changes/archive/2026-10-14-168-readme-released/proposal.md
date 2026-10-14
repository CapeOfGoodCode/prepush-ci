Issue: #168

## Why

The README is the PyPI long description. The page of 0.1.0 still says "Status: under construction. Nothing here is released yet" and "until the first release is on PyPI, run the command from the repository instead", on the page of the release that disproves them; a reader installs from git for no reason or not at all. The classifier `Development Status :: 2 - Pre-Alpha` says the same to someone browsing PyPI (#1, a tool a team can trust enough to install).

## What Changes

- `README.md` loses the three places that assume no release: the "Status: under construction" box, the "until the first release is on PyPI" comment with its `uv tool install git+…` line in step 2, and the `uvx --from git+…` sentence in step 1. The plugin sentence stays.
- The requirement "The agent step has a form that runs before the first release" is removed: it pins the sentence being cut. A new requirement says the README has no pre-release wording.
- `pyproject.toml`: the classifier `Development Status :: 2 - Pre-Alpha` becomes `Development Status :: 3 - Alpha`. No spec pins it; it is a task.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme`: one requirement removed, one added.

## Impact

`README.md`, `pyproject.toml` and `tests/integration/readme_spec.py`. No code of the tool changes. The release 0.1.1 is a separate `chore(release)` pull request.
