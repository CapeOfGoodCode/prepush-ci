# Design

## Context

`SKILL.md` is read by an agent and cannot be unit-tested for behavior; what can be tested is that it tells the truth about the CLI and keeps its promises in order. This change specifies those checkable properties. The prose itself stays the builder's to write within them. Section 6 of #1 (the skill) and the maintainer's comment on #1 (existing pre-push setups, ask about pre-push locally) are the sources.

## Goals / Non-Goals

**Goals:** a setup that cannot name a missing command or action; no hand-written copy of what `init` writes; existing hooks looked at and never removed without a yes; the pre-push question asked before anything is installed.

**Non-Goals:** testing the agent's judgment (choosing the check command, reading CI files); changing any CLI behavior; the README (#86).

## Tools run

Run in scratch repositories with the repository's own build (`uv run --project <repo> prepush-ci`, version `prepush-ci 0.0.0`), to settle what the skill may promise:

- `prepush-ci init --non-interactive --check "sh ci.sh" --hooks none --ci github` printed `written: .prepush-ci.toml`, `skipped: hooks (--hooks none)`, `written: .claude/hooks/session-start.sh`, `written: .claude/settings.json`, then the gate snippet (`uses: CapeOfGoodCode/prepush-ci@main`). The script it wrote runs `uv tool install prepush-ci`, then `prepush-ci install`, and exports `PATH` and `PREPUSH_CI=full` through `CLAUDE_ENV_FILE`. It contains no `uvx` and no manager activation.
- With an executable `.git/hooks/pre-push` that echoes `my old pre-push`, `init --non-interactive --check "sh ci.sh" --ci none --no-session-hook` printed `installed: …/.git/prepush-ci/hooks` and `hooks kept from: …/.git/hooks`. A push of a trailer commit printed `my old pre-push` first, then our hook ran: the existing hook is chained and runs first.
- With a `.pre-commit-config.yaml` and `--hooks none`, nothing was added to the file. A later `prepush-ci install` (what the SessionStart script runs) printed `installed: pre-commit`, left `.pre-commit-config.yaml` modified (pre-commit 4.6.2) and printed `next: run pre-commit install`. A modified tracked file makes the pre-push hook refuse (the worktree must be clean, #1 section 2).
- With a `.pre-commit-config.yaml`, `init --non-interactive --check true --hooks pre-commit --ci none --no-session-hook` printed `written: .prepush-ci.toml`, `installed: pre-commit` and modified `.pre-commit-config.yaml` (`default_install_hook_types: [pre-commit, commit-msg, pre-push]`). After a commit of both files, `prepush-ci install --hooks pre-commit` printed `already installed: pre-commit` and the worktree stayed clean.
- With `.husky/pre-push` (`npm test`) and `lefthook.yml` committed, `init --non-interactive --check true --hooks husky --ci none --no-session-hook` printed `installed: husky` and left `.husky/pre-push` modified (our block first, `npm test` kept after it) and `.husky/commit-msg` and `.prepush-ci.toml` untracked; `--hooks lefthook` left `lefthook.yml` modified (a `prepush-ci` command added under `pre-push` and a new `commit-msg` section, the existing `t` command kept). After a commit of those files, `install --hooks husky` and `install --hooks lefthook` printed `already installed` and the worktree stayed clean. So for every manager the block `init` writes must be committed, or the pre-push hook refuses on a dirty tree.
- `prepush-ci --help` (`prepush-ci 0.0.0`) ends with `also: verify <sha> exit 0 when a commit carries the trailer and was not made by a server`; `prepush-ci verify --help` printed `not verified: --help --help is an option, not a sha` and exited 1.
- `prepush-ci doctor` in the first repository, with no remote, failed only the `up-to-date` line with a `fix:` line and exit 1.

## Decisions

- **`verify` is checked by its shape.** It is not a parser subcommand, so `prepush-ci verify --help` exits 1 (`--help` is not a sha, `verify` spec). The top-level `--help` lists it in its `also:` line, so the check counts it as existing when that line names it and accepts one `<sha>` and no option.
- **The CLI is the source of truth; the check parses `--help`.** Every `prepush-ci …` invocation in a code block or code span is split into command words and options; the test accepts a command if `prepush-ci <words> --help` exits 0 and an option if that help lists it. No second list to maintain.
- **The `init` invocation is run, not only parsed.** Parsing proves the flags exist, not that the command is complete (`--check` is required). The test substitutes each `<placeholder>` and runs it once in a scratch repository.
- **Ask before `init`, never after.** `init` installs hooks at once. Asking afterwards asks about something already done, so the question comes before the step that runs `init`, and the order is a test.
- **Three answers, no more.** (1) keep the existing hooks and run ours after them (the default; what `install` does); (2) hooks only in cloud sessions; (3) fold the existing pre-push steps into the full check and remove the old hook. The tool cannot do (3) by itself, so the skill does it only on a yes that names the file.
- **"Cloud sessions only" is offered for native hooks only.** With a manager there is no variant that leaves tracked config and developers' machines alone: the session's `install` edits the tracked config (see above), and a committed block gives `commit-msg` and `pre-push` hooks to every developer who runs `pre-commit install` (the config sets `default_install_hook_types`), which fail with `Executable prepush-ci not found` where the tool is missing. The skill therefore leaves the answer out for a manager and says why; the user keeps answers 1 and 3. Committing the block first leaves the session's `install` with nothing to change (see above).
- **The skill owns the manager activation.** `init` leaves `pre-commit install` and `lefthook install` to the skill (init spec), so the skill adds them to the SessionStart script it extends.
- **Interactive commands may use `uvx`; hooks and the SessionStart script may not.** A hook needs the tool on `PATH` at every commit; `uvx` there is slow and fails offline. `uvx prepush-ci doctor` run by the agent once is fine.
- **Until the first release exists on PyPI the precondition `uvx prepush-ci --version` fails.** The skill is shipped with the release; the check does not run the network.

## Risks / Trade-offs

- [Prose checks are string checks] → they pin only what a wrong skill got wrong before: names, order and one question; the proof in the pull request shows the whole file.
- [The check runs `--help` for each invocation] → one subprocess per distinct command; the table of commands is small.
