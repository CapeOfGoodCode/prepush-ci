# Design

## Context

`strip` is the escape hatch of the trailer model: the commits keep their content, lose the demand, and CI treats them like any other commit. It rewrites history, so it must be predictable, must touch only what it says, and must be easy to undo.

## Goals / Non-Goals

**Goals:** remove exactly the demanding trailer lines, rewrite as few commits as possible, refuse every state in which a rewrite could lose work, and tell the user what to do next.

**Non-Goals:** pushing (the user pushes with `--force-with-lease`), changing other refs, re-signing commits, repairing a history another tool is rewriting.

## Decisions

- **Which keys:** `trailer.key` and `legacy_keys` of the config at `HEAD`. The worktree must be clean, so that is also the worktree's config. The configs committed in earlier commits are not consulted; a commit made under a key that was dropped from the config since is left as it is. Unlike the hook, no union is needed: strip runs on the branch the user has checked out.
- **What is removed:** the lines of the trailer block, as `git log` reads it (`%(trailers:only,unfold)`), whose key matches, case-insensitively, whatever the value, all of them when there are several. The continuation lines of a removed trailer go with it: git unfolds them into the trailer's value, and left behind they would attach to the trailer before it. Everything else in the message stays byte for byte. When that leaves the trailer block empty, the blank line that separated it from the body goes too, so a message made by `commit-msg` is restored exactly (`add x`, blank line, `Prepush-CI: full` becomes `add x`). A `---` line in the body and a matching text in an earlier paragraph are ordinary text.
- **Default base:** `git merge-base HEAD origin/<default_branch>`; when that ref does not exist, the local `<default_branch>`; when neither exists, or the ref exists but shares no history with `HEAD` (an orphan branch, a force-pushed fresh history), an error that asks for `<base>`; never the whole history, which may be published. Rationale: session commits are the ones not yet on the remote default branch, and the local branch covers repositories without a remote.
- **`<base>` must be an ancestor of `HEAD`.** Otherwise `<base>..HEAD` would include commits the user did not make on this line of history. `<base>` itself is never rewritten.
- **No hooks, whatever the environment.** `strip` writes the commits itself and runs no git hook, so `commit-msg` cannot put the trailer back when `PREPUSH_CI=full` is still exported in the session (it often is: that is where `strip` is used).
- **Rewrite in history order, keep the graph.** A commit whose message does not change and whose parents did not change keeps its SHA; a commit whose parent changed gets a new SHA and the same message; a merge commit keeps all its parents (rewritten where needed). Authors, committers (name, e-mail, date), trees and the message encoding are kept exactly, so a commit that GitHub made keeps its server committer for `verify` (#6). Signatures cannot survive a rewrite; a signed commit that is rewritten loses its signature.
- **Only the current branch moves.** No other ref, no remote, no tag. The old tip stays reachable by its SHA (it is printed) and in the reflog, which is the undo: `git reset --hard <old tip>`.
- **Refusals change nothing and exit 1:** dirty worktree (same definition as the pre-push hook), an unfinished rebase, merge, cherry-pick, revert, `git am` or bisect, a detached `HEAD`, an unknown `<base>`, a `<base>` that is not an ancestor, a missing or invalid config, extra arguments. A detached `HEAD` is refused because there is no branch to move. `git am` and bisect are listed on their own: they can leave a branch checked out and a clean worktree while a sequence is still open.
- **Report:** one `strip:` line with the number of commits rewritten out of the number in range and the old and new tip. When commits were rewritten, a second line says the next push needs `git push --force-with-lease`; when none were, it says nothing needs pushing again and no force hint is printed.

## Risks / Trade-offs

- [A rewrite loses work] → the dirty and in-progress refusals, the printed old tip and the reflog.
- [A commit made under a key the config no longer has keeps its trailer] → accepted; `doctor` or `verify` shows it, and the config can list the key in `legacy_keys`.
- [Signed commits lose their signature] → inherent to rewriting; not mitigated here.
- [`--force-with-lease` is the user's call] → `strip` never pushes.
