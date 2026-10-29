Issue: #310

## Why

prepush-ci exists so that cloud sessions can be the CI, and the session that lands a pull request is usually not the one that ran the check: a reviewer lands what a builder checked. In a Claude Code cloud session the GitHub proxy refuses the result ref push, so the result comment is the only pass the reviewer's session can find, and the proxy also refuses `GET /repos/<owner>/<repo>/collaborators/<login>/permission`. `land` reads a permission it cannot read as no, so every landing from a second cloud session fails with "no pass was found", and says nothing about the comment it threw away.

## What Changes

- A comment still counts only when its author has write access, but `land` now has a second way to see it, which the proxy serves: when the comment's author is the token's own user (`GET /user`) and the repository answers `permissions.push` `true` for that token (`GET /repos/<owner>/<repo>`), the comment counts and no permission request is sent. That is the case #310 reports: the sessions of one owner land each other's work with the same user's token. Every other author is asked about as today, so nobody without write access gains anything.
- A comment that states a pass for this tree, check and preflight but whose author does not count is still ignored, and `land` now prints one line on standard error per such author, naming the author and the reason (a GitHub App, a permission below write, a permission that cannot be read). A comment without a usable login is one unknown author, named once. The one line on standard output stays.
- An error of these two new requests only leaves the author to the permission lookup and adds no reason to the `not landed:` line; the reasons it adds stay those of the comments listing and the permission lookup.
- Where the permission lookup works and the author is not the token's user (a reviewer's comment on Actions, another user's comment), `land` decides as today.

## Capabilities

### Modified Capabilities

- `land`: "A comment of the pull request is a pass when no result is found" names the requirements it refers to by their titles, not by their position; "Only a comment of someone with write access counts" names the token's own user as the first way to show it; "A comment that cannot be read is not a pass" names the two requests whose errors add no reason; new requirements: "A comment of the token's own user counts without a lookup", "A comment of an unknown author does not count", "An ignored pass is named" and "The comments are walked in order until one counts", which says once, as `land` does today, that the comments are taken in the order of the listing and that the first one that counts, or a page that cannot be read, ends the walk.

## Impact

`src/prepush_ci/github_api.py` (`PullRequestClient` gains the token's user and whether the token can push), `src/prepush_ci/core/land.py` (the login check, the permission values and the text of the ignored lines), `src/prepush_ci/land_comments.py`, `tests/unit/land_spec.py`, `tests/integration/land_spec.py`, and the README paragraph on the comment route. Out of scope: `docs/ci/land.yml` and its `land-workflow` spec, which run on GitHub Actions with the job's token, where the permission lookup works; vouching across different users through the proxy (design).
