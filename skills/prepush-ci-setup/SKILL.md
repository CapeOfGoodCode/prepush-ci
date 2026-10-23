---
name: prepush-ci-setup
description: Set up prepush-ci in a repository so that Claude Code cloud sessions run the full CI check in the pre-push hook and pull request CI skips commits that passed it. Use when the user asks to set up prepush-ci, to "run CI in the session", to "save CI minutes with cloud sessions", or to make pull request CI skip checked commits. Not for changing what the CI checks.
---

# Set up prepush-ci

Goal: after this setup, every commit made in a cloud session carries the trailer `Prepush-CI: full`, the pre-push hook runs the full check before such a commit can leave the machine, and the pull request CI skips commits that carry it. The default branch keeps running CI in full.

Work on a branch and open a pull request with the result; do not push to the default branch. Make no assumption about the CI system: read what the repository has. Ask the user only where this skill says so.

## 0. Preconditions

- The repository is a git repository with a remote, and you can push branches.
- `prepush-ci` is reachable: `uvx prepush-ci --version` (or `pipx run prepush-ci --version`). If the network policy blocks the package index, stop and tell the user which host is needed. Use `uvx` for the commands you run yourself, once; hooks and the SessionStart script never use it (below).
- If `.prepush-ci.toml` already exists, run `uvx prepush-ci doctor`, report its findings, and fix only what it lists.

## 1. Find the full check

1. Read every CI definition in the repository (`.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`, `Jenkinsfile`, `azure-pipelines.yml`, `bitbucket-pipelines.yml`, `.buildkite/`, others). List the commands that run on pull requests: tests, linters, format checks, type checks, builds, other validations. Ignore deploy, release and publishing steps.
2. Look for an entry point that already runs them: `make ci`, `bin/ci`, `npm run ci`, `just ci`, `scripts/ci`, a `tox`/`nox` session.
3. If there is none, or it misses CI steps, write `scripts/ci`: a POSIX sh script with `set -eu` that runs the steps in CI's order. Keep it free of CI-only setup (checkout, caching, service containers).
4. **Ask the user** to confirm the command and the list of steps it covers, naming any CI step you left out and why. Do not continue without a confirmed check.
5. Propose (in the same pull request) that CI calls the same entry point, so the pre-push and CI cannot drift. If the user declines, note the drift risk in the docs.
6. **Have the check write its result files.** The comment that step 8 and step 9 put on the pull request shows test counts and coverage only from files the check wrote. After the check is confirmed and before `init` runs (step 5), have the check write a JUnit XML file to `.prepush-ci/junit.xml` and the coverage report of coverage.py as JSON to `.prepush-ci/coverage.json`, both at the top of the worktree, each only where the rules below allow it.
   - **Where the files come from.** Write the JUnit file for `pytest` only, through its own option (`pytest --junitxml=.prepush-ci/junit.xml -o junit_family=xunit1`), which adds the file and takes nothing from the console output; use an option the runner has built in, and never add a package or plugin to the project. A `vitest`, `jest` or `node --test` check gets no JUnit file, and you tell the user that the comment will show no counts for that check: a reporter named for the file (`--reporter=junit`, `--reporters=jest-junit`) replaces the reporters that the runner chooses itself from the environment (an agent reporter under an agent, `github-actions` in GitHub Actions) and the project's own `reporters`, so the console output of the check would change in the pre-push hook and in CI, and a list of reporters that equals what the runner would choose in every environment cannot be written; `node --test` has a further problem, since its reporter destination does not create `.prepush-ci/`, so on a fresh checkout the run fails with exit 7 and the check turns red. The coverage file is the JSON of coverage.py (`--cov-report=json:.prepush-ci/coverage.json` beside the `--cov` the check already has), and you write it only when the check already measures coverage with coverage.py: never add measurement, because a coverage threshold in the project's configuration would then start to fail the check; a runner that cannot write it gets a JUnit file and no coverage file.
   - **Where the options go.** Only into a check you can show. If the check is a command line, such as a runner call or a chain of commands, add the options to the test command in that line. If it is a `scripts/ci` you wrote in this run (item 3), add the options to the line of the script that runs the tests. For any other entry point (`make ci`, `npm run ci`, `just ci`, a `tox` or `nox` session, or a script that existed before this run), write neither file, change no file of the project, and tell the user that the entry point is the project's and the comment will show no counts.
   - **Only after a direct call of the runner.** The options go to a test command that is a call of `pytest`: `pytest` or `uv run pytest`. When the test command is itself an entry point, as in `ruff check . && make test`, `npm run lint && npm test`, or a `scripts/ci` whose test line is `tox -e py`, write neither file, change no file of the project, and tell the user that the test command is not a call of the runner and the comment will show no counts; never append `--junitxml`, `--reporter`, `--outputFile`, `--test-reporter-destination`, `JEST_JUNIT_OUTPUT_FILE` or `--cov-report` to a Makefile target, a package script or a tox session.
   - **Only where the test command starts at the top of the worktree.** The paths of the options are relative to the directory the test command starts in, so a file would land in another directory than the one step 8 looks in. When a command changes the directory before the test command starts (a `cd` or `pushd` in the chain or the script, `uv run --directory`, `make -C`), as in `cd backend && pytest -q` or a `scripts/ci` whose test line follows a `cd`, write neither file, change no file of the project, and tell the user that the test command runs in another directory and the comment will show no counts. The rule is about the directory in which the test command starts: in `(cd web && npm run build) && pytest -q` the `cd` ended in a subshell before `pytest` started, so the options go to `pytest` here.
   - **One test command.** The files make sense for one test command only: when the check runs tests with more than one command, neither file is written, because the commands would overwrite each other's files and the comment would show part of the tests as the whole; tell the user that the comment will show no counts for that reason.
   - **Leave the check's own output alone.** The options add files and take nothing away. When the check names `--cov` and no `--cov-report`, on its command line or in the runner's configuration (`addopts` of `pytest.ini`, `pyproject.toml`, `tox.ini` or `setup.cfg`), add `--cov-report=term` beside the JSON report: the JSON report alone replaces the table of uncovered lines that pytest-cov prints by default. When the command line or the runner's configuration already writes a JUnit file (`--junitxml` in `addopts`) or a coverage JSON file (`--cov-report=json`), do not add yours, because the later option wins and the check would stop writing the project's file; leave that file out and tell the user that the check already writes its own file and the comment will show no counts for it.
   - **Tell the user, and ask.** Before you change anything, show the user the change (the command line with the added options, or the changed line of `scripts/ci`) and ask for a yes before you make it; leave the check as it is without the yes. The change is small: the change only adds the files and never changes the steps, the selection of tests or the thresholds of the check. For each file left out, for this or any other reason, tell the user which file is left out and why, and leave `--junit` or `--coverage` out of the step 8 call for it. Without the yes the files count as not written, and the step 8 call has neither `--junit` nor `--coverage`.
   - **The ignore line.** Where a file is written, add `.prepush-ci/` to `.gitignore` unless it is ignored already, because the pre-push hook refuses a worktree with untracked files that are not ignored. Do this only when at least one of the files is written; in every case where none is written (a "no", several test commands, an entry point, a test command that is not a runner call, a test command that runs in another directory), leave `.gitignore` as it is.

