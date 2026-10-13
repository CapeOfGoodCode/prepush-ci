# Design

## Context

#9 installs native hooks through `core.hooksPath`; #10 added pre-commit, husky and lefthook, whose install "leaves git alone". A repository that holds both states has the manager's files and a `core.hooksPath` that is ours. See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** a user who reruns `install` in that state learns at once what blocks the manager and how to remove it.

**Non-Goals:** removing the native hooks directory, migrating the hooks that the native install chained to (the refusal only names them), the wording in README and skill (#15), a `doctor` check for this state.

## Decisions

- **Refuse; do not unset `core.hooksPath` for the user.** "A manager leaves git alone" stays true, and the user sees the one command and decides. Refusing is cheap because nothing was written.
- **The refusal says what the unset drops.** The native install may have chained a previous hooks directory (the file `previous`), and once the local value is gone git no longer looks there. The message names that directory when it holds a hook and git will not use it anyway, so the user does not lose hooks without a word. When git uses it anyway (the default `.git/hooks`), nothing is lost and the message stays quiet. The user can move the hooks into the manager's own configuration; migrating them for the user is a non-goal.
- **The refusal covers pre-commit and lefthook only.** Run on the tools, with git 2.39.5: `pre-commit 4.7.0 install` answers `Cowardly refusing to install hooks with core.hooksPath set` and exits 1; `lefthook 2.2.1 install` prints a refusal that offers `--force` and exits 1; `npx husky` (the step husky's entries need) exits 0 and sets `core.hooksPath` to `.husky/_` over the old value. After `git config --local --unset core.hooksPath`, both `pre-commit install` and `lefthook install` succeed and write into `.git/hooks`.
- **"Ours" is the local `core.hooksPath`, made absolute, equal to the native hooks directory.** `install` only ever sets the local value, and the command the message names removes only the local value, so a refusal on a value from another scope would repeat after the user followed it. A value in another scope or pointing elsewhere is not ours and is left to the manager's own message.
- **The check comes before any file is read or written,** like the other refusals, so a refused run leaves the repository as it was.

## Risks / Trade-offs

- [A user who removes `core.hooksPath` and never activates the manager has no hooks at all] → `install` prints the activation step on its next run, and `doctor` (#14) reports the missing hooks.
- [The native hooks directory stays on disk after the unset] → harmless; git no longer looks at it.
