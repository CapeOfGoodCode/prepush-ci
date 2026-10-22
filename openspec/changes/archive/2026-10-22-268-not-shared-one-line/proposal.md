Issue: #268

## Why

When `origin` refuses the result ref, the push itself carries on, yet the warning appends git's raw output: `fatal: expected 'acknowledgments', received 'packfile'`, `RPC failed; HTTP 403`, `send-pack: unexpected disconnect`. A reader takes that for a failed push. In a Claude Code cloud session it happens on every push, because the proxy refuses anything but branches. Found in the final trial of `f815b8d`; the owner wants it fixed before 0.2.0 (#227).

## What Changes

- The warning that a result was not shared is one line: it says the result was not shared through `origin`, that another clone runs the check again, that the push goes on, and the cause in a few words (`origin refused the ref, HTTP 403`, `origin rejected the ref`, or `git could not push it`). Git's lines are not in it.
- With `PREPUSH_CI_DEBUG` set to a non-empty value, git's lines follow the warning unchanged. The README says so.
- The other warnings of the cache (the lookup that failed, the cache that could not be written, cleanup that failed) are not changed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `run-cache`: one requirement is added for the form of the warning that a result was not shared.

## Impact

- `message_not_shared` in `core/run_cache.py` and its caller `publish_pass` in `pass_cache.py`; a pure function that names the cause from git's output; the README paragraph on result refs. No config key, no new dependency, no change to the hook's decision about the push.
