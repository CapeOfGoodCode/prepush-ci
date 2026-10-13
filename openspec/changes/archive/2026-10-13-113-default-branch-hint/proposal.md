Issue: #113

## Why

The setup skill tells the agent to take `--default-branch` from `git symbolic-ref refs/remotes/origin/HEAD`, which prints `refs/remotes/origin/main`. Since #111 `init` refuses that value, so an agent that follows the hint gets exit 1 and no config, and one that works around it by hand guesses the name. The setup the user asked for stops at its first command (#1, section 4.1, skill).

## What Changes

- The skill's `<default branch>` step gives a command whose output is the full ref, `refs/remotes/origin/<branch>`, and says to remove the `refs/remotes/origin/` prefix.
- The skill says what to do when `origin/HEAD` is unset: the command fails, and the agent asks the user for the default branch instead of guessing.
- A test fills the hint's command in a repository with `origin/HEAD` and runs `init` with the result; another does the same for a repository without `origin/HEAD`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `skill`: two added requirements, the default branch hint yields a branch name and the hint says what to do without `origin/HEAD`.

## Impact

- `skills/prepush-ci-setup/SKILL.md`: the `<default branch>` bullet.
- `tests/integration/skill_spec.py`: specs for the two requirements.
