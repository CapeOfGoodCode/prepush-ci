## ADDED Requirements

### Requirement: One module decides every encoding
Every conversion between bytes and text, and between the tool's text and an operating system string (an argument, an environment value, a path), SHALL be made by `src/prepush_ci/text_io.py`, which every command uses. No other module outside `core/` SHALL call `read_text`, `write_text`, `open`, `decode`, `encode`, `fsdecode`, `fsencode`, `reconfigure` or `input`, pass `encoding`, `errors`, `text` or `universal_newlines`, or use `sys.stdin` or `subprocess`.

#### Scenario: No other module decides an encoding
- **WHEN** the modules of `src/prepush_ci/`, except `text_io.py` and `core/`, are parsed
- **THEN** none of them contains a call, keyword or name named above

#### Scenario: The scan finds a violation
- **WHEN** the same scan runs on a module text that calls `path.read_text(encoding="utf-8")`
- **THEN** it reports that call

#### Scenario: The scan finds an implicit crossing
- **WHEN** the same scan runs on a module text that reads `sys.stdin`, and on one that calls `subprocess.run(["git", text])`
- **THEN** it reports each of them

### Requirement: The tool's text is UTF-8, whatever the locale
Names and contents the tool holds as text (git's output, paths, ref and remote names, config values, arguments, environment values and standard input) SHALL be decoded as UTF-8 with `surrogateescape`, so that a byte that is not UTF-8 survives and is written back unchanged. The commands SHALL behave the same under a UTF-8 locale and under `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`, except that a hook run by pre-commit is held to this only as far as pre-commit itself runs under the locale.

#### Scenario: Bytes survive the round trip
- **WHEN** the bytes `or\xc3\xa9` and the bytes `x\xff` are decoded and encoded again
- **THEN** each gives back the bytes it started from

### Requirement: The locale decides only the operating system's strings
The conversion of the tool's text to and from an operating system string (an argument, an environment value, a path) SHALL be the only step that depends on the locale, and SHALL be exact for every byte sequence.

#### Scenario: Tool text survives the operating system's strings
- **WHEN** a process with a file system encoding of `ascii` converts the text `oré` to the operating system's string and back
- **THEN** it gets `oré`

### Requirement: Every command handles non-ASCII names the same way
`doctor`, `init`, `install`, `run` and the hooks SHALL work in a repository whose path, remotes, branches, hooks directory and templates have non-ASCII names, and with non-ASCII arguments and answers, under both locales above; the hooks that pre-commit runs only as far as pre-commit itself runs under the locale.

#### Scenario: A remote with a non-ASCII name matches the config
- **WHEN** the remote `oré` has the branch `main`, the config says `require_up_to_date = "oré/main"` and `doctor` runs
- **THEN** the `up-to-date` line starts with `ok`

#### Scenario: Run with a remote that has a non-ASCII name is not refused
- **WHEN** the config says `require_up_to_date = "oré/main"`, the remote `oré` has `main` and `run` checks the tip
- **THEN** `run` does not refuse for a missing remote

#### Scenario: Doctor and init work in a repository whose path is non-ASCII
- **WHEN** the repository lives in a directory named `dé` and `doctor --hooks none` and `init --non-interactive --check true --hooks none --ci none` run in it
- **THEN** neither prints a traceback and `init` writes `.prepush-ci.toml` and exits 0

#### Scenario: Install writes the hooks in a non-ASCII path and says so once
- **WHEN** the repository lives in a directory named `dé` and `install --hooks native` runs twice
- **THEN** the first run exits 0 and writes the hook scripts, and the second prints `already installed` and changes no file

#### Scenario: Init sees the previous hook in a non-ASCII hooks directory
- **WHEN** `core.hooksPath` is a directory named `pré` that holds a `pre-push` hook and interactive `init` asks which hooks to set up
- **THEN** the question names that hook as one that is kept and runs first

#### Scenario: A non-ASCII argument reaches the config
- **WHEN** `init --non-interactive --check "echo é" --hooks none --ci none` runs
- **THEN** it exits 0 and `.prepush-ci.toml` holds `check = "echo é"` as UTF-8

#### Scenario: A non-ASCII answer reaches the config
- **WHEN** interactive `init` reads the check `echo é` from standard input
- **THEN** it exits 0 and `.prepush-ci.toml` holds `check = "echo é"` as UTF-8

#### Scenario: A check with a non-ASCII character runs
- **WHEN** the config says `check = "echo é"` and `run` checks the tip
- **THEN** `run` exits 0 and ends in no traceback, and the check's own output is passed through: it prints `é` in `utf8`, whatever the terminal shows in `ascii`

#### Scenario: A preflight with a non-ASCII character runs
- **WHEN** the config says `preflight = "echo é"`, and `run` checks the tip and `doctor --hooks none` runs
- **THEN** `run` ends in no traceback and the `preflight` line of `doctor` starts with `ok`

#### Scenario: A branch with a non-ASCII name is pushed
- **WHEN** a commit on the branch `fé` is pushed with the pre-push hook installed
- **THEN** the hook reads the ref, runs the check once and the push succeeds

#### Scenario: A commit template in a non-ASCII path is read
- **WHEN** `commit.template` names a file in a directory called `dé`, an editor saves the template untouched, and the commit-msg hook runs
- **THEN** the hook writes no trailer, as it does for any untouched template

### Requirement: A file the tool parses must be UTF-8, and says so
A file the tool parses (`.prepush-ci.toml`, `pyproject.toml`, `.claude/settings.json`), whether on disk or committed in a revision, that is not valid UTF-8 SHALL be reported as a problem of that file in one line that names it and says `not valid UTF-8`, through the way the command reports a config or settings problem today (`config`, "invalid TOML"; `init`, "Malformed settings are refused"), and SHALL NOT end in a traceback.

#### Scenario: The commit-msg hook refuses a config that is not UTF-8
- **WHEN** `.prepush-ci.toml` holds the byte `\xe9` and a commit runs with `PREPUSH_CI=full`
- **THEN** the hook exits non-zero, prints one line that names `.prepush-ci.toml` and says `not valid UTF-8`, and no traceback

#### Scenario: Doctor reports a config that is not UTF-8
- **WHEN** `.prepush-ci.toml` holds the byte `\xe9` and `doctor --hooks none` runs
- **THEN** the `config` line starts with `fail` and names the file and `not valid UTF-8`, and the other five checks still print

#### Scenario: Verify reports a committed config that is not UTF-8
- **WHEN** the config committed in a commit that carries the trailer holds the byte `\xe9` and `verify` runs on it
- **THEN** it exits 1 and its line names the config file and `not valid UTF-8`

#### Scenario: Init refuses settings that are not UTF-8
- **WHEN** `.claude/settings.json` holds the byte `\xe9` and `init` runs
- **THEN** it exits 1 naming the file and `not valid UTF-8`, and writes no file

### Requirement: A file the tool edits keeps its bytes
A file the tool reads, changes in a block or a line, and writes back (a hook manager's file, a hook script, a commit message) SHALL keep every byte outside the change, including bytes that are not UTF-8, and SHALL NOT be refused for them.

#### Scenario: A message that is not UTF-8 gets its trailer
- **WHEN** a commit is made with `PREPUSH_CI=full` and a message holding the byte `\xe9`
- **THEN** the commit exists, the hook exits 0 and the message holds the trailer, and its other bytes are those of the message

#### Scenario: A manager's file keeps a byte that is not UTF-8
- **WHEN** `.pre-commit-config.yaml` holds a comment with the byte `\xe9` and `install --hooks pre-commit` runs
- **THEN** the file holds the prepush-ci block and every other byte of it is as it was

### Requirement: A file the tool writes reads back equal
A file the tool writes (hook scripts, config, the recorded paths of `install`, the pass records, the settings and the session script) SHALL be written as UTF-8 with `surrogateescape`, with the line ending the command uses today, so that the tool reads back the text it wrote.

#### Scenario: A hook script that embeds a non-ASCII path reads back equal
- **WHEN** `install --hooks native` writes hook scripts that name an interpreter or a hooks directory with the character `é`, and runs again
- **THEN** the second run reports no change

#### Scenario: A pass record in a non-ASCII repository is found again
- **WHEN** the remote rejects a push after the hook passed, in a repository whose path has the character `é`, and the same commit is pushed again
- **THEN** the check ran exactly once and the second push said it skipped the check

### Requirement: The terminal never makes a command fail
Standard output and standard error SHALL replace a character the terminal cannot encode and SHALL NOT raise. On standard output the replacement is `?`.

#### Scenario: A report that quotes a non-ASCII key prints
- **WHEN** the config holds the key `unknownÉ` and `doctor --hooks none` runs with an ASCII standard output
- **THEN** it prints its report, the `config` line quotes `unknown?`, and there is no traceback

#### Scenario: A refusal that quotes a non-ASCII key prints
- **WHEN** the config holds the key `unknownÉ`, standard error is ASCII and a commit runs with `PREPUSH_CI=full`
- **THEN** the hook exits non-zero and prints a line that names `.prepush-ci.toml` and holds `unknown`, and there is no traceback

### Requirement: The integration specs run in two variants
Every integration spec that uses a repository or starts the CLI SHALL run in a variant named `utf8`, the environment the specs run in today, and in one named `ascii`; the id of the test SHALL name the variant. A spec SHALL NOT opt out of a variant; one that cannot run in it fails. A spec starts the CLI by what it does, not how it is spelled: `python -m prepush_ci`, the installed `prepush-ci` script, or a script of the repository that runs either.

#### Scenario: Both variants run
- **WHEN** the integration specs are collected
- **THEN** every test that uses the `repo` fixture or starts the CLI has one item for `utf8` and one for `ascii`

#### Scenario: A spec that starts the CLI another way has both variants
- **WHEN** the integration specs are collected
- **THEN** the specs that run the installed `prepush-ci` script, and those that run a repository script that starts the CLI (the demo's recording), have one item for `utf8` and one for `ascii`

#### Scenario: A command that cannot run under the variant fails the suite
- **WHEN** a spec runs a command in the `ascii` variant and the command ends in a traceback
- **THEN** the spec fails, and is not skipped

### Requirement: The ascii variant is hostile
In `ascii` the repository SHALL live in a directory whose name has a non-ASCII character, and every process the spec starts SHALL get `LC_ALL=C`, `PYTHONUTF8=0` and `PYTHONCOERCECLOCALE=0`, on every platform, except the processes of pre-commit (next requirement).

#### Scenario: The ascii variant is hostile
- **WHEN** a spec runs in the `ascii` variant
- **THEN** the path of its repository has a non-ASCII character and the CLI it starts runs with the three variables above

### Requirement: Pre-commit keeps the outer locale in the ascii variant
In `ascii`, the processes of pre-commit (`pre-commit install`, and the commits and pushes whose hooks pre-commit runs) SHALL get the locale of the outer environment instead of the three variables above, because pre-commit 4.6 fails in a repository whose path is non-ASCII under `LC_ALL=C`. The repository path stays non-ASCII, every other process of the spec stays hostile, and no other process takes this exception.

#### Scenario: Pre-commit's processes keep the outer locale
- **WHEN** a spec in the `ascii` variant runs `pre-commit install`, a commit whose hook pre-commit runs, and a push whose pre-push hook pre-commit runs
- **THEN** none of these processes gets `LC_ALL=C`, `PYTHONUTF8=0` or `PYTHONCOERCECLOCALE=0` from the variant, and the repository path has a non-ASCII character

#### Scenario: Every other process stays hostile
- **WHEN** the same spec runs the CLI itself (`install --hooks pre-commit`, `doctor`) in the `ascii` variant
- **THEN** that process gets the three variables
