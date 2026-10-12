# Design

## Context

The repository has a CLI with `--version` only. This change adds the config both hooks depend on and the first hook. See `proposal.md` for the why, the delta specs for the behavior.

## Goals / Non-Goals

**Goals:** a config parser every later slice reuses unchanged; a `commit-msg` hook that never corrupts or invents a commit.

**Non-Goals:** installing the hook (#9), reading legacy keys from commits (#6), acting on `check`, `preflight`, `require_env`, `require_up_to_date` or `cache` (#5, #7, #8): they are only parsed here.

## Decisions

- **`check` is required, no default.** #1 asks never to guess the check; a default `scripts/ci` that does not exist would fail late and confusingly.
- **`.prepush-ci.toml` wins over `pyproject.toml`, no merging.** One source of truth (#1 4.4); merging two files would hide which value applies.
- **`require_up_to_date` defaults to `origin/<default_branch>`, `false` disables it.** #1 4.5 says "up to date by default"; deriving it from `default_branch` keeps a renamed default branch consistent.
- **Not opted in means the config is not read.** The hook will be installed for every clone; a contributor who never set `PREPUSH_CI` must be able to commit even if the config is missing or broken.
- **Empty `PREPUSH_CI` counts as unset; values are case-sensitive.** `PREPUSH_CI=` is how shells unset a variable for one command; accepting `FULL` would invite a third spelling elsewhere (CI, docs).
- **An empty message stays empty.** Verified in a scratch repository: `interpret-trailers` adds the trailer to an empty or comment-only message, and git then creates a commit whose message is only the trailer instead of aborting.
- **"Empty" is decided like git does, for this commit.** A `commit-msg` hook runs before git cleans the message up, and git gives hooks no cleanup mode, so the hook rebuilds it: `commit.cleanup` if set, else `strip` when an editor is used and `whitespace` when not. Git sets `GIT_EDITOR=:` for its hooks when it launches no editor; a user's own `GIT_EDITOR=:` (the editor that does nothing) is told apart by the template git leaves, which starts with an empty line. Under `strip`, lines starting with the comment prefix are dropped; under `whitespace` and `scissors` they are text, so `git commit -m "#123 fix"` gets its trailer. Everything from the scissors line on (the diff of `git commit -v`) is discarded in every mode but `verbatim`, where the message is empty only when it has no bytes.
- **The comment prefix is asked from git, not read from the configuration.** `git stripspace --comment-lines` prints the prefix of the git that runs the hook, so `core.commentString` counts only on a git that honours it (2.45 and newer) and `core.commentChar` counts everywhere.
- **Known limits: what a hook cannot see of the git command line.** The hook assumes the default cleanup (or `commit.cleanup`), and takes `GIT_EDITOR=:` for "no editor" unless the file starts with an empty line. Three cases then give a commit whose message is only the trailer, where git alone aborts: `GIT_EDITOR=:` with a comment-only `commit.template`; `GIT_EDITOR=:` with `-m "#123 x" --edit`; `--cleanup=strip` on the command line. The human chose to record them in the `commit-msg-hook` spec rather than read git's command line from the parent process (`ps`), which would add a platform dependency; each has a scenario. Also invisible: `--template`/`-t` (an unchanged template given that way becomes a commit), and `GIT_EDITOR=:` with a template that has text (same outcome). Each has a scenario.
- **An unchanged `commit.template` is left alone.** Git aborts with "you did not edit the message" when the cleaned message equals the cleaned template; a trailer added by the hook would make it differ and turn an abort into a commit, in the ordinary case of a team template and a user who quits the editor. The hook compares the two after the same cleanup, as git does. A missing or unreadable template is ignored: git reports that itself. Git checks the template only when an editor ran, so the hook does too: an `-m` text equal to the template still gets its trailer. Like git (`rest_is_empty`), the hook does not count `Signed-off-by:` lines as message text or as an edit, so `git commit -s` on an empty message or an unchanged template still aborts.
- **`core.commentChar=auto` (and an empty setting) is refused in full mode.** Git picks the character per commit, so the hook cannot tell an empty message from one that holds only the trailer; failing loudly beats writing a trailer-only commit.
- **Report every config problem at once.** An agent fixes the file in one round instead of one per error.
- **Trailer and legacy keys are one or more letters, digits and hyphens.** That is what git recognizes as a trailer token; anything else would be written but never read back.
- **`trailer.value` is a non-empty single line without surrounding whitespace.** Verified by review: `interpret-trailers` writes an empty value as `Prepush-CI: `, turns a newline into a second, invented trailer, and trims whitespace so the commit differs from the config.
- **Each `trailer` sub-key defaults on its own.** `trailer = { key = "Full-Check" }` means `Full-Check: full`; making a half table an error would add a rule with nothing to protect.
- **Unknown keys are reported by full path, inside `trailer` too.** `trailer.valeu` is the same typo as `chekc` and must not silently fall back to the default.
- **Only the config source in use is parsed.** A broken `pyproject.toml` next to a valid `.prepush-ci.toml` is not the tool's concern, consistent with "ignored" above.
- **Pure parsing in `core/`.** `core/` turns TOML text (already read) into a config or a list of errors; locating the repository root (`git rev-parse --show-toplevel`) and reading files stay outside `core/`, so the parser is unit-tested at 100%.

## Risks / Trade-offs

- [Every key is fixed now, before the slices that use them] → a later slice that needs a different shape changes the `config` spec through its own delta, after this change is archived.
- [A failing hook blocks commits in full mode] → intended: the user asked for the full check, and without a valid config it cannot run; the error says how to fix it.
