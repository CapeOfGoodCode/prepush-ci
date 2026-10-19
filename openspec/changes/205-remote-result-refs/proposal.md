Issue: #205

## Why

A result ref lives in one clone. A new session in a fresh clone, a reviewer or another agent cannot see that a tree already passed, so it checks again. Publishing the ref to the remote and looking it up there before a check lets a result outlive the clone that made it (#196, step 2; #199 needs it to find a result from another session).

## What Changes

- When the pre-push hook records a pass for a push to `origin`, it also pushes the ref `refs/prepush-ci/results/<tree>-<config>` to `origin`. It pushes a result it reuses from the local clone in the same way, so a pass that could not be published once is published by the next push to `origin`.
- A push to any other remote, a push by url, and a hook that cannot tell the remote (lefthook passes none) publish nothing, and `prepush-ci run` publishes nothing: a result ref reaches `origin` only in a push to `origin`. That push may be a `--dry-run` or one that `origin` declines; the hook cannot tell, so the tree reaches `origin` in those cases too.
- Before it runs the check, the hook that finds no local result looks for the ref on `origin`, whichever remote the push goes to. A result found there counts as one found locally, and the hook's line says it came from `origin`.
- `run` never contacts the remote. A repository without `origin` shares nothing and says nothing.
- A remote that cannot be reached or refuses the ref is a warning on standard error and a miss; it never refuses a push.
- `cache = false` turns the remote off with the rest of the cache.

## Capabilities

### Modified Capabilities

- `run-cache`: requirements are added for publishing a pass by a push to `origin`, how the hook learns the remote (argument 1, then `PRE_COMMIT_REMOTE_NAME`, else nothing is published), the rule that only `origin` and only with the cache counts, reusing a result found there, `run` not using the remote, and a remote that fails costing time and nothing else.

## Impact

- `pass_cache.py` gains `publish_pass` and `fetch_pass`, which call `git push --no-verify` and `git fetch` for the one ref; `pre_push_hook.py` calls them and reads the remote from its `git_args` (now used) or `PRE_COMMIT_REMOTE_NAME`. `install` does not change: lefthook installs publish nothing until a later change adds `{1}`. `run_command.py` does not change.
- One extra `git ls-remote` per hook run that finds no local result, one `git push` after each pass in a push to `origin`. No config key, no runtime dependency.
- Where the remote accepts branches only (a Claude Code cloud session behind its proxy rejects any other ref), the publish is refused: a warning on every pass, and no sharing from that session. See `design.md`.
