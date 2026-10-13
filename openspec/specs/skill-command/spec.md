# skill-command Specification

## Purpose
`prepush-ci skill [--write]`: the setup skill of the installed version, printed for any agent to follow or written as the project skill, and the wheel that carries the file it reads.

## Requirements

### Requirement: The skill command prints the installed skill
`prepush-ci skill` SHALL write the setup skill of the installed version to standard output, byte for byte, and nothing else, and exit 0. It SHALL need no repository and no network. The file SHALL be the one of the source checkout when `skills/prepush-ci-setup/SKILL.md` exists two directories above the package, and otherwise the file the wheel installed as package data.

#### Scenario: The output is the skill
- **WHEN** the test runs `prepush-ci skill` in an empty directory that is not a git repository
- **THEN** it exits 0 and standard output equals the bytes of `skills/prepush-ci-setup/SKILL.md` of the repository

#### Scenario: The command is listed
- **WHEN** the test runs `prepush-ci --help`
- **THEN** the output lists `skill`

#### Scenario: The installed file without a checkout
- **WHEN** the lookup finds no `skills/prepush-ci-setup/SKILL.md` above the package and the distribution lists a data file `SKILL.md`
- **THEN** the command prints that file

#### Scenario: Neither file exists
- **WHEN** the lookup finds neither the checkout file nor an installed data file
- **THEN** the command exits 1, standard output is empty and standard error says the skill is not part of this installation

### Requirement: The skill command can write the project skill
`prepush-ci skill --write` SHALL write the same bytes to `.claude/skills/prepush-ci-setup/SKILL.md` at the root of the working tree it runs in, creating the directories and replacing a file that is there, print `wrote .claude/skills/prepush-ci-setup/SKILL.md` and exit 0. It SHALL print nothing else to standard output, SHALL NOT touch any other file and SHALL NOT stage or commit anything. Outside a git repository it SHALL exit 1 with a message and write nothing.

#### Scenario: A new project skill
- **WHEN** the test runs `prepush-ci skill --write` in a new git repository
- **THEN** it exits 0, prints `wrote .claude/skills/prepush-ci-setup/SKILL.md`, the file equals the bytes of `skills/prepush-ci-setup/SKILL.md`, and `git status --porcelain` shows only `.claude/`

#### Scenario: An older copy is replaced
- **WHEN** the same happens in a repository whose `.claude/skills/prepush-ci-setup/SKILL.md` holds other text
- **THEN** the file afterwards equals the skill and the command exits 0

#### Scenario: From a subdirectory
- **WHEN** the test runs `prepush-ci skill --write` in a subdirectory of a repository
- **THEN** the file is written under the root of the working tree and the subdirectory has no `.claude/`

#### Scenario: A linked worktree
- **WHEN** the test runs `prepush-ci skill --write` in a linked worktree
- **THEN** the file is written under that worktree's root, not under the main worktree's

#### Scenario: Outside a repository
- **WHEN** the test runs `prepush-ci skill --write` in a directory that is not a git repository
- **THEN** it exits 1, standard error says it is not a git repository and no file is written

#### Scenario: A non-ASCII repository path
- **WHEN** the test runs `prepush-ci skill --write` with `LC_ALL=C` in a repository whose path contains `é`
- **THEN** it exits 0 and no traceback is printed, and the file is written under that path

### Requirement: The skill command reports a target it cannot write
When the target of `prepush-ci skill --write` cannot be written, the command SHALL exit 1 with one line on standard error that names the target path and the reason, print nothing to standard output and no traceback, and leave every other file as it was.

#### Scenario: A target that cannot be written
- **WHEN** the test runs `prepush-ci skill --write` in a repository whose `.claude` is a file, or whose `.claude/skills/prepush-ci-setup/SKILL.md` is a directory
- **THEN** it exits 1, standard error is one line that names the target path and the reason, standard output is empty, no traceback is printed and `git status --porcelain` is what it was before

### Requirement: The wheel carries the skill file of the repository
The wheel and the source distribution that `uv build` makes SHALL contain `skills/prepush-ci-setup/SKILL.md` itself, not a copy kept in the source tree, and `prepush-ci skill` of a wheel installed into a new virtual environment SHALL print the same bytes as that file.

#### Scenario: The installed command prints the skill
- **WHEN** the test runs `uv build`, installs the wheel into a new virtual environment and runs the `prepush-ci skill` of that environment outside the repository
- **THEN** it exits 0 and standard output equals the bytes of `skills/prepush-ci-setup/SKILL.md` of the repository

#### Scenario: The source distribution has it
- **WHEN** the test lists the files of the source distribution that the same build made
- **THEN** it contains `skills/prepush-ci-setup/SKILL.md`

#### Scenario: A written copy matches
- **WHEN** the test runs `prepush-ci skill --write` of that installed wheel in a new git repository
- **THEN** the written file equals the bytes of `skills/prepush-ci-setup/SKILL.md` of the repository
