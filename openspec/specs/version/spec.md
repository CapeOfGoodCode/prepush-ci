# version Specification

## Purpose
`prepush-ci --version`: the version of the installed package and, for a build that did not come from a package index, whether it is a git commit or another direct install; it never prints a path or a URL of the installation record and never fails on a record it cannot read.

## Requirements

### Requirement: The version line names the commit of a git install
`prepush-ci --version` SHALL print one line, `prepush-ci <version>` with the version of the installed package, and exit 0. When the installation record of the package (`direct_url.json` of its distribution) names a git commit, the line SHALL end with ` (git <commit>)`, the commit cut to its first 12 characters. When there is no record, the line SHALL have no suffix.

#### Scenario: An install from git
- **WHEN** the record holds `{"url": "https://github.com/CapeOfGoodCode/prepush-ci", "vcs_info": {"vcs": "git", "commit_id": "7a42451df0fd6a1b2c3d4e5f60718293a4b5c6d7"}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (git 7a42451df0fd)` and exits 0

#### Scenario: An install from an index
- **WHEN** the package has no record and `--version` runs
- **THEN** it prints `prepush-ci <version>` and exits 0

#### Scenario: A short commit is kept whole
- **WHEN** the record holds a git `commit_id` of 7 characters, `7a42451`, and `--version` runs
- **THEN** it prints `prepush-ci <version> (git 7a42451)`

### Requirement: Any other direct install is named, not described
When the record names a path, a file or an archive, or a repository system other than git (a name that is not a string counts as one), or a git URL without a commit (a commit that is not a non-empty string of hex digits counts as none), the line SHALL end with ` (direct install)`. The line SHALL NOT contain a path or a URL of the record.

#### Scenario: A directory install
- **WHEN** the record holds `{"url": "file:///home/someone/prepush-ci", "dir_info": {"editable": true}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)` and the output contains neither `file:` nor `someone`

#### Scenario: An archive install
- **WHEN** the record holds `{"url": "https://user:secret@example.invalid/p.whl", "archive_info": {}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)` and the output contains neither `secret` nor `example.invalid`

#### Scenario: Another repository system
- **WHEN** the record holds `{"url": "https://example.invalid/r", "vcs_info": {"vcs": "hg", "commit_id": "7a42451df0fd6a1b"}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)`

#### Scenario: A git record without a commit
- **WHEN** the record holds `{"url": "https://example.invalid/r", "vcs_info": {"vcs": "git"}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)`

#### Scenario: A repository system that is not a string
- **WHEN** the record holds `{"url": "https://example.invalid/r", "vcs_info": {"vcs": 1, "commit_id": "7a42451df0fd6a1b"}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)`, exits 0 and prints nothing on standard error

#### Scenario: A commit that is not a string
- **WHEN** the record holds `{"url": "https://example.invalid/r", "vcs_info": {"vcs": "git", "commit_id": 42}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)`, exits 0 and prints nothing on standard error

#### Scenario: A commit that is not hex
- **WHEN** the record holds `{"url": "https://example.invalid/r", "vcs_info": {"vcs": "git", "commit_id": "7a42451\nfake"}}` and `--version` runs
- **THEN** it prints `prepush-ci <version> (direct install)` on one line and the output does not contain `fake`

### Requirement: An unreadable record is no record
When the installation record cannot be read as JSON, or its value is not an object, or it names none of `vcs_info`, `dir_info` and `archive_info`, or a key it names holds something that is not an object, `--version` SHALL print the line without a suffix, exit 0, and print nothing on standard error.

#### Scenario: Invalid JSON
- **WHEN** the record holds `{not json` and `--version` runs
- **THEN** it prints `prepush-ci <version>`, exits 0 and prints nothing on standard error

#### Scenario: Not an object
- **WHEN** the record holds `[]` and `--version` runs
- **THEN** it prints `prepush-ci <version>`, exits 0 and prints nothing on standard error

#### Scenario: No known key
- **WHEN** the record holds `{"url": "https://example.invalid/p"}` and `--version` runs
- **THEN** it prints `prepush-ci <version>`, exits 0 and prints nothing on standard error

#### Scenario: A known key that is not an object
- **WHEN** the record holds `{"vcs_info": null}` and `--version` runs
- **THEN** it prints `prepush-ci <version>`, exits 0 and prints nothing on standard error

#### Scenario: A known key that is a string
- **WHEN** the record holds `{"dir_info": "editable"}` and `--version` runs
- **THEN** it prints `prepush-ci <version>`, exits 0 and prints nothing on standard error