## 2. Services and preflight

1. List what CI provides besides the code: service containers (PostgreSQL, MySQL, Redis, …), environment variables, secrets used by tests.
2. Check what the cloud container offers (`command -v psql pg_ctlcluster redis-server docker`, installed versions). A different major version is acceptable; say so in the docs.
3. Write the preflight: list required variables for `--require-env <NAME>` (once per variable), or write `scripts/ci-preflight` that exits non-zero when a service is unreachable and pass it as `--preflight "<command>"`. **A missing service must fail the full check, never skip tests.** A suite that skips its database tests while the commit carries the trailer makes the pull request CI skip unchecked code.
4. If a service cannot run in the container at all, tell the user: the full check cannot replace CI for that part, and either that step stays in pull request CI (not skipped) or the setup stops here.

## 3. Look at the existing hooks

Before you change anything, list what the repository already has and tell the user what you found:

- `git config core.hooksPath`, and the effective hooks directory (`git rev-parse --git-path hooks`);
- the files `commit-msg` and `pre-push` in that directory;
- the files of the hook managers: `.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`.

If there is more than one manager, ask the user which one to use and pass the choice as `--hooks`. Without a manager the value is `native`.

## 4. Ask what pre-push should do locally

Stop and ask the user: "What should happen with pre-push on your own machines? (1) keep the existing hooks and run ours after them; (2) install the hooks only in cloud sessions; (3) fold the existing pre-push steps into the full check and remove the old hook." Wait for the answer before you run any command that installs hooks: `init` installs them at once, so the question comes first, never after.

