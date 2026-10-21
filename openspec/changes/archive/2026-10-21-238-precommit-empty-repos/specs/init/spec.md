## ADDED Requirements

### Requirement: A refused install can be retried
When `install` refused and `init` exited 1 after it wrote `.prepush-ci.toml`, running `init` again, with no flag whose value differs from that config, SHALL leave the config as it is, run `install` again and then do the steps after it as a first run with the same flags would, once what `install` refused has been fixed.

#### Scenario: Second run after a refusal
- **WHEN** `init --non-interactive --check scripts/ci` exited 1 because `.pre-commit-config.yaml` held `repos: [{repo: local}]`, the file was changed to a block list, and `init --non-interactive` runs
- **THEN** it exits 0, `.prepush-ci.toml` has the same contents and modification time as after the first run, the file holds the `prepush-ci` block, `.claude/hooks/session-start.sh` exists, and `.claude/settings.json` registers the script in `hooks.SessionStart`
