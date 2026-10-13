Issue: #78

## Why

A config with `require_env = [""]` loads without a complaint, and then every push of a trailer commit is refused with "unset or empty: " and no name to set, so the user cannot fix it by setting a variable. `init --require-env ""` writes exactly this config, so the tool can create the trap itself.

## What Changes

- The config rejects a `require_env` entry that cannot be the name of an environment variable: one that is not a portable name: it must start with a letter or `_` and hold only letters, digits and `_`.
- The rejection names `require_env` and the entry, like every other invalid value, and is reported together with any other problem.
- `init` needs no change: its existing requirement already ends in exit 1 and no file when the config rejects a value.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config`: adds the requirement "Required variable names are valid".

## Impact

- One more check in config loading; no new files, no runtime dependencies.
- A config that has such an entry today stops loading. For an empty entry or one with `=`, no variable can have that name, so every trailer push it governed was already refused. For a name that is not a shell identifier (`MY-VAR`, `DATABASE URL`) it depends on `sh`: where `sh` is dash (Debian, Ubuntu) the hook never sees the variable and the push was already refused; where `sh` is bash (macOS, Git for Windows, Fedora) the variable arrives and the config works today. On those systems this change breaks such a config, and the user has to rename the variable. The portable form is chosen on purpose: the same config must give the same answer everywhere.
