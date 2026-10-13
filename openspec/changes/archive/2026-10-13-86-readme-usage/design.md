# Design

## Context

`README.md` is the PyPI long description and the first page a user reads. Prose cannot be unit-tested for its sense; what can be tested is that it names no command or flag that does not exist, leaves none out, and says the few facts a user acts on. #15 built that check for `SKILL.md`; this change reuses it. The prose stays the builder's to write within the requirements.

## Goals / Non-Goals

**Goals:** a README whose commands, flags, `PREPUSH_CI` values and config keys cannot drift from the CLI; a usage path from install to a refused push.

**Non-Goals:** the animation (own slice); a plugin or marketplace package of the skill; a change to `SKILL.md`; changing any CLI behavior; changing the "Status: under construction" note (it changes with the release, not with this slice); the text of the existing "How it works" and "How this repository is built" sections.

## Tools run

`prepush-ci 0.0.0` from the repository's own build (`uv run --project <repo> prepush-ci`), uv 0.13.0, to settle what the reference lists and which exit codes it may promise:

- `prepush-ci --help` lists `{hook,run,install,init,doctor,strip}` and ends with `also: verify <sha> exit 0 when a commit carries the trailer and was not made by a server`. `hook --help` lists `{commit-msg,pre-push}`.
- Flags (from `--help`): `init` has `--non-interactive`, `--check`, `--preflight`, `--require-env`, `--require-up-to-date`, `--default-branch`, `--hooks {native,pre-commit,husky,lefthook,none}`, `--no-session-hook`, `--ci {github,gitlab,generic,none}`, `--ci-gate-file`; `install` has `--hooks {native,pre-commit,husky,lefthook}`; `doctor` has `--hooks {…,none}` and `--mode {full,off,unset}`; `strip` takes `[base ...]`; `hook commit-msg` takes `file`; `hook pre-push` takes `[git_args ...]`; `run` has none.
- In a scratch repository: `doctor` without hooks and config exits 1; `doctor --hooks foo` and `install --hooks foo` exit 2 (argparse, "invalid choice"); `run` without config exits 1; `verify HEAD` in a repository without commits prints `not verified: HEAD …` and exits 1; `strip a b` exits 1 (`expected at most one <base>`); `init --non-interactive` without `--check` exits 2 naming `--check`.
- A config with an unknown key `foo` and `trailer = { zz = 1 }`: `doctor` prints `unknown key `foo` (known keys: check, preflight, require_env, require_up_to_date, default_branch, trailer, legacy_keys, cache)` and `unknown key `trailer.zz` (known keys: key, value)`. The config therefore tells its own keys; no second list is needed.

## Decisions

- **The README is held to the CLI by the same check as `SKILL.md`.** One checker, two files; the `skill` capability keeps its requirements. The checker moves to one shared place (pytest runs with `--import-mode=importlib`, so spec files import nothing from each other: a fixture in `tests/integration/conftest.py` fits; the builder picks). No second copy to drift.
- **Completeness is checked both ways.** The issue asks that the check fails on a command the README lacks as well as one the CLI lacks. The commands come from `--help` (the parser's choices, `hook`'s choices, and `verify` from the `also:` line); the flags from the `--help` of each command, without `-h` and `--help`. A flag left out of the reference is a finding, because the synopsis is the reason to read the reference.
- **The config keys come from the CLI's own message.** The test provokes the `unknown key` message above and reads the key lists from it, so the README's list is compared with what the config accepts, not with a copy in the tests. `trailer` sub-keys (`key`, `value`) are compared the same way.
- **The defaults are compared, not only the keys.** A key set that matches with a wrong default is the drift this change exists to stop. The README lists defaults in a `key | default` table in the canonical forms of the `config` spec (`none`, `[]`, `origin/<default_branch>`), and the test compares each with what the config loads for a config that sets only `check`; the builder picks how it reads the loaded config.
- **`PREPUSH_CI` is described by its two hooks, not by one slogan.** `off` only stops the trailer: the pre-push hook refuses a tip that carries one (`pre-push-hook`, "Off refuses a demanding tip") and `strip` is the way out; an unset or empty variable also writes no trailer but a tip that carries one is still checked. The README says each in those terms.
- **Exit codes only where they carry meaning.** `run`, `verify`, `doctor` and `strip` (0 or 1) and `init` (0, 1, and 2 when `--check` is missing); the hooks' exit code is the push or commit being refused. Not listed for `install` and the others: a command line the parser rejects exits 2 everywhere, said once.
- **The reference lists `hook commit-msg` and `hook pre-push` as commands of their own**, because the hook scripts call them and a reader debugging a hook meets them; the entry says they are for git, not for a person.
- **One example per command is not run.** The invocation check proves the command and the flags exist; running every example would need a repository per command. `init`'s invocation is already run by the `skill` capability.
- **Absolute links only.** The README is the PyPI description; `readme_links_spec.py` already enforces it and stays as it is.
- **The agent setup is the first step of the usage section, the manual steps follow (review of #122, 2026-10-13).** The maintainer says the main use case is an agent setting the tool up with the skill; the detailed part of the README then serves agents as much as people, and needs no framing as such. The manual steps stay as the core; the agent step says so and names what the skill does on top (the check command, services and preflight, the SessionStart script, the `doctor` proof), because the skill protects the invariant that a missing service fails the check, which the manual steps do not mention.
- **Two ways to give the agent the skill, both from files the repository has.** A prompt with an absolute link to `SKILL.md` works with any agent that can read a URL; copying `skills/prepush-ci-setup/` into `.claude/skills/` makes it a project skill of Claude Code. A plugin or marketplace entry would be packaging the repository does not have; it is not specified here.
- **The link is checked against the repository, not against the network.** The test resolves the path of the link in the repository (the README is read at the same commit as `skills/`), so a renamed skill breaks the check.
- **The README claims only what the skill's spec pins.** The agent step says the user always confirms the check and is asked about pre-push, is asked more only where the repository leaves something open, and gets a pull request. The pre-push question and the other questions are requirements of the `skill` capability already; the check confirmation, the branch and pull request, the check command and the services were true of `SKILL.md` but unspecified, so the `skill` delta adds them. A README that promised more than the spec holds would drift.
- **Best practices for a repository an agent can set up (the maintainer's question).** What an agent needs is a command that runs the whole check, services it can name, an explicit statement of what it may not do, and a way to prove the result. The tool already gives the agent a non-interactive `init`, a `doctor` that proves the setup, exit statuses and messages that name the next step, and a skill that always asks two questions and others only where the repository leaves something open. On the repository side, one entry point for the check (`scripts/ci`, `make ci`) is the single thing worth having: skill step 1 looks for it and writes one when it is missing. A further document (an `AGENTS.md` pointer, a list of conventions for tool authors) is not part of this change; if the maintainer wants it, it is a slice of its own.

## Risks / Trade-offs

- [A flag list in prose is a string match] → the match is on the flag as a word (not inside a longer flag), as the skill check does; a README that lists a flag only in a code block passes, which is where it is shown.
- [Every new flag now needs a README line] → intended: a flag nobody can find is not shipped.
