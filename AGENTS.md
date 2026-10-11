# AGENTS.md

The rulebook for everyone who changes this repository, human or agent. `README.md` says what the tool is; [`LOOP.md`](LOOP.md) says how the loops that build it work together. Follow them; don't restate them.

## Language

- **Everything in this repository is English**: code, comments, tests, specs, commits, issues, pull requests, this file. This holds whatever language the conversation is in.

## Scope and backlog

- **Issue #1 is the intent.** It is the scope contract for the first release. Decisions it leaves open are made by whoever picks them up, with a one-line rationale in the commit body (the intent asks for exactly this).
- **Every piece of work is an issue** with an issue type: `Epic` (issue #1), `Feature`, `Bug`, `Improvement`, `Refactoring` or `Task`. Ideas, follow-ups and bugs become issues right away (`gh issue create --type …`), never TODO comments. Anything outside the intent gets the label `proposal` and waits for a human.
- **Structure is native, not prose**: slices of the intent are sub-issues of #1 (`--parent 1`); dependencies are "blocked by" relations (`--blocked-by <n>`). Pick up an issue only when nothing blocks it.
- **Types say what an issue is; labels say whose move it is** (`LOOP.md`).

## OpenSpec

- **Behavior is specified before it is built.** A feature or a behavior-changing bug fix is an OpenSpec change named `<issue>-<name>` (e.g. `openspec new change 4-pre-push-hook`); `proposal.md` starts with `Issue: #<n>`. Use the `/opsx:*` commands or the `openspec-*` skills.
- **Specs use SHALL and scenarios** (`#### Scenario:` with WHEN/THEN). Every scenario is covered by at least one test whose name says the same thing.
- **Archive before merge.** The implementation pull request ends with archiving its change (`openspec archive <change>`), so specs in `openspec/specs/` always describe `main`.
- `npx openspec validate --all --strict` must pass (part of `scripts/ci`).

## Commits

- **Conventional Commits**: `type(scope): subject`, type one of `feat, fix, docs, refactor, test, chore`; subject imperative, lowercase, at most 100 characters. Enforced by commit-check (`cchk.toml`).
- **Scope** is the OpenSpec change (`feat(4-pre-push-hook): …`) or the issue number (`fix(12): …`). Bootstrap commits may omit it.
- **Type is the primary intent.** A feature's tests and docs ride in its `feat:` commit. OpenSpec artifacts are `docs:` commits of their own.
- **Atomic**: one logical change per commit. If the subject needs "and", split it.
- **Agent commits end with trailers** naming the model and, for a loop, the loop:

  ```
  Co-Authored-By: <Model Name> <noreply@anthropic.com>
  Loop: <loop name>
  ```

## Branches and pull requests

- **One branch per issue**: `<type>/<issue>-<name>`, e.g. `feat/4-pre-push-hook`. Nothing but bootstrap is committed on `main`.
- **Pull requests** follow `.github/pull_request_template.md`, start with `Closes #<n>`, and carry a **Proof** section: what a reviewer can see without running anything (new test names, a terminal transcript of the tool doing the new thing). CI fails a pull request without it.
- **Only a human merges**, rebase merge only. Rebase onto the latest `main` before asking for the merge; update with `git push --force-with-lease`, never `--force`.

## Testing

- **Tests are specs**: they live in `tests/`, files are named `*_spec.py` (pytest collects nothing else), and test names read as sentences about behavior: `test_pre_push_refuses_a_trailer_commit_when_the_worktree_is_dirty`.
- **Two tiers, both run by `scripts/ci`**:
  - `tests/unit/`: pure logic, no I/O (trailer parsing, config, ref lines, the `verify` decision). Keep that logic in modules that do no I/O so it can be tested here.
  - `tests/integration/`: the behavior a user sees, against real temporary git repositories (`git init` in `tmp_path`), with hooks run by real `git commit`/`git push`. Never mock git.
- End-to-end use of the released tool (`uvx` in throwaway repositories) is not part of the suite; terminator does it (`LOOP.md`).
- **Never weaken a test to make it pass**, never skip one silently. A test that cannot run fails.
- **Coverage** (branch, gated in `scripts/ci`): `src/prepush_ci/core/` at **100% from `tests/unit` alone** (a branch only an integration test reaches does not count), everything at **95%** overall, including code the tests start as a subprocess through git. `core/` does no I/O (a unit spec enforces it). Every `# pragma: no cover` carries a comment saying why.

## Versioning

- **Semantic versioning**; the version lives only in `pyproject.toml`. Until 1.0.0, a minor bump may break the CLI or config; say so in the release notes.
- **Only a human releases**: bump the version in a `chore(release): …` pull request, then push the tag `vX.Y.Z` on `main`. `.github/workflows/release.yml` refuses a tag that does not match the version, publishes to PyPI and creates the GitHub release.

## Quality gates

- **`scripts/ci` is the full check**: ruff, format, `mypy --strict`, pytest, OpenSpec validation. The pre-push hook and CI run the same script, so they cannot drift. Run it before you ask for review.
- **Hooks**: `uv run pre-commit install` installs commit-msg (commit-check), pre-commit (ruff) and pre-push (`scripts/ci`). Claude Code also runs ruff after every edit and blocks a few dangerous commands (`.claude/hooks/`).
- **Never bypass hooks** (`--no-verify`).

## Working in this repository

- **uv for Python, npm only for the OpenSpec CLI**: `uv sync && npm ci`, then `uv run <tool>`.
- **Layout**: `src/prepush_ci/` (the tool, standard library only), `tests/` (specs), `openspec/` (specs and changes), `scripts/ci` (the full check), `.claude/` (agent hooks and skills).
- **No runtime dependencies** unless an OpenSpec change argues for one: `uvx prepush-ci` should start fast and install nothing.
- **Decide and proceed**: make implementation decisions (file layout, internal APIs, test structure) yourself, with a one-line rationale in the commit body. Pause only when a decision changes the intent's scope or contradicts a spec.
