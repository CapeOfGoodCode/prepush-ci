Issue: #111

## Why

The setup skill tells the agent to take `--default-branch` from `git symbolic-ref refs/remotes/origin/HEAD`, which prints `refs/remotes/origin/main`. `init` accepts that value, exits 0 and writes `default_branch = "refs/remotes/origin/main"`. From then on the up-to-date check fetches `origin/refs/remotes/origin/main`, which does not exist, so every push of a trailer commit is refused and `doctor` fails. The user was told the setup worked (#1, section 4.1, config).

## What Changes

- The config rejects a `default_branch` that begins with `refs/` or with `origin/`, naming the key and, where the value holds one, the branch name to write instead. This covers every reader of the config: `init`, the hooks, `doctor`, and a config written by hand or by an earlier `init`.
- `init` therefore exits 1 and writes nothing for such a value, whether it came from `--default-branch` or from an interactive answer.
- Other values, including a branch name with slashes (`release/1`), keep loading.
- The skill's hint (`git symbolic-ref refs/remotes/origin/HEAD`) is not changed here: `SKILL.md` and its spec belong to #15 (PR #89) and are not on `main` yet. A follow-up slice corrects the hint once #15 has merged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config`: two added requirements, the default branch is a branch name and the refusal says which branch to write.
- `init`: one added requirement, `init` refuses a default branch that is not a branch name.

## Impact

- `src/prepush_ci/core/config.py`: one more check on `default_branch`, next to the empty-string check.
- Tests: integration specs for the config and for `init` (flag and interactive answer).
