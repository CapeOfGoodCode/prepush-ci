---
name: prepush-ci-setup
description: Set up prepush-ci in a repository so that Claude Code cloud sessions run the full CI check in the pre-push hook and pull request CI skips commits that passed it. Use when the user asks to set up prepush-ci, to "run CI in the session", to "save CI minutes with cloud sessions", or to make pull request CI skip checked commits. Not for changing what the CI checks.
---

# Set up prepush-ci

Goal: after this setup, every commit made in a cloud session carries the trailer `Prepush-CI: full`, the pre-push hook runs the full check before such a commit can leave the machine, and the pull request CI skips commits that carry it. The default branch keeps running CI in full.

Work on a branch and open a pull request with the result; do not push to the default branch. Make no assumption about the CI system: read what the repository has. Ask the user only where this skill says so.

## 0. Preconditions

- The repository is a git repository with a remote, and you can push branches.
- `prepush-ci` is reachable: `uvx prepush-ci --version` (or `pipx run`). If the network policy blocks the package index, stop and tell the user which host is needed.
- If `.prepush-ci.toml` already exists, run `uvx prepush-ci doctor`, report its findings, and fix only what it lists.

## 1. Find the full check

1. Read every CI definition in the repository (`.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `Jenkinsfile`, `azure-pipelines.yml`, `bitbucket-pipelines.yml`, `.buildkite/`, others). List the commands that run on pull requests: tests, linters, format checks, type checks, builds, other validations. Ignore deploy, release and publishing steps.
2. Look for an entry point that already runs them: `make ci`, `bin/ci`, `npm run ci`, `just ci`, `scripts/ci`, a `tox`/`nox` session.
3. If there is none, or it misses CI steps, write `scripts/ci`: a POSIX sh script with `set -eu` that runs the steps in CI's order. Keep it free of CI-only setup (checkout, caching, service containers).
4. **Ask the user** to confirm the command and the list of steps it covers, naming any CI step you left out and why. Do not continue without a confirmed check.
5. Propose (in the same pull request) that CI calls the same entry point, so the pre-push and CI cannot drift. If the user declines, note the drift risk in the docs.

## 2. Services and preflight

1. List what CI provides besides the code: service containers (PostgreSQL, MySQL, Redis, …), environment variables, secrets used by tests.
2. Check what the cloud container offers (`command -v psql pg_ctlcluster redis-server docker`, installed versions). A different major version is acceptable; say so in the docs.
3. Write or extend `.claude/hooks/session-start.sh` and register it in `.claude/settings.json` under `hooks.SessionStart`. It must:
   - return immediately unless `CLAUDE_CODE_REMOTE` is `true` (laptops are not touched);
   - install dependencies with the lockfile (`uv sync --frozen`, `npm ci`, …);
   - start the services and create users/databases the way CI does;
   - run `uvx prepush-ci install` (or the repository's hook manager install);
   - export `PREPUSH_CI=full` and the service variables by appending `export NAME=VALUE` lines to `$CLAUDE_ENV_FILE`;
   - be idempotent and finish well within the hook timeout.
4. Write the preflight: list required variables in `require_env`, or write `scripts/ci-preflight` that exits non-zero when a service is unreachable. **A missing service must fail the full check, never skip tests.** A suite that skips its database tests while the commit carries the trailer makes the pull request CI skip unchecked code.
5. If a service cannot run in the container at all, tell the user: the full check cannot replace CI for that part, and either that step stays in pull request CI (not skipped) or the setup stops here.

## 3. Hooks and config

Run `uvx prepush-ci init --non-interactive` with:

- `--check "<confirmed command>"`, `--preflight …` or `--require-env …` from step 2;
- `--hooks <manager>`: `pre-commit` if `.pre-commit-config.yaml` exists, `husky` or `lefthook` if configured, else `native` (`core.hooksPath`);
- `--default-branch <name>` from `git symbolic-ref refs/remotes/origin/HEAD`;
- `--require-up-to-date origin/<default branch>` (the default; leave it on unless the user objects).

For pre-commit, check that `default_install_hook_types` contains `commit-msg` and `pre-push` and that no `args:` duplicate the check command (the config file is the single source of truth). If the repository already has legacy trailers from a hand-made version of this setup, add them to `legacy_keys`.

## 4. CI gate

Add the gate for pull/merge request pipelines only. Never skip on the default branch, and never for pull requests from forks.

- **GitHub Actions:** a first job that runs `prepush-ci verify "${{ github.event.pull_request.head.sha }}"` after a checkout with enough history (or uses `prepush-ci/gate@v1` if the user prefers), exposes `verified`, and every other pull request job gets `needs: <gate>` plus `if: needs.<gate>.outputs.verified != 'true'`. Jobs on `push` to the default branch keep running unconditionally. Mention that the gate costs one rounded minute per workflow.
- **GitLab CI:** a `rules:` entry that skips merge request pipelines when `$CI_COMMIT_MESSAGE` contains the trailer, plus `prepush-ci verify` in the first job for the committer check.
- **Other systems:** call `prepush-ci verify` first and exit early with success when it returns 0.

Show the diff and say plainly: this change is where CI minutes are saved, and the default branch stays the backstop.

## 5. Documentation

Add a short section to `CLAUDE.md` (or `AGENTS.md`, whichever the repository uses):

- In cloud sessions `git push` runs the full check and takes about as long as CI; run it with a long timeout (the Bash tool's maximum), not the default.
- What `Prepush-CI: full` means: the commit can only be pushed after the full check passed on it.
- Never use `--no-verify`. To push session commits from a machine that cannot run the full check, run `prepush-ci strip <base>`; CI then runs normally.
- Push one branch at a time (pre-commit hooks see only the first ref).

Also add a sentence to the README for humans: how to opt in locally (`export PREPUSH_CI=full`) and that nothing changes for them otherwise.

## 6. Prove it

The SessionStart hook did not run for the current session. Then:

1. Run `.claude/hooks/session-start.sh` by hand (with `CLAUDE_CODE_REMOTE=true` and `CLAUDE_ENV_FILE` set) and source the exported variables into your shell.
2. Run `uvx prepush-ci doctor`; fix everything it reports.
3. Commit the setup on the branch. This commit may lack the trailer (the hooks were not installed yet when it was written); that is harmless, CI runs in full on it.
4. Make a second, trivial commit (e.g. the docs section). Confirm with `git log -1 --format=%B` that it carries `Prepush-CI: full`.
5. Push with a long timeout; show that the full check ran and passed.
6. Open the pull request (as a draft if the repository runs no CI on drafts, then mark it ready) and report what the CI did: the gate verified the head commit and skipped the other jobs.

## Report to the user

End with: the confirmed check command, the services started in the session and their versions, what the gate skips and what it never skips, measured times (full check in the session vs. the last CI run), and anything left open (steps that cannot run in the container, CI drift if CI does not call the same entry point).
