## ADDED Requirements

### Requirement: Required variable names are valid
The tool SHALL reject a `require_env` entry that does not match `[A-Za-z_][A-Za-z0-9_]*`, because the pre-push hook runs under `sh`, which may drop a variable with any other name before the tool starts. The report SHALL name `require_env` and the entry, together with any other problem, and the tool SHALL exit non-zero.

#### Scenario: Empty name
- **WHEN** the config sets `check = "true"` and `require_env = [""]`
- **THEN** the tool reports `require_env` and the empty entry and exits non-zero

#### Scenario: Name with whitespace
- **WHEN** the config sets `require_env = ["DATABASE URL"]`
- **THEN** the tool reports `require_env` and `DATABASE URL` and exits non-zero

#### Scenario: Name with a hyphen or a dot
- **WHEN** the config sets `require_env = ["MY-VAR", "A.B"]`
- **THEN** the tool reports `require_env`, `MY-VAR` and `A.B` and exits non-zero

#### Scenario: Name starting with a digit
- **WHEN** the config sets `require_env = ["1A"]`
- **THEN** the tool reports `require_env` and `1A` and exits non-zero

#### Scenario: Name with an equals sign
- **WHEN** the config sets `require_env = ["DATABASE_URL=x"]`
- **THEN** the tool reports `require_env` and `DATABASE_URL=x` and exits non-zero

#### Scenario: One bad name among good ones
- **WHEN** the config sets `require_env = ["DATABASE_URL", "", "_TOKEN1"]` and an unknown key `foo`
- **THEN** the tool reports the empty entry of `require_env` and the unknown key `foo` and exits non-zero

#### Scenario: Valid names load
- **WHEN** the config sets `require_env = ["DATABASE_URL", "_TOKEN1", "a"]`
- **THEN** the parsed config holds exactly those three names

#### Scenario: init writes no config with an empty name
- **WHEN** `init --non-interactive --check true --require-env ""` runs in a repository without a config
- **THEN** it exits 1 with the config's message naming `require_env` and writes no file

#### Scenario: init writes no config with a name the hook would drop
- **WHEN** `init --non-interactive --check true --require-env "DATABASE URL"` runs in a repository without a config
- **THEN** it exits 1 with the config's message naming `require_env` and `DATABASE URL` and writes no file
