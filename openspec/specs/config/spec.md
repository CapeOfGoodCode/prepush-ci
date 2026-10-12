# config Specification

## Purpose
The single source of truth for prepush-ci: where its config is found, which keys it has with which defaults, and how an invalid or missing config is reported.

## Requirements

### Requirement: Config location
The tool SHALL read its config from `.prepush-ci.toml` at the root of the repository's working tree. When that file does not exist, it SHALL read the table `[tool.prepush-ci]` of `pyproject.toml` at the same root. When both exist, `.prepush-ci.toml` SHALL be used and `pyproject.toml` SHALL be ignored.

#### Scenario: Config file at the repository root
- **WHEN** the repository root contains `.prepush-ci.toml` with `check = "scripts/ci"`
- **THEN** the tool uses `scripts/ci` as the check

#### Scenario: Config in pyproject.toml
- **WHEN** the repository root has no `.prepush-ci.toml` and its `pyproject.toml` contains `[tool.prepush-ci]` with `check = "make ci"`
- **THEN** the tool uses `make ci` as the check

#### Scenario: Dedicated file wins over pyproject.toml
- **WHEN** `.prepush-ci.toml` sets `check = "scripts/ci"` and `pyproject.toml` sets `[tool.prepush-ci]` `check = "make ci"`
- **THEN** the tool uses `scripts/ci` as the check

#### Scenario: Run from a subdirectory
- **WHEN** the tool runs in a subdirectory of the working tree and `.prepush-ci.toml` is at the root
- **THEN** the tool reads the config at the root

### Requirement: Missing config fails
When a command needs the config and neither `.prepush-ci.toml` nor a `[tool.prepush-ci]` table in `pyproject.toml` exists, the tool SHALL print an error naming both places and exit non-zero; it SHALL NOT assume a check command.

#### Scenario: No config anywhere
- **WHEN** the repository has neither `.prepush-ci.toml` nor `pyproject.toml`
- **THEN** the tool prints an error naming `.prepush-ci.toml` and `[tool.prepush-ci]` and exits non-zero

#### Scenario: pyproject.toml without the table
- **WHEN** the repository has no `.prepush-ci.toml` and its `pyproject.toml` has no `[tool.prepush-ci]` table
- **THEN** the tool prints the same error and exits non-zero

### Requirement: Config keys and defaults
The config SHALL accept exactly these keys: `check` (string, required), `preflight` (string, default none), `require_env` (list of strings, default empty), `require_up_to_date` (see below), `default_branch` (string, default `main`), `trailer` (see below), `legacy_keys` (list of strings, default empty), `cache` (boolean, default `true`).

#### Scenario: Only the check is given
- **WHEN** the config contains only `check = "scripts/ci"`
- **THEN** the parsed config has no preflight, no required variables, `require_up_to_date` `origin/main`, `default_branch` `main`, trailer `Prepush-CI: full`, no legacy keys and `cache` true

#### Scenario: Every key is given
- **WHEN** the config sets `check = "make ci"`, `preflight = "make lint"`, `require_env = ["DATABASE_URL"]`, `require_up_to_date = "upstream/develop"`, `default_branch = "trunk"`, `trailer = { key = "Full-Check", value = "yes" }`, `legacy_keys = ["Full-Pre-Push"]` and `cache = false`
- **THEN** the parsed config holds exactly those eight values

### Requirement: Up-to-date ref
`require_up_to_date` SHALL accept a string ref or a boolean. When it is absent or `true`, it SHALL be `origin/<default_branch>`; when it is `false`, the config SHALL have no up-to-date ref.

#### Scenario: Up-to-date ref follows the default branch
- **WHEN** the config sets `default_branch = "trunk"` and does not set `require_up_to_date`
- **THEN** `require_up_to_date` is `origin/trunk`

#### Scenario: Up-to-date set to true
- **WHEN** the config sets `default_branch = "trunk"` and `require_up_to_date = true`
- **THEN** `require_up_to_date` is `origin/trunk`

