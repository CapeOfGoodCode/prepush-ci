## REMOVED Requirements

### Requirement: A file the tool writes reads back equal
**Reason**: It lists "the pass records" among the files the tool writes, and its second scenario names a pass record. After this change the tool writes no such file: git writes the result ref and its commit. A MODIFIED block cannot drop or rename a scenario, so the requirement is replaced under a new name.
**Migration**: `A written file reads back equal` has the same text without the pass records; its scenarios keep their steps, and the second one says "result".

## ADDED Requirements

### Requirement: A written file reads back equal
A file the tool writes (hook scripts, config, the recorded paths of `install`, the settings and the session script) SHALL be written as UTF-8 with `surrogateescape`, with the line ending the command uses today, so that the tool reads back the text it wrote. A result ref is written by git and is not such a file.

#### Scenario: A hook script that embeds a non-ASCII path reads back equal
- **WHEN** `install --hooks native` writes hook scripts that name an interpreter or a hooks directory with the character `é`, and runs again
- **THEN** the second run reports no change

#### Scenario: A result in a non-ASCII repository is found again
- **WHEN** the remote rejects a push after the hook passed, in a repository whose path has the character `é`, and the same commit is pushed again
- **THEN** the check ran exactly once and the second push said it skipped the check
