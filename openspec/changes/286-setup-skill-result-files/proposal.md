Issue: #286

## Why

The comment on the pull request is what a reviewer of an agent's work reads, and today it says only which command ran on which tree: no test count, no coverage. `report --markdown` can add both from a JUnit and a coverage file, but the instruction the setup skill writes into `CLAUDE.md` or `AGENTS.md` (step 8) uses the bare call, and the skill never makes the check write those files. So no agent ever passes them.

## What Changes

- The setup skill, after the user confirmed the check and before `init` runs, has the agent make the check write a JUnit file, and a coverage file where the runner can write coverage.py's JSON, to fixed paths under `.prepush-ci/` at the top of the worktree. It adds the options to the test command in the check's command line, or in a `scripts/ci` the skill wrote in this run; for any other entry point (a project's script, `make ci`, `npm run ci`, tox, nox) it writes no files and says why. It shows the change and asks the user first, adds the directory to `.gitignore` if needed, and never changes what the check checks: no new dependency, no new coverage measurement, no files when the check runs tests with more than one command, and no files when the test command runs in another directory than the top of the worktree (a `cd` before it), since the paths are relative.
- The instruction of step 8 passes those files to `report --markdown` (`--junit`, `--coverage`), with paths anchored at the top of the worktree so the call works from a subdirectory, and says to leave out a file the push did not write in this run.
- The instruction says that the post-push hook writes the short comment right after the push and the agent's call then updates the same comment.
- The README says the same in one sentence under `hook post-push` and one under `report`; both sentences are pinned by requirements that exist (see the design).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `skill`: requirements for the check that writes its result files, for where the options go, for the change to the check, for what `init` stores, and for what the instruction of the documentation step passes, leaves out and says about the comment are added; nothing existing is modified.

## Impact

- `skills/prepush-ci-setup/SKILL.md` (steps 1 and 8) and `README.md`. No code of the tool, no flag, no config key, no new dependency.
