## Context

`app setup` runs GitHub's manifest flow and by design sends no credential ("GitHub's answer completes the setup"). A ruleset is created with `POST /repos/<owner>/<repo>/rulesets`, which needs a token with administration rights on the repository. The experiment of #199 (T1–T8) fixed what the ruleset must say: only bypass actors move the branch, a bypass actor's push without `--force` is still refused unless it is a fast-forward, and the built-in `GITHUB_TOKEN` cannot be a bypass actor.

## Decisions

- **The ruleset is a second command, `app ruleset`, not a step of `app setup`.** Rationale: the app is not installed on the repository when `app setup` ends, and GitHub lists only an installed app as a bypass actor; the call also needs the user's admin token, which `app setup` never sees. Way 1 needs no app at all.
- **`app setup --land` is a flag; the default app keeps `checks: write` alone.** Rationale: the issue wants the `report` app to stay at one permission; an app that can write `contents` is a different risk the user should choose.
- **The landing app asks for `checks: write`, `contents: write`, `pull_requests: read` and `workflows: write`.** Rationale: moving the branch needs `contents: write` (GitHub then shows the pull request as merged by itself); #293 reads the pull request comment, which `pull_requests: read` covers; `report` still needs `checks: write` from the same app; GitHub refuses an installation token's push of any change under `.github/workflows/` without `workflows: write`, and with the app as the only bypass actor such a pull request (this repository's own, #296) could otherwise be landed by nobody. No `pull_requests: write` or `administration`: the workflow merges nothing through the API and never changes the ruleset. The app can thus change workflow files; that is the price of landing them, and the user who wants less runs way 1 or the default app.
- **The ruleset is named `prepush-ci landing` and found by that name.** Rationale: `doctor` and `app ruleset` need to find it without guessing among the rulesets a repository already has; a ruleset a user built by hand under another name is not checked.
- **An existing `prepush-ci landing` ruleset is never changed.** Rationale: replacing it could drop an actor the user added on purpose; the user deletes it in the settings and runs the command again.
- **The token is `GITHUB_TOKEN`, then `GH_TOKEN`, and the repository is `origin`, then `GITHUB_REPOSITORY`, as `report` reads them.** Rationale: one convention, so a command that runs in a workflow works as `report` does there; `gh auth token` fills `GH_TOKEN` for anyone using the GitHub CLI.
- **`doctor --ruleset` is opt-in.** Rationale: most repositories never land, and `doctor` exits 1 for any line that is not `ok`; a `skip` or `fail` for a ruleset nobody wants would break every existing use. The six-check output is unchanged without the flag.
- **`doctor --ruleset` accepts the admin role or one app as the single bypass actor.** Rationale: it cannot know which way the repository chose; when `PREPUSH_CI_APP_ID` is set, the app must be that one, which is the app `report` runs as.
- **`doctor --ruleset` also requires nothing excluded, `bypass_mode` `always` and rules without parameters.** Rationale: an excluded default branch protects nothing, a `pull_request` bypass mode cannot push the branch, and `update` with `update_allows_fetch_and_merge` is not the ruleset `app ruleset` makes; each reads `ok` otherwise. A value that means the absence passes: `update_allows_fetch_and_merge` `false` and a missing `bypass_mode` (GitHub's default, `always`). `exempt` fails: it pushes too, but leaves no bypass entry in the audit log.
- **Reading the bypass actors needs an administrator's token.** GitHub omits `bypass_actors` from the answer to anyone else (checked on this repository with a token that has no write rights: the ruleset answers without that field). `doctor` says so and fails instead of passing on a guess.
- **The check looks at the ruleset, not at what GitHub enforces.** Rationale: another ruleset, such as a `pull_request` rule, can still block the lander; `doctor` does not read other rulesets.

## Not verified here

The loop's token has no administration rights on any repository, so no ruleset was created. The request body below is taken from GitHub's documented shape and the experiment of #199, and the first real run, the owner's in #296, confirms the ids, and `doctor --ruleset` shows a mismatch:

```
POST /repos/<owner>/<repo>/rulesets
{"name": "prepush-ci landing", "target": "branch", "enforcement": "active",
 "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
 "rules": [{"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}],
 "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]}
```

`actor_id` 5 is the repository-admin role; for an app it is `{"actor_id": <app id>, "actor_type": "Integration", "bypass_mode": "always"}`. The listing, `GET /repos/<owner>/<repo>/rulesets`, answers without rules or actors; `GET /repos/<owner>/<repo>/rulesets/<id>` holds both (the second field only for an administrator).

## Risks

- A private repository on a free plan answers 403 to the creation; the command passes GitHub's message on and says a paid plan is needed.
- Two rulesets can disagree: a repository that already requires pull requests on its default branch keeps requiring them. `land` then fails with GitHub's own message, which `land` reports.
