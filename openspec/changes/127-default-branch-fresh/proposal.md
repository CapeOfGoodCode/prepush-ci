Issue: #127

## Why

The setup skill takes `--default-branch` from `git symbolic-ref refs/remotes/origin/HEAD`, a local record that `git fetch --prune` never updates. In a clone that predates a rename of the remote's default branch, the hint yields the old name, `init` accepts it and writes `default_branch = "master"` for a branch that no longer exists. Every push of a trailer commit is then refused by the up-to-date check, and the user was told the setup worked (#1, section 4.1, skill and `init`).

## What Changes

- The skill's `<default branch>` step runs `git remote set-head origin --auto` first, which asks the remote for its default branch and refreshes the local record, and only then `git symbolic-ref refs/remotes/origin/HEAD`. When the first command fails (no `origin`, remote unreachable, remote without a default branch, a clone that does not fetch the default branch), the agent asks the user instead of guessing, as it already does when `origin/HEAD` is unset.
- `init` refuses a default branch, given by flag or typed as the answer, that `origin` lacks: the repository holds remote-tracking branches of `origin`, none of them the named one, `origin` has the default fetch refspec, and the up-to-date ref in effect is `origin/<branch>`. It exits 1 and writes nothing.
- Without remote-tracking branches of `origin` (no remote, an empty remote, a remote never fetched), with a fetch refspec of `origin` that is not the default (a single-branch or shallow clone) or with another up-to-date ref, nothing is checked, so a first `init` in a new repository keeps working.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `skill`: the default branch hint refreshes `origin/HEAD` first; the agent asks when that fails.
- `init`: two added requirements, a default branch that `origin` lacks is refused, and when nothing is checked.
- `readme`: the agent step names the cases in which the agent asks for the default branch, the same as the skill does.

## Impact

- `skills/prepush-ci-setup/SKILL.md`: the `<default branch>` bullet.
- `src/prepush_ci/init_command.py`: one more check on the default branch, next to the branch-name check.
- `README.md`: the sentence on what the agent asks.
- Tests: `tests/integration/skill_spec.py` and the init integration specs.
