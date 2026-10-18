# Tasks

## 1. The command and its refusals

- [ ] 1.1 Add `prepush-ci report` with `--result`, `--tree`, `--commit`, `--name`, `--duration`, `--tool`, `--junit` and `--coverage`, the exit statuses, the refusals (no worktree, usage errors with exit 2, malformed `--tool`, `--duration` and `--name`, unresolved commit, tree mismatch, bad input files) and the one output line; verify with specs for each refusal, which must send no request
- [ ] 1.2 Add reading of the repository from `origin` (userinfo ignored, `ssh://` form, `GITHUB_REPOSITORY` when `origin` has none) and of `GITHUB_API_URL`; verify with specs for the URL forms, a remote that is not GitHub, empty variables and an API error or refusal that is reported without a secret or the remote's userinfo

## 2. The summary

- [ ] 2.1 Add JUnit counting (by test case, pytest and node shapes) and the coverage reading, with the refusal of a `passed` result that has failing tests; verify with unit specs for both shapes and each refusal
- [ ] 2.2 Add the summary text (commit, tree, check, preflight, tools, OS, duration, counts, coverage); verify with specs on the body the local server receives

## 3. Posting

- [ ] 3.1 Add the commit status (state, context, description); verify with specs for a pass, a failure, `--name` and a description without files
- [ ] 3.2 Add the app path (JWT through `openssl`, installation lookup, token, check run) and the choice between app and status; verify with specs that check the JWT's signature against the public key, the claims, an app without a key, an uninstalled app, a missing `openssl` and the absence of the key and the token from the output

## 4. The README

- [ ] 4.1 Add the entry for `report` to the README's reference, with every flag in its synopsis and its exit statuses, and copy the `Purpose` of `report` from this `design.md` into `openspec/specs/report/spec.md` when the change is archived; verify with the drift checks of the `readme` capability. The prose on setting up an app is #201's.
- [ ] 4.2 Run `sh scripts/ci` and verify it passes
