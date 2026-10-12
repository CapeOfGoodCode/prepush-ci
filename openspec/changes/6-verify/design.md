# Design

## Context

The pre-push hook (#5) guarantees: trailer on the remote implies the full check passed on that commit. `verify` is what CI asks. A false "yes" costs a skipped CI run on unchecked code, a false "no" costs one extra run, so every doubt answers no.

## Goals / Non-Goals

**Goals:** one decision, the same trailer rule as the hook, a reason on every path, no skip on anything the tool cannot read.

**Non-Goals:** fork handling, default-branch handling and the pipeline wiring (#11), writing or removing trailers (#4, #13), proving the check ran (the trailer is a trust model for cost, #1 section 2).

## Decisions

- **Same rule as the hook, one function.** The trailer key alone, compared case-insensitively, whatever the value, for the configured key and `legacy_keys`. A hand-typed `Prepush-CI: off` therefore verifies: the hook demanded the check for it too. The core exposes one matcher that both commands call.
- **Trailers are read as `git log` shows them** (`git log -1 --format=%(trailers:only,unfold)`), so a `---` line in the body hides nothing. `commit-msg` writes the trailer after such a line on purpose.
- **The config is the one committed in `<sha>`.** That is what the commit's author ran the hook with, and a CI checkout may not be the commit. Location and validation are the `config` capability's, applied to the files as committed. Unlike the hook, `verify` does not consult the worktree config: it would let a later config change decide about an earlier commit. A commit without a config, or with an invalid one, does not verify and the reason says which.
- **Exit status: 0 only for "verified", 1 for everything else**, including an unknown sha, a missing config and unreadable git state. A gate that tests `verify`'s status can never skip because something went wrong. A misused command line (no sha, an empty one, extra arguments) exits 1 too, with the same `not verified:` line, so the argument parser's own status 2 never leaks out: the gate only ever sees 0 or 1.
- **Output: one line on standard output, starting with `verified:` or `not verified:`**, then the full sha and the reason. Greppable, and CI logs show it as it is.
- **Server-made commits are recognized by the recorded committer e-mail, from a fixed list:** `noreply@github.com` (GitHub's web-flow: merge, squash, rebase and web-edit commits) and `noreply@gitlab.com` (the identity GitLab uses for web commits when web commit signing is on), compared case-insensitively on the whole address. Rationale: a server rewrites the commit, so the check never ran on it, and the committer is the one field a server must set to itself. The author is not used: it stays the user. The e-mail is read with `%ce`, the address as recorded in the commit object, never `%cE`: `.mailmap` comes from the checkout and could map a server to anyone, or a user to a server. Exact match, not a suffix: `123+u@users.noreply.github.com` is a user.
- **Known gap, GitLab and self-managed servers.** GitLab does not sign, and does not use its own identity for, commits it makes without web commit signing, and it cannot sign the commits of a rebase from the UI or the API. The **Rebase button on a merge request** writes new commits that keep the trailer and have the user who clicked as committer; `verify` accepts them though no hook checked them. Self-managed servers use other identities. Accepted for a cost-only trust model: the default branch always runs in full (#1 section 5), and #11's GitLab example warns about the rebase button. Making the list configurable needs a new config key; that is a later change, not this one. Issue #6's acceptance line is amended to what is decidable: GitHub's server-made commits, and GitLab's when it signs.
- **Merge commits are not special.** A merge made on a machine that ran the hook carries the trailer and was checked; only the committer decides.
- **`<sha>` is anything git resolves to a commit**, printed back as the full 40-hex sha (stable across clones and greppable in CI logs, unlike an abbreviation that depends on `core.abbrev`), so `HEAD` works in CI scripts.
- **The "what to fetch" text** names the sha and the command: if the repository is shallow, `git fetch --unshallow` or a deeper fetch (`fetch-depth: 0` for GitHub Actions' checkout); otherwise `git fetch origin <sha>`. One line, same prefix.

## Risks / Trade-offs

- [A server identity outside the list verifies a server-made commit that carries a trailer] → accepted, see above; the trailer would have to come from the message the server composed.
- [A rebase from the GitLab UI or API keeps the trailer under the clicking user] → accepted and named in the PR's Decisions; #11's GitLab example says not to use that button on a merge request that relies on skipping.
- [Key-only matching verifies a hand-typed `Prepush-CI: off`] → consistent with the hook, which checked it before it could be pushed.
- [A commit amended by a bot after the check] → outside the model: the hook would have checked the new tip, the trailer says nothing else.
