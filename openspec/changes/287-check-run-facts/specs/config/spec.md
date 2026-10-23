## MODIFIED Requirements

### Requirement: Config keys and defaults
The config SHALL accept exactly these keys: `check` (string, required), `preflight` (string, default none), `require_env` (list of strings, default empty), `require_up_to_date` (see below), `default_branch` (string, default `main`), `trailer` (see below), `legacy_keys` (list of strings, default empty), `cache` (boolean, default `true`), `results` (see below, default none).

#### Scenario: Only the check is given
- **WHEN** the config contains only `check = "scripts/ci"`
- **THEN** the parsed config has no preflight, no required variables, `require_up_to_date` `origin/main`, `default_branch` `main`, trailer `Prepush-CI: full`, no legacy keys, `cache` true and no result files

#### Scenario: Every key is given
- **WHEN** the config sets `check = "make ci"`, `preflight = "make lint"`, `require_env = ["DATABASE_URL"]`, `require_up_to_date = "upstream/develop"`, `default_branch = "trunk"`, `trailer = { key = "Full-Check", value = "yes" }`, `legacy_keys = ["Full-Pre-Push"]`, `cache = false` and `results = { coverage = "out/cov.json" }`
- **THEN** the parsed config holds exactly those nine values

## ADDED Requirements

### Requirement: The result files are named in results
`results` SHALL be a table whose keys are all optional: `junit` (list of strings), `coverage`, `ruff` and `mypy` (each a string). An unknown key SHALL be named by its full path (e.g. `results.junt`), and a value of the wrong type or an empty string SHALL be reported with its key, together with any other problem; the tool SHALL exit non-zero.

#### Scenario: All four given
- **WHEN** the config sets `results = { junit = ["out/a.xml", "out/b.xml"], coverage = "out/cov.json", ruff = "out/ruff.json", mypy = "out/mypy.txt" }`
- **THEN** the parsed config holds those two JUnit paths and those three paths

#### Scenario: Only one given
- **WHEN** the config sets `results = { junit = ["out/a.xml"] }`
- **THEN** the parsed config has that JUnit path and no coverage, ruff or mypy path

#### Scenario: An unknown key
- **WHEN** the config sets `results = { junt = ["out/a.xml"] }`
- **THEN** the tool reports `results.junt` as unknown and exits non-zero

#### Scenario: A JUnit entry that is not a string
- **WHEN** the config sets `results = { junit = [1] }`
- **THEN** the tool reports `results.junit` and exits non-zero

#### Scenario: Not a table
- **WHEN** the config sets `results = "out/a.xml"`
- **THEN** the tool reports `results` and exits non-zero

#### Scenario: An empty path
- **WHEN** the config sets `results = { coverage = "" }`
- **THEN** the tool reports `results.coverage` and exits non-zero

### Requirement: A result path stays inside the worktree
Each path in `results` SHALL be relative to the top of the working tree, because the tool deletes it before the check and reads it after. A path with a `..` component, an absolute path and a path with a drive letter SHALL be refused. A path that breaks this or the next requirement SHALL be reported with its key and the entry, together with any other problem, and the tool SHALL exit non-zero.

#### Scenario: A path above the worktree
- **WHEN** the config sets `results = { coverage = "../cov.json" }`
- **THEN** the tool reports `results.coverage` and `../cov.json` and exits non-zero

#### Scenario: An absolute path
- **WHEN** the config sets `results = { mypy = "/tmp/mypy.txt" }`
- **THEN** the tool reports `results.mypy` and `/tmp/mypy.txt` and exits non-zero

#### Scenario: A path with a drive letter
- **WHEN** the config sets `results = { ruff = "C:\\out\\ruff.json" }`
- **THEN** the tool reports `results.ruff` and exits non-zero

#### Scenario: A path inside a directory is fine
- **WHEN** the config sets `results = { coverage = "build/out/cov.json" }`
- **THEN** the parsed config holds that path

### Requirement: A result path reads the same on every operating system
A path in `results` SHALL be written with `/` as its only separator, and SHALL be refused on every operating system when it contains a backslash, starts with `/`, or starts with a letter and `:` (a drive, also a drive-relative one).

#### Scenario: A drive-relative path
- **WHEN** the config sets `results = { ruff = "C:ruff.json" }`
- **THEN** the tool reports `results.ruff` and exits non-zero

#### Scenario: A backslash climbs
- **WHEN** the config sets `results = { coverage = "..\\cov.json" }`
- **THEN** the tool reports `results.coverage` and `..\\cov.json` and exits non-zero, on every operating system

#### Scenario: A leading backslash
- **WHEN** the config sets `results = { coverage = "\\out\\cov.json" }`
- **THEN** the tool reports `results.coverage` and exits non-zero, on every operating system

#### Scenario: A network path
- **WHEN** the config sets `results = { junit = ["\\\\server\\share\\a.xml"] }`
- **THEN** the tool reports `results.junit` and exits non-zero
