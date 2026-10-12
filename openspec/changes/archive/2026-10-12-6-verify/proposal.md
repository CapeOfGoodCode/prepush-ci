Issue: #6

## Why

The trailer is a demand that the pre-push hook (#5) enforces. `verify` is the other half: the one decision every CI gate calls to learn whether a commit provably went through the full check, so pull request CI may skip its own run (#1 sections 4.3 and 5).

## What Changes

- New command `prepush-ci verify <sha>`: exit 0 when the commit carries the trailer and was not made by a server; exit 1 otherwise. It always prints one line, with the full sha, saying why. A misused command line exits 1 as well.
- The trailer rule is the one of the pre-push hook: key alone, case-insensitive, whatever the value, for the configured key and `legacy_keys`, read from the config committed in `<sha>`.
- Only `<sha>` counts, never earlier commits.
- Commits whose recorded committer is a server identity (`noreply@github.com`, and `noreply@gitlab.com` for GitLab's signed web commits) never verify. Known gap: GitLab's UI rebase keeps the trailer under the user.
- An unknown `<sha>`, or one missing from a shallow clone, fails with a reason that says what to fetch.

## Capabilities

### New Capabilities

- `verify`: what `prepush-ci verify <sha>` decides and prints.

### Modified Capabilities

None.

## Impact

- New: the pure decision in `src/prepush_ci/core/`, the `verify` subcommand in the CLI.
- The key matcher comes from the pre-push hook (#5), which blocks this change, so the two cannot drift.
- Not here: the CI gate itself, fork handling and the GitHub Action (#11).
