# Tasks

## 1. The config and the non-interactive run

- [x] 1.1 Add `prepush-ci init --non-interactive` with its flags: write `.prepush-ci.toml` from the flags (pure text and validation in `core/`), keep an existing config and refuse a config that does not load and flags that disagree with it, require `--check` while there is no config; verify with specs for every flag, the quoted check, `--require-up-to-date false`, the config in `pyproject.toml`, and the two refusals
- [ ] 1.2 Run `install` from `init` (`--hooks` including `none`), print its output, stop on its refusal; verify with specs for a detected manager, an existing pre-push hook that still refuses a push, `none`, and several managers
- [ ] 1.3 Place files at the root of the working tree wherever `init` runs, refuse outside a git repository and report `written`, `updated` or `kept` per step and the closing `set up` or `already set up`; verify with specs that run `init` twice, including with a manager file

## 2. Claude Code

- [ ] 2.1 Write `.claude/hooks/session-start.sh` (executable, never overwritten, `uv tool install` and the tool's directory on `PATH`, no manager activation, `--hooks <name>` when one was given or chosen, `--no-session-hook`); verify with specs that run the script with a stub `uv` on `PATH` and a hook manager's file sourced from `CLAUDE_ENV_FILE`, and with `CLAUDE_CODE_REMOTE` set, unset, and `CLAUDE_ENV_FILE` set, unset and already holding the export
- [ ] 2.2 Register the script in `.claude/settings.json` by merging JSON, once, refusing malformed JSON or an unexpected shape before any file is written; verify with specs for a new file, existing settings, a second run and malformed JSON

## 3. The CI gate

- [ ] 3.1 Carry the three files of `docs/ci/` inside the package, pick the snippet by detection or `--ci`, print it; verify with specs for each system, `--ci` and `none`, and a unit spec that the packaged copies equal `docs/ci/`
- [ ] 3.2 Add `--ci-gate-file`: write the snippet, keep an identical file, refuse another one before any write; verify with specs

## 4. Interactive

- [ ] 4.1 Ask for each config value with a detected default (`scripts/ci`, `bin/ci`, `make ci`; `origin/HEAD`), skip the questions a flag or an existing config answers, write only the answers that differ from the built-in defaults, ask the SessionStart question; verify with specs that feed answers on standard input
- [ ] 4.2 Ask the hooks question always, naming the manager file and the existing pre-push hook; refuse unknown answers and end of input before any write; verify with specs
- [ ] 4.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 12-init`) before the pull request is marked ready.
