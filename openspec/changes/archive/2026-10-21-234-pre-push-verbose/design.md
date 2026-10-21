## Context

pre-commit hides the output of a hook that passes unless the hook sets `verbose: true`. The `commit-msg` hook of the block has had it since the warning for a missing tool needed it; the `pre-push` hook did not, and since 0.2.0 it says things the user should read (a reused result, a result that could not be shared).

## Verified with the tool

`pre-commit 4.7.0` (`uvx pre-commit --version`), git push through `pre-commit install -t pre-push`, a hook `./h.sh` that writes `prepush-ci: not run again` to standard error and exits 0, with `pass_filenames: false` and `always_run: true`:

```
== without verbose
p........................................................................Passed
== with verbose: true
p........................................................................Passed
- hook id: p
- duration: 0s

prepush-ci: not run again
```

## Decisions

- **Both hooks get `verbose: true`, no other change to the entry.** The output is what the hook prints today; a push that passes silently (nothing to say) prints only the extra lines pre-commit adds for a verbose hook (`- hook id`, `- duration`).
- **No new requirement for old blocks.** "Manager installs are idempotent" already writes the difference and prints `updated`; the scenario below pins it for this difference.
- **`doctor` does not flag a block without `verbose`.** The block works; the user only sees less. `install` fixes it on the next run.
