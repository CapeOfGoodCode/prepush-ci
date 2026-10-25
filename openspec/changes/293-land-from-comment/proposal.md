Issue: #293

## Why

A Claude Code cloud session cannot push result refs (#242), and the projects that use prepush-ci work mostly in cloud sessions. With the result ref as the only source of a pass, `land` would run the full check again on nearly every merge. A session already shows its result as a pull request comment (`report --markdown`, posted by the post-push hook), and that comment names the tree it checked. Part of #199, owner's decision of 2026-10-25.

## What Changes

- `land` looks for a pass in a second place: when neither the clone nor `origin` holds the result ref of the head's tree and key, it reads the comments of the pull request and accepts one that says the check passed on this tree. A result ref wins over a comment when both exist.
- A comment counts only when: it starts with the marker of the default check (`<!-- prepush-ci:prepush-ci / full -->`); its title line is a pass title; its `Tree` is the tree being landed; its `Check` and `Preflight` are the ones committed in the head, compared with what `report` writes for them (the preflight's output is not attested); and its author is a user, not an App, with write access to the repository.
- Reading the comments needs a token (`GITHUB_TOKEN`, else `GH_TOKEN`) and a repository (`origin`, else `GITHUB_REPOSITORY`), found the way `report` and the post-push hook find them. Without them, or when the API fails, the comment is not a source and the line says why.
- The comment of the post-push hook must attest the check that ran, not only the committed one: the result commit records a digest of the config the run used (`run-cache`), and the hook posts only for a pass whose digest is that of the committed config (`post-push-hook`).
- `report --markdown` says `Failed (<counts>)` in the title line of a failed result that has test counts, so that a comment states its result in one way only; the check run's title is unchanged.
- A comment is never written, and no result ref is created from it.

## Capabilities

### Modified Capabilities

- `land`: "The tree must have a pass for the configured check" gains the comment as a second source; new requirements say which comments count and what happens when they cannot be read.
- `run-cache`: a recorded pass names the config it ran with.
- `post-push-hook`: only a pass of the committed config is shown.
- `report`: "The Markdown is the check run's summary under a marker" fixes the title line of a failed result.

## Impact

`src/prepush_ci/land_command.py`, `core/land.py`, `github_api.py` (two reads: the comments of an issue exist already; the permission of a user is new), `core/report.py` (the title line), `core/run_cache.py`, `pass_cache.py` and `post_push_hook.py` (the digest), `README.md` (the sentence about what `land` needs). No new dependency. Out of scope: the workflow that runs `land` (#295), the ruleset (#294, merged).
