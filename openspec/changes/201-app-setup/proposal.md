Issue: #201

## Why

`report` posts a check run only as a GitHub App the team owns, and creating an app by hand means filling in a form with the right permission and copying an id and a key. A one-click setup makes the check run available to a team without a platform engineer, and keeps the app to the one permission it needs (#196, step 1; split from #197 so each slice is reviewable in one sitting).

## What Changes

- `prepush-ci app setup` creates the app with GitHub's manifest flow: one click in the browser, `checks: write` and nothing else, no server of ours (a page on the loopback address serves the click and receives GitHub's answer, then stops).
- The private key is saved outside the repository with owner-only permissions. The command prints the app id, where to install the app and the environment variables `report` reads.
- The README gets an entry for `app setup`, and the builder adds a paragraph on setting the app up, backed by `app-setup` and `report` (the `readme` spec pins only the entry).

## Capabilities

### New Capabilities

- `app-setup`: the command, the manifest it sends, the exchange of GitHub's code for the app, where the key goes and what is printed.

### Modified Capabilities

- `readme`: the reference has an entry for `app setup`.

## Impact

- New `src/prepush_ci/app_setup_command.py` (the loopback page, the wait, the key file), a pure `src/prepush_ci/core/app_setup.py` (manifest, names, paths, callback decision), one request added to `src/prepush_ci/github_api.py` (the code exchange), and `app setup` in `src/prepush_ci/cli.py`.
- `README.md`: an entry in the command reference and a paragraph on the setup.
- The app needs no other permission: `report` already works with `checks: write` (see `report`, "Authenticating as the app").
