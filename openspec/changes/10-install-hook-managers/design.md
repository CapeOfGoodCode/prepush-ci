# Design

## Context

`install` (#9) wires git itself. Teams that use pre-commit, husky or lefthook have their hooks declared in committed files of those tools; `prepush-ci hook pre-push` already reads pre-commit's variables (#5). See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** one command makes a manager-based repository run the trailer and the check, without dropping what the manager already runs; running it again is harmless; the committed files stay reviewable.

**Non-Goals:** installing or activating the managers, configuring them from scratch, a global install, diagnosing a broken setup (#14), the interactive choice (#12).

## Decisions

- **Write the files; do not just print a snippet.** A printed snippet is lost the next time and cannot be idempotent or checked. Writing makes `make setup` one line and lets `doctor` (#14) compare. The price is editing YAML without a parser, handled by the next two decisions.
- **One managed block, markers `# prepush-ci: begin` and `# prepush-ci: end`; everything else is left alone.** No runtime dependency and no YAML round trip that would drop comments or reflow the file. The block is found by its markers, so a rerun replaces it in place, and a hand edit inside it is restored (`updated`). The marker is a comment in YAML and in shell.
- **Refuse a shape that cannot be edited safely, with the reason, and change nothing.** The edits assume the common shape: `repos:` as a block list, a block list or a one-line flow list for `default_install_hook_types`, a `commands:` mapping in block style under the lefthook hook. A flow `repos: []`, a `jobs:`-only lefthook hook and the like exit 1 naming the key to fix. Guessing could produce a config the manager rejects, or silently drop a hook.
- **`default_install_hook_types` is the one edit outside the block.** It is a top-level key and a duplicate would be invalid YAML. Absent: it is added as `[pre-commit, commit-msg, pre-push]` (`pre-commit` stays because absent means `[pre-commit]` for pre-commit). Present: only the missing `commit-msg` and `pre-push` are appended, existing items stay.
- **Detection: none → native, one → that manager, several → refuse.** With none, `install` behaves as in #9; with several, picking one would leave the other manager's hooks unchecked or doubled, so the user chooses with `--hooks`. `--hooks native` forces #9's behavior in a repository that has a manager.
- **An explicit manager whose files are missing is refused.** Creating a `.pre-commit-config.yaml` or a `.husky` directory from nothing means taking over setup of a tool that is not installed here. A husky hook file that is missing, inside an existing `.husky`, is created (executable, `#!/usr/bin/env sh`).
- **The entries call `prepush-ci` from `PATH`, never an absolute interpreter.** These files are committed and shared; a path of one machine would be wrong on every other. This differs from the native hooks, which stay in `.git`. The skill and `init` (#12, #15) recommend `uv tool install prepush-ci`; `doctor` (#14) can check that the command resolves. Tests put a shim named `prepush-ci` first on `PATH` that starts `sys.executable -m prepush_ci`, as the other specs do, so coverage measures it.
- **`install` does not run the manager.** `pre-commit install`, `lefthook install` and husky's `prepare` are the team's own step (`pre-commit install` also refuses while `core.hooksPath` is set), and running a third-party tool from here would add failure modes. The report prints the command for pre-commit and lefthook; husky is activated by its `prepare` script.
- **Manager choice does not touch git config or `.git/hooks`.** If native hooks were installed earlier, they stay; with both active, the check runs twice at most, and the result cache (#8) skips the second run. `doctor` (#14) can flag the overlap.
- **The husky block goes first, and hands standard input on.** An earlier line can end the hook (`exit 0`, `exec`) or read git's ref lines (`git lfs pre-push "$@"` does), and then a block placed last never runs the check: a trailer commit would reach the remote unchecked, which breaks the invariant. So the block comes first (after a `#!` line), reads standard input once, runs `prepush-ci hook pre-push "$@"` on it, ends the hook with its status when it fails, and re-supplies the same input to the lines after it. The cost: the check runs before cheaper existing checks, unlike the native hooks of #9. The same placement for `commit-msg` keeps one rule.
- **pre-commit hooks without `stages:` stay at the pre-commit stage.** Adding `commit-msg` and `pre-push` to `default_install_hook_types` would make every such hook run at those stages too (on the message file, and again on push). When the types change and `default_stages` is absent, `install` adds `default_stages` set to the types the file had before (`[pre-commit]` when the key was absent), so no hook loses a stage it ran at; a team that chose its own `default_stages`, or already installed those types, is not touched. This is the second key edited outside the block.
- **Standard input elsewhere.** lefthook hands standard input to every `use_stdin` command, so `use_stdin: true` is enough there. pre-commit hands over its `PRE_COMMIT_*` variables, which #5 reads, with the limits that spec states.
- **The native requirements stay native.** The requirements about the hooks directory, the interpreter file and `core.hooksPath` are scoped to native hooks in the spec; the manager files start `prepush-ci` from `PATH` and say so in a restated "found without PATH" requirement.

## Risks / Trade-offs

- [A husky 8 hook sources `husky.sh` on its second line, which runs the file again, so the block runs twice per hook] → harmless: `commit-msg` does not duplicate the trailer and the result cache (#8) skips the second check.
- [The husky pre-push block runs the full check before cheaper lines of the same hook] → accepted for correctness; the result cache (#8) means a retried push does not pay twice.
- [`prepush-ci` is not on `PATH` where a teammate commits] → pre-commit and husky then fail loudly ("command not found"), which is safe for the push (it fails closed) and fixed by installing the tool.
- [A line-based edit meets YAML it misreads (anchors, multi-document files)] → refused shapes are listed in the spec; for the rest the file is only changed inside the block and the one key, and a manager that rejects the result says so on the next run.
- [A manager's own `pre-commit install` run before this change put hooks in `.git/hooks`] → untouched; the manager owns them.
