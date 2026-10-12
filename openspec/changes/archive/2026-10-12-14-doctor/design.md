# Design

## Context

`doctor` is the diagnosis of the intent (#1, section 4.3). It adds no behavior to the hooks; it asks the questions the hooks would answer with a refusal, before a push does. See `proposal.md` for the why and the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** every reason a push is refused or a trailer is missing that the tool can see shows up as one line with its fix; the report is the same on a laptop and in a cloud session.

**Non-Goals:** repairing anything (`install` and `init` do that), judging the check command itself, deciding whether `HEAD` contains the default branch (that depends on the branch being pushed and is the hook's job), checking the CI gate.

## Decisions

- **One line per check, fixed order, never stops early.** A user with three problems should see three lines, not fix one and meet the next. The six names are stable so a script can grep them.
- **A check that needs the config is `skip` when the config is bad.** `preflight` and `up-to-date` have nothing to read; saying `ok` would lie and omitting them would hide that they were not run. `skip` is not a pass, so the exit status is 1 either way.
- **"Installed" means "git would run it".** Native hooks need our hooks directory in the effective `core.hooksPath`, an executable script of the name and a recorded interpreter that exists. A manager's hooks need the block in its file and the manager's own activation: the hook script it writes into the directory git uses (`pre-commit install`, `lefthook install`, husky's `.husky/_`): a block that no git hook calls checks nothing, and that is the commonest failure of a fresh clone.
- **Activation is judged from the installed hook script.** The hook of the name in the directory git uses must exist, be executable and, for pre-commit and lefthook, contain the manager's name. husky's stubs are generated and git-ignored, so `core.hooksPath` alone can outlive them (`git clean -fdx`, a fresh worktree) and git then runs nothing; husky is held to the same rule without the content marker. The tool does not run the manager or parse its output.
- **The closing count counts every line that is not `ok`.** A `skip` is a check that did not pass, so a missing config is `3 of 6`: the config and the two checks it blocks.
- **`doctor --hooks none` passes the hook checks.** `init --hooks none` (#12) is a choice, and a repository that made it should be able to reach exit 0. `doctor` cannot know the choice by itself; without the flag a repository with a detected manager is judged by it, and the fix lines name `--hooks native` so a user who chose native hooks over a manager finds the way. `install` does not learn `none`.
- **`doctor` takes `--hooks`, with `install`'s values and detection.** Two managers make `install` refuse without it, and a diagnosis that can only answer "several managers" for ever would be useless. The same choice means the repository `install` just fixed is the repository `doctor` checks.
- **`PREPUSH_CI` passes for every value the hooks accept, including unset.** On a laptop, unset is the normal state. `--mode full|off|unset` is for the place that knows what it expects (a cloud session's SessionStart script, the skill): the check then also compares. Without the flag `doctor` cannot tell a missing export from a choice.
- **"Reachable" means the remote has the branch, read with `git ls-remote` without a credential prompt (`GIT_TERMINAL_PROMPT=0`).** A diagnosis that waits for a password on a terminal is no diagnosis; a remote that needs credentials it cannot get is one that cannot be reached. It writes nothing, unlike the fetch the hook does, and proves the same thing the user needs: the remote answers and has the ref. Whether `HEAD` contains it is left to the hook.
- **The `preflight` command is run, its output shown only on failure.** The intent asks that preflight passes, and only running it tells. It runs as the hook runs it. It is the user's command and may do what it likes; `doctor` itself writes nothing. A missing variable stops it, as in the hook.
- **No timeout of its own.** A `preflight` that hangs hangs the hook too; `doctor` shows the same.

## Risks / Trade-offs

- [Running `preflight` can start services or take minutes] → that is what the intent's "preflight passes" means; the line shows after the command ends, and the other checks are cheap.
- [Activation by file content is a heuristic] → it is stated in the spec and tested against a hook script of each manager; a manager that renames its marker needs a spec change.
- [`ls-remote` needs the network] → an unreachable remote is a `fail` that names itself and its way out (`require_up_to_date = false`), as the hook's refusal does.
