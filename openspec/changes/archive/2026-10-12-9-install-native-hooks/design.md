# Design

## Context

`commit-msg` (#4) and `pre-push` (#5) are commands; git has to be told to call them. See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** after `install`, commits and pushes run our hooks and every hook that ran before; running it again is harmless; nothing in the repository's worktree changes.

**Non-Goals:** pre-commit, husky and lefthook (#10), writing config or CI snippets (#12), diagnosing a broken setup (#14), a global (user-level) install.

## Decisions

- **Chain, never install into the previous directory.** The previous hooks directory (a `core.hooksPath` or `.git/hooks`) may be tracked, shared or owned by a manager. Writing there would dirty the worktree (the pre-push hook refuses a dirty one) or be overwritten by the owner. Our own directory plus chaining keeps every existing hook byte for byte where it was.
- **The hooks directory is `<git common dir>/prepush-ci/hooks`, and `core.hooksPath` is set locally to its absolute path.** Inside `.git` it is never committed or pushed, and in a linked worktree the common dir makes one install cover all worktrees. An absolute path because git resolves a relative one against the directory the hook runs in.
- **The previous directory is the effective `core.hooksPath` of any scope (read as a path, so `~` expands), otherwise what `git rev-parse --git-path hooks` prints, which is under the common directory in a linked worktree (the git directory of a worktree has no hooks).** It is recorded in the file `previous` of our directory, because after `install` the effective `core.hooksPath` is ours. A relative previous path is resolved against the worktree root and recorded absolute.
- **Existing hooks run before ours.** An existing hook is cheap and its refusal should not cost a full check. Ours runs only after it passed. For `pre-push` standard input is saved once and fed to both.
- **Chained and forwarded hooks do what git does, at run time.** Git skips a hook that is missing or not executable (with a hint) and goes on. The scripts test `[ -x … ]` each time and exit 0 otherwise, so a non-executable file never turns into a failing hook and a deleted one does not block until `install` is rerun.
- **A rerun adopts a changed `core.hooksPath` as the new previous directory.** If a manager (husky, say) set its own path after the first run, resetting ours would drop it; chaining to it keeps it running. Ours is a hop in the chain only while `core.hooksPath` points at it.
- **Every other hook of the previous directory gets a forwarding script.** Replacing `core.hooksPath` hides hooks we do not own (`pre-commit`, `post-merge`, …); a forwarder per regular file, except `*.sample`, runs the previous one with `exec` when it is executable, so arguments, standard input and exit status are untouched. The forwarders are made at install time; a hook added later to the previous directory is picked up by running `install` again.
- **The scripts read the interpreter from the file `python` of our directory.** `install` records `sys.executable`, which is the interpreter that has `prepush_ci`, so the scripts never look at `PATH` (AGENTS.md starts the CLI the same way in tests). Keeping it in a file makes the scripts identical on every machine, and a rerun from another interpreter is an update of one file.
- **A missing interpreter fails closed for `pre-push` and open for `commit-msg`.** Without the tool, a push could carry a trailer commit unchecked, so `pre-push` refuses and names `prepush-ci install` as the fix. A missing `commit-msg` hook only means no trailer, so CI runs in full; blocking every commit for that would be worse. It warns on stderr.
- **Idempotent means byte-identical output files and unchanged config** (while `core.hooksPath` is still ours). The run compares what it would write with what exists and writes nothing if equal; the report says `already installed`. Any difference (new interpreter, new forwarder, removed previous hook) is written and reported as `updated`.
- **`install` needs no `.prepush-ci.toml`.** It only wires git; the hooks fail closed on a missing config themselves.
- **Hook scripts are POSIX `sh`, with the executable bit set.** Git runs hooks through `sh` on every platform it supports, Git for Windows included; paths are written with forward slashes (as the Windows fix in #36 does for tests).

## Risks / Trade-offs

- [A `pre-commit install` run later refuses while `core.hooksPath` is set] → that is #10's case; here a user who already runs pre-commit keeps its hook through chaining.
- [Under `uvx`, `sys.executable` lives in uv's cache and can vanish] → `pre-push` then refuses with the fix named; a persistent install (`uv tool install`) avoids it, which `init` (#12) and the skill (#15) can recommend.
- [A hook added to the previous directory after `install` is not forwarded until `install` is rerun] → documented; `doctor` (#14) can warn.