- **Keep the existing hooks** (the default): run `init` with the `--hooks` value you found (step 5).
  - Native hooks: `init` chains the existing hooks, which run first; leave the existing hook files as they are, never edit, move or remove `commit-msg` or `pre-push` in the hooks directory.
  - pre-commit: the only changes to `.pre-commit-config.yaml` are the block `init` writes and the keys `default_install_hook_types` and `default_stages`, every other line stays as it is. Commit these changes together with `.prepush-ci.toml`: committed, the session's `install` finds nothing to change.
  - With pre-commit the hooks set `verbose: true`, and pre-commit then prints the whole output of the check on every push that runs it. In an agent session that output fills the context. Tell the user, and offer a check command that prints a summary and writes the detail to a file, or a quiet mode of the test runner such as `pytest -q`; change the check only with their yes. A quiet mode does not always help: `node --test` prints at least a line per test (up to Node 22, TAP when its output is not a terminal, as in an agent session). Keep `verbose: true`: `doctor` fails without it and `install` writes it back. In an agent session cut the push's own output instead, `git push 2>&1 | tail -n 40`; the post-push hook recognizes that form.
  - husky or lefthook: the only change to the files under `.husky/` or to `lefthook.yml` is the block `init` writes (a new hook file also starts with `#!/usr/bin/env sh`), every other line stays as it is. Commit the block together with `.prepush-ci.toml`.
- **Cloud sessions only**: run `init` with `--hooks none`. It applies when no hook manager is in use: the hooks then exist only where the SessionStart script installs them.
- **Fold into the check**: the tool cannot do this by itself. Show the user the hook file, move its steps into the check command first, and remove the file only after the user confirms it by name. Without that yes, change no hook file.

With a hook manager only the first and the third answer are offered; say so and why: the session's `install` would modify the tracked config and leave the worktree dirty, so that every push refuses, while committing the block gives `commit-msg` and `pre-push` hooks to every developer who runs the manager's install, and they fail where the tool is missing.

## 5. Run init

Run `init` once, with the check from step 1, the preflight from step 2 and the answer from step 4:

```sh
uvx prepush-ci init --non-interactive \
  --check "<check command>" \
  --hooks <hooks> \
  --default-branch "<default branch>"
```

- after a yes, `<check command>` is the confirmed command line with the added options, or `scripts/ci`, unchanged, when the options are in the script; without a yes `<check command>` is the confirmed check unchanged;
- `<hooks>` is `pre-commit`, `husky`, `lefthook` or `native` for answers 1 and 3, `none` for answer 2;
- `<default branch>` comes from two commands, run in this order: `git remote set-head origin --auto`, which refreshes the local record from the remote, then `git symbolic-ref refs/remotes/origin/HEAD`; remove the leading `refs/remotes/origin/` from the output of the second (`refs/remotes/origin/release/1` gives `release/1`). The commands fail when `origin` does not exist, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch); then ask the user for the default branch and do not guess it, and do not use the output of the second when the first failed;
- add `--preflight "<command>"` or `--require-env <NAME>` from step 2; `--require-up-to-date` stays at its default unless the user objects; `--ci github|gitlab|generic|none` picks the gate snippet it prints (default: detected).

`init` writes `.prepush-ci.toml`, installs the hooks, writes the SessionStart script and registers it, and prints the CI gate snippet; do not write those files by hand. If the repository already has legacy trailers from a hand-made version of this setup, add them to `legacy_keys` in `.prepush-ci.toml`. For pre-commit, check that no `args:` duplicate the check command (the config file is the single source of truth).

## 6. Extend the SessionStart script

`init` wrote `.claude/hooks/session-start.sh`. Extend that script with what the repository needs to run its check, after the `prepush-ci install` line; do not write another. It already returns immediately unless `CLAUDE_CODE_REMOTE` is `true`, installs the tool with `uv tool install`, installs the hooks and exports `PREPUSH_CI=full` and `PATH` through `$CLAUDE_ENV_FILE`. Add:

- dependencies from the lockfile (`uv sync --frozen`, `npm ci`, …);
- the services, with the users and databases CI sets up;
- the activation of the hook manager when the repository uses one: `pre-commit install` or `lefthook install` (husky activates itself through its `prepare` script);
- the service variables, as `export NAME=VALUE` lines appended to `$CLAUDE_ENV_FILE`.

Keep it idempotent and well within the hook timeout.

## 7. CI gate

Add the gate for pull/merge request pipelines only. Start from the snippet `init --ci` printed, or from `docs/ci/`. Pull requests from forks never skip and the default branch never skips; say so in the pull request.

