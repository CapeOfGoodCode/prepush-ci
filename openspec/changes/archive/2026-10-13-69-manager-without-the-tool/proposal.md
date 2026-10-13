Issue: #69

## Why

The files of a hook manager are committed, so the whole team gets the hook lines, and the lines start `prepush-ci` from `PATH`. A contributor who does not have the tool (a docs contributor, a new clone, a CI image) can then neither commit nor push: pre-commit prints `Executable prepush-ci not found`, husky `prepush-ci: not found`, and the commit fails with status 1, trailer or not. The native hooks treat the same state differently: `commit-msg` warns and lets the commit through, `pre-push` refuses and names the fix. A rule the maker of the change sets on purpose (#1, section 4.3, `install`) should not depend on which hook manager a team chose.

## What Changes

- The `commit-msg` entry of every manager, when `prepush-ci` is not on `PATH`, prints a warning on standard error, writes no trailer and lets the commit through, like the native `commit-msg`. A commit without the trailer demands no check, so nothing is lost.
- The `pre-push` entry of every manager, when `prepush-ci` is not on `PATH`, refuses the push and says it cannot be checked, like the native `pre-push`. A commit that carries the trailer (rebased or cherry-picked by someone without the tool) must not reach the remote unchecked.
- The pre-commit `commit-msg` hook shows its output when it passes (`verbose: true`), otherwise pre-commit hides the warning.
- An `install` rerun replaces a block written by an earlier version and prints `updated`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: added requirements about what the manager entries do when the tool is not on `PATH`, and that every entry names the tool's command (`prepush-ci hook <name>`); the requirement "lefthook entries" is modified so that its scenario checks that the command contains the tool's command. The requirements "pre-commit entries" and "husky entries" stay as they are.

## Impact

- `src/prepush_ci/core/hook_managers.py`: the pre-commit block, the husky blocks and the lefthook commands.
- `doctor` is not touched: the guarded entries still contain `prepush-ci hook <name>`, which is what its hook checks look for.
- README and skill wording about the contributor without the tool follows with #86 and #15.