#### Scenario: Up-to-date check disabled
- **WHEN** the config sets `require_up_to_date = false`
- **THEN** the parsed config has no up-to-date ref

### Requirement: Trailer table
`trailer` SHALL be a table with a string `key`, default `Prepush-CI`, and a string `value`, default `full`; a sub-key that is absent SHALL take its own default.

#### Scenario: Trailer table with only a key
- **WHEN** the config sets `trailer = { key = "Full-Check" }`
- **THEN** the parsed trailer is `Full-Check: full`

### Requirement: Invalid config fails with the key named
The tool SHALL reject a config with a missing `check`, an unknown key, a value of the wrong type, or an empty string where a command, branch or ref is expected. An unknown key SHALL be named by its full path, at the top level or inside `trailer` (e.g. `trailer.valeu`). The tool SHALL report every problem found, each naming its key, and exit non-zero.

#### Scenario: Missing check
- **WHEN** the config sets `cache = false` but no `check`
- **THEN** the tool reports that `check` is required and exits non-zero

#### Scenario: Unknown key
- **WHEN** the config contains `chekc = "scripts/ci"`
- **THEN** the tool reports the unknown key `chekc` and exits non-zero

#### Scenario: Unknown key in the trailer table
- **WHEN** the config sets `trailer = { key = "X", valeu = "y" }`
- **THEN** the tool reports the unknown key `trailer.valeu` and exits non-zero

#### Scenario: Wrong type
- **WHEN** the config sets `cache = "yes"`
- **THEN** the tool reports that `cache` must be a boolean and exits non-zero

#### Scenario: Several problems at once
- **WHEN** the config contains an unknown key `foo` and sets `default_branch = 3`
- **THEN** the tool reports both `foo` and `default_branch` and exits non-zero

### Requirement: Trailer keys and value are valid
The tool SHALL reject a `trailer.key` or a legacy key that is not a trailer token (one or more letters, digits and hyphens), and a `trailer.value` that is empty, spans more than one line, or has leading or trailing whitespace, naming the key and exiting non-zero.

#### Scenario: Invalid trailer key
- **WHEN** the config sets `trailer = { key = "Prepush CI", value = "full" }`
- **THEN** the tool reports that `trailer.key` is not a valid trailer key and exits non-zero

#### Scenario: Empty trailer key
- **WHEN** the config sets `trailer = { key = "", value = "full" }`
- **THEN** the tool reports that `trailer.key` is not a valid trailer key and exits non-zero

#### Scenario: Empty trailer value
- **WHEN** the config sets `trailer = { key = "Prepush-CI", value = "" }`
- **THEN** the tool reports `trailer.value` and exits non-zero

#### Scenario: Multi-line trailer value
- **WHEN** the config sets `trailer = { value = "full\nSigned-off-by: x" }`
- **THEN** the tool reports `trailer.value` and exits non-zero

#### Scenario: Trailer value with surrounding whitespace
- **WHEN** the config sets `trailer = { value = "  full  " }`
- **THEN** the tool reports `trailer.value` and exits non-zero

### Requirement: Malformed config file fails
When the config source in use (`.prepush-ci.toml`, or `pyproject.toml` when it is the source) is not valid TOML, the tool SHALL report that file's name and the parse error and exit non-zero. A `pyproject.toml` that is ignored because `.prepush-ci.toml` exists SHALL NOT be parsed.

#### Scenario: Malformed TOML
- **WHEN** `.prepush-ci.toml` is not valid TOML
- **THEN** the tool reports `.prepush-ci.toml` and the parse error and exits non-zero

#### Scenario: Malformed pyproject.toml as the source
- **WHEN** the repository has no `.prepush-ci.toml` and its `pyproject.toml` is not valid TOML
- **THEN** the tool reports `pyproject.toml` and the parse error and exits non-zero

#### Scenario: Malformed pyproject.toml is ignored
- **WHEN** `.prepush-ci.toml` is valid with `check = "scripts/ci"` and `pyproject.toml` is not valid TOML
- **THEN** the tool uses `scripts/ci` as the check