- **GitHub Actions:** a first job that checks out the pull request's head commit with enough history and uses `CapeOfGoodCode/prepush-ci@<ref>` (pin a release tag or a commit sha), which exposes `verified`; every other pull request job gets `needs: <gate>` plus `if: needs.<gate>.outputs.verified != 'true'`. Jobs on `push` to the default branch keep running unconditionally. Mention that the gate costs one rounded minute per workflow.
- **GitLab CI:** a `rules:` entry that skips merge request pipelines when `$CI_COMMIT_MESSAGE` contains the trailer, plus `prepush-ci verify "$CI_COMMIT_SHA"` in the first job for the committer check.
- **Other systems:** call `prepush-ci verify "$SHA"` first and exit early with success when it returns 0.

Show the diff and say plainly: this change is where CI minutes are saved, and the default branch stays the backstop.

## 8. Documentation

Add a short section to `CLAUDE.md` (or `AGENTS.md`, whichever the repository uses):

- In cloud sessions `git push` runs the full check and takes about as long as CI; run it with a long timeout (the Bash tool's maximum), not the default.
- What `Prepush-CI: full` means: the commit can only be pushed after the full check passed on it.
- Never use `--no-verify`. To push session commits from a machine that cannot run the full check, run `prepush-ci strip <base>`; CI then runs normally.
- Push one branch at a time (pre-commit hooks see only the first ref).
- After a push of a commit with the trailer to a branch that has a pull request, show the result on it: run `prepush-ci report --markdown --result passed --tree "$(git rev-parse 'HEAD^{tree}')"` and put its output into the one comment of that check. Find the comment whose body holds the marker line `<!-- prepush-ci:` followed by the check's name (the first line of the output) and update it; create a comment only when none holds the marker. Never use `--edit-last`: it edits the last comment of the user, whatever it says. If the branch has no pull request, post nothing.

Also add a sentence to the README for humans: how to opt in locally (`export PREPUSH_CI=full`) and that nothing changes for them otherwise.

## 9. Show the result after every push

The rule above depends on the agent remembering it. A Claude Code hook can do it after every successful `git push`: `prepush-ci hook post-push` runs after each command of the agent and, when the command pushed a commit with the trailer that passed the check, creates or updates the one comment of the check on the pull request of the branch; it does nothing when the branch has none. Tell the user in a sentence what the hook does and ask the user for a yes. Without a yes, change no file; the rule above stays for agents without hooks, and stays when the hook is added.

With the yes, add this group to `hooks.PostToolUse` of `.claude/settings.json`; keep every other setting, and add nothing when a command there already runs `hook post-push`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "d=$(uv tool dir --bin 2>/dev/null) && [ -n \"$d\" ] && PATH=\"$d:$PATH\"; command -v prepush-ci >/dev/null 2>&1 && prepush-ci hook post-push || true",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

The command is `d=$(uv tool dir --bin 2>/dev/null) && [ -n "$d" ] && PATH="$d:$PATH"; command -v prepush-ci >/dev/null 2>&1 && prepush-ci hook post-push || true`: it puts the directory `uv tool install` uses in front of `PATH` only when `uv` prints one (an empty entry in `PATH` is the current directory, where a cloned repository could plant a `prepush-ci`), runs the hook only when `prepush-ci` is found, and exits 0 whatever happens. The settings file is committed, so every teammate gets the hook, and the hook does nothing until the tool is installed (`uv tool install prepush-ci`): tell the user so. The hook gives up by itself after 15 seconds and always exits 0; the `timeout` is the backstop.

## 10. Prove it

The SessionStart hook did not run for the current session. Then:

1. Run `.claude/hooks/session-start.sh` by hand (with `CLAUDE_CODE_REMOTE=true` and `CLAUDE_ENV_FILE` set) and source the exported variables into your shell.
2. Run `prepush-ci doctor --mode full`; fix everything it reports.
3. Commit the setup on the branch. This commit may lack the trailer (the hooks were not installed yet when it was written); that is harmless, CI runs in full on it.
4. Make a second, trivial commit (e.g. the docs section). Confirm with `git log -1 --format=%B` that it carries `Prepush-CI: full`.
5. Push with a long timeout; show that the full check ran and passed.
6. Open the pull request (as a draft if the repository runs no CI on drafts, then mark it ready) and report what the CI did: the gate verified the head commit and skipped the other jobs.

## Report to the user

End with: the confirmed check command, the services started in the session and their versions, what the gate skips and what it never skips, measured times (full check in the session vs. the last CI run), and anything left open (steps that cannot run in the container, CI drift if CI does not call the same entry point).
