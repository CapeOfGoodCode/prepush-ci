Issue: #287

## Why

The comment the post-push hook (#246) writes on the pull request says only which command ran on which tree. The test count, the coverage and the duration reach it only if the agent remembers to call `report` with result files (#286), and the files may be missing or left over from an earlier run. A reviewer should see what ran without anyone having to remember a step.

## What Changes

- The config gets an optional table `results` that names the files the check writes: `junit` (a list), `coverage`, `ruff` and `mypy`, as paths from the top of the worktree.
- When a check that the tool runs (in `prepush-ci run` or in the pre-push hook) passes, the pass it records also holds the facts of that run: the duration of the check, and what the named files of this run say (test counts, per test file; coverage; the number of errors of ruff and of mypy). The tool deletes the named files before the check starts, so a file left from an earlier run is never read.
- The post-push hook adds to the comment, after the Markdown of `report`, the facts as one visible line (tests, coverage, duration) and a collapsed `<details>` block (per tool, per test file). A pass reused from an earlier run says so and names the commit it ran on.
- Nothing the check printed goes into the facts: only numbers, and the paths of test files that exist in the checked tree.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config`: the key `results` (added to the keys and defaults; its own requirements).
- `run-cache`: the facts a recorded pass holds, and how they are read (added; nothing existing is modified).
- `post-push-hook`: the comment is the Markdown of `report` followed by the facts (modified), and the block of facts (added).

## Impact

`core/config.py`, `core/run_cache.py` (the message of the result commit and its reading), `pass_cache.py`, `checking.py`, `post_push_hook.py`, a new pure module for the facts in `core/`, and the config reference in `README.md`. No flag, no new dependency. Not in scope: the setup skill and `init` writing `results` (a follow-up slice once this is built), and any change to `report`.
