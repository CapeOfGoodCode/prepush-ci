Issue: #9

## Why

The hooks exist (#4, #5) but nothing puts them in a repository. Without that, the trailer is never written and never enforced. Many repositories already have a `pre-push` or `commit-msg` hook, or a `core.hooksPath`; overwriting those would silently drop their checks, so installing has to keep them running (#1, comment by the maintainer).

## What Changes

- New command `prepush-ci install`: writes `commit-msg` and `pre-push` hook scripts into a hooks directory of its own under the git directory and points the repository's `core.hooksPath` at it.
- The scripts run the hook of the interpreter that ran `install` (`<python> -m prepush_ci hook …`), so `PATH` does not matter.
- Hooks that were active before keep running: the scripts run the previous hook of the same name first, with the same arguments and standard input, and a failure aborts. Other hooks of the previous directory are forwarded, so replacing `core.hooksPath` loses nothing. The previous directory is never modified.
- `install` is idempotent: a second run changes nothing and says so.
- Hook managers (pre-commit, husky, lefthook) are not handled here; that is #10.

## Capabilities

### New Capabilities

- `install`: what `prepush-ci install` writes, how it keeps existing hooks, and what it reports.

### Modified Capabilities

None.

## Impact

- New: `install` subcommand and a module that writes the hooks directory, in `src/prepush_ci/`. Hook scripts are POSIX `sh` (Git for Windows ships one).
- No runtime dependencies. `init` (#12) will call `install`; #10 extends this capability for hook managers; `doctor` (#14) will check what this writes.
