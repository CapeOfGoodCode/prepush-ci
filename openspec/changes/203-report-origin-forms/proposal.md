Issue: #203

## Why

`prepush-ci report` reads the repository from `origin` in three forms only. A user whose `origin` is a short alias (`url.<base>.insteadOf`, a common way to type `gh:acme/widgets`) or GitHub's ssh over the HTTPS port (`ssh.github.com:443`, the way out of a network that blocks port 22) gets "no repository could be read from `origin`" and a failed `report`, although git itself knows the repository. Without this change the only way out is to set `GITHUB_REPOSITORY` by hand.

## What Changes

- `report` reads the URL of `origin` the way `git remote get-url origin` prints it, so `insteadOf` rewrites apply.
- `ssh.github.com` counts as GitHub's host, in every form the spec lists (with or without a port).
- An ssh host alias from `~/.ssh/config` (`git@github.com-work:acme/widgets.git`) stays unsupported: `report` cannot tell it from a proxy, and `GITHUB_REPOSITORY` already names the repository. The spec now says so.

## Capabilities

### Modified Capabilities

- `report`: where the result is posted (the URL of `origin` and the hosts that count as GitHub) and the API address (the same hosts).

## Impact

- `src/prepush_ci/report_command.py` reads `origin` through `git remote get-url`; `src/prepush_ci/core/report.py` accepts `ssh.github.com` beside `github.com`.
- No change to the README: it does not list the URL forms.
