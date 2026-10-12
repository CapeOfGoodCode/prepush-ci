# Design

## Context

`init` is the one-command setup of the intent (#1, section 4.3). It only composes what exists: the config file (#4), `install` (#9, #10) and the CI examples (#11). See `proposal.md` for the why and the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** a fresh repository reaches a working setup with one command; nothing the user already has is overwritten; asking is explicit where the maintainer asked for it (pre-push locally).

**Non-Goals:** writing the services and dependency installation of the SessionStart hook (the skill does that, #15), editing a CI definition in place, diagnosing a setup (`doctor`, #14), changing `install`.

## Decisions

- **An existing config is kept, never rewritten, and must load.** The tool cannot know which lines of a hand-written TOML file are the user's. Flags that disagree with it make `init` exit 1 naming the keys, before any file is written; flags that agree, or none, are fine. This is also what makes a second run idempotent.
- **`--check` is required only while no config exists.** The check is the one value with no safe default (the config spec forbids assuming one). Interactive, it has a detected default: `scripts/ci`, `bin/ci` or `make ci` (a `Makefile` with a `ci:` target), the first that exists.
- **Written config holds only what was given.** Defaults stay out of the file so a later change of the tool's default is not frozen into the repository. Interactively, an answer counts as given only when it differs from the built-in default (`check` always counts); a flag counts as given whatever its value.
- **`--require-up-to-date` takes a ref, `true` or `false`,** mapped to the config's string or boolean. `--require-env` is repeatable, one variable per use.
- **`--hooks` adds `none` to install's four values.** The maintainer asked that the user decides what happens with pre-push locally; "nothing" is one of the answers. `install` itself does not learn `none`.
- **The hooks question is always asked interactively,** also when nothing was found, and names what was found: the hook manager's file and the existing pre-push hook (looked up in the directory `install` calls the previous one). Existing hooks need no answer to be kept, because `install` chains them; the question lets the user pick a manager over native hooks, or none.
- **Invalid interactive answers refuse, they do not loop.** All questions are asked before the first file is written, an answer the config or `--hooks` rejects exits 1 naming the valid values, and end of input exits 1 with a hint at `--non-interactive`. Nothing is half done and the code has no retry state.
- **The order is config, hooks, SessionStart hook, CI gate; a failing step stops the rest.** Usage errors, a config that does not load or disagrees with the flags, a malformed `.claude/settings.json` and a CI gate file that cannot be written are all found before the first file is written. What only `install` can refuse (several hook managers, an unsupported `repos:`) stops `init` after the config; rerunning is idempotent, so the config written is no harm.
- **Paths: the working tree root, except `--ci-gate-file`.** `.prepush-ci.toml` and `.claude/` go where the config is read from, wherever `init` runs inside the tree; a path the user types is read like any shell argument, relative to where they are.
- **The CI snippet is chosen by detection with one winner:** `.github/workflows/` holds a `.yml` or `.yaml` file → GitHub Actions; else `.gitlab-ci.yml` → GitLab CI; else the generic shell gate. `--ci` overrides, `none` prints nothing. Printing the whole example, header comment included, keeps one source of truth with `docs/ci/`; editing a CI file in place is too risky to automate. `--ci-gate-file` writes it to a path the user names and never overwrites different content.
- **The SessionStart script is a skeleton, not the whole setup.** It returns at once unless `CLAUDE_CODE_REMOTE=true`; otherwise it runs `uv tool install prepush-ci`, puts the tool's bin directory on its own `PATH` and, through `$CLAUDE_ENV_FILE`, on the session's, runs `prepush-ci install` (with `--hooks <name>` when a hooks value other than `none` was given or chosen, so the cloud session installs the same kind) and appends `export PREPUSH_CI=full`, each line once. It exits 0 when `CLAUDE_ENV_FILE` is missing, with a warning: a SessionStart hook that fails must not break a session. The skill extends it with services and dependencies.
- **A persistent `uv tool install`, not `uvx`.** The files of a hook manager start `prepush-ci` from `PATH` (the `install` spec), which `uvx` never provides; native hooks would also record an interpreter in uv's cache (#58). A tool install gives both a command on `PATH` and a stable interpreter.
- **The skeleton does not activate a hook manager.** `pre-commit install`, `lefthook install` and husky's `prepare` need the manager itself, which comes with the repository's dependencies; the skill (#15) installs those and runs the step `install` prints. The skeleton installs our part only.
- **The tool is not pinned.** The skeleton installs the latest release. A pin written now would go stale on the first release and silently freeze cloud sessions; before 1.0 a minor release may break the CLI, so a team that wants a pin edits the one `uv tool install` line, which is theirs.
- **`--hooks none` does not stop the SessionStart script,** only `--no-session-hook` does. `none` is a choice about the developer's machine; the cloud container is another place that still needs the trailer enforced.
- **Settings are merged as JSON.** Every other key and every other hook stay; the file may be reformatted (two-space indent). The entry is added only if no `SessionStart` command already mentions `session-start.sh`.
- **A step reports `written`, `updated` or `kept`; the run ends with `set up` or `already set up`.** The last line is `already set up` exactly when no file changed, including those `install` writes.

## Risks / Trade-offs

- [A cloud container without `uv`, or with a network policy that blocks the package index, cannot run the skeleton] → the skill (#15) checks both in its preconditions; the skeleton fails loudly rather than skip the install.
- [A repository whose CI definition is neither GitHub nor GitLab gets the generic gate] → it is a shell script that any CI can call; the skill (#15) adapts it.
- [Reformatting `.claude/settings.json` makes a diff noisier than necessary] → accepted; a JSON-preserving editor would be code for a rare case.
- [The packaged snippets can drift from `docs/ci/`] → a test compares them.
