# commit-msg-hook Specification

## Purpose
The `commit-msg` hook that turns the opt-in variable `PREPUSH_CI=full` into the trailer on the commit, the demand that the pre-push hook must run the full check on it.

## Requirements

### Requirement: Trailer written in full mode
With `PREPUSH_CI=full`, `prepush-ci hook commit-msg <file>` SHALL add the configured trailer (default `Prepush-CI: full`) to the message in `<file>` in place, using `git interpret-trailers --in-place --no-divider --where start --if-exists doNothing`, and exit 0.

#### Scenario: Commit in full mode
- **WHEN** the hook is installed as the repository's `commit-msg` hook and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full`

#### Scenario: Configured trailer
- **WHEN** the config sets `trailer = { key = "Full-Check", value = "yes" }` and a commit runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with `Full-Check: yes`

#### Scenario: Existing trailers are kept
- **WHEN** a commit message already ends with `Co-Authored-By: A <a@example.com>` and the commit runs with `PREPUSH_CI=full`
- **THEN** the message's trailer block contains `Prepush-CI: full` and `Co-Authored-By: A <a@example.com>`

### Requirement: A divider line in the body does not move the trailer
The hook SHALL treat a `---` line in the message body as ordinary text, so the trailer lands in the trailer block at the end of the message.

#### Scenario: Body with a divider line
- **WHEN** a commit with the message `subject`, a blank line, `body`, `---`, `more` runs with `PREPUSH_CI=full`
- **THEN** the message keeps `body`, `---`, `more` in order and ends with `Prepush-CI: full` after `more`

### Requirement: The trailer is written at most once
When the message already has a trailer with the configured key, the hook SHALL leave the message unchanged.

#### Scenario: Amend keeps one trailer
- **WHEN** a commit made with `PREPUSH_CI=full` is amended with `git commit --amend --no-edit` under `PREPUSH_CI=full`
- **THEN** the message contains `Prepush-CI: full` exactly once

#### Scenario: Running the hook twice
- **WHEN** `prepush-ci hook commit-msg <file>` runs twice on the same file with `PREPUSH_CI=full`
- **THEN** the file after the second run equals the file after the first run

### Requirement: An empty message stays empty
The hook SHALL leave a message unchanged when git is going to discard it as empty, judged after the cleanup git applies to this commit, or to abort it because an editor left the message unchanged from `commit.template`, so that git still aborts the commit. Sign-off lines (`git commit -s`) do not count as message text or as an edit of the template. A message git keeps as text SHALL get the trailer, even if it starts with the comment character.

#### Scenario: Empty message aborts the commit
- **WHEN** `git commit` runs with an empty message (e.g. `-F` of an empty file) and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Empty editor message aborts the commit
- **WHEN** `git commit` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Verbose diff does not count as a message
- **WHEN** `git commit -v` opens an editor that leaves the message empty and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Message that starts with the comment character
- **WHEN** `git commit -m "#123 fix the bug"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message is `#123 fix the bug` followed by the trailer `Prepush-CI: full`

#### Scenario: Message from a file that starts with the comment character
- **WHEN** `git commit -F <file>` runs with `PREPUSH_CI=full` and the file holds `#123 fix the bug`
- **THEN** the commit's message is `#123 fix the bug` followed by the trailer `Prepush-CI: full`

#### Scenario: Editor strips a comment-only message
- **WHEN** `git commit -m "#123 fix the bug" --edit` runs with an editor that changes nothing and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Editor with the no-op command
- **WHEN** `git commit` runs with `GIT_EDITOR=:` and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Another comment character
- **WHEN** `core.commentChar` is `;`, `git commit` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created

#### Scenario: Comment string of a newer git
- **WHEN** `core.commentString` is `//`, `git commit` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git aborts the commit and no commit is created, whether or not the installed git knows `core.commentString`

#### Scenario: Cleanup mode from the configuration
- **WHEN** `commit.cleanup` is `whitespace` and an editor writes the message `#123 fix the bug` and `PREPUSH_CI=full`
- **THEN** the commit's message is `#123 fix the bug`, a blank line, the trailer `Prepush-CI: full`, a blank line, and then the comment lines git prepared, which `whitespace` keeps

#### Scenario: Unchanged commit template aborts the commit
- **WHEN** `commit.template` holds `Subject here`, a blank line and `# describe why`, `git commit` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git aborts the commit with "you did not edit the message" and no commit is created

#### Scenario: Signed-off empty message aborts the commit
- **WHEN** `git commit -s` opens an editor that leaves the message empty and `PREPUSH_CI=full`
- **THEN** git aborts the commit with "empty commit message" and no commit is created

#### Scenario: Signed-off unchanged template aborts the commit
- **WHEN** `commit.template` is set, `git commit -s` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git aborts the commit with "you did not edit the message" and no commit is created

#### Scenario: Signed-off message gets the trailer
- **WHEN** `git commit -s -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message contains the trailer `Prepush-CI: full` and ends with the `Signed-off-by:` line

#### Scenario: Message equal to the template given with -m
- **WHEN** `commit.template` holds `Subject here` and `git commit -m "Subject here"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message is `Subject here` followed by the trailer `Prepush-CI: full`

#### Scenario: Edited commit template gets the trailer
- **WHEN** `commit.template` is set, `git commit` opens an editor that adds a line to the template and `PREPUSH_CI=full`
- **THEN** the commit's message contains the trailer `Prepush-CI: full`

#### Scenario: Message given with -m while a commit template is set
- **WHEN** `commit.template` is set and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message is `add x` followed by the trailer `Prepush-CI: full`

#### Scenario: Missing commit template file
- **WHEN** `commit.template` names a file that does not exist and `prepush-ci hook commit-msg <file>` runs on a file holding `add x` with `PREPUSH_CI=full`
- **THEN** the file holds `add x` followed by the trailer `Prepush-CI: full`

### Requirement: Known limits of the rebuilt cleanup
A `commit-msg` hook cannot see how git was started, so the hook SHALL rebuild the cleanup from `commit.cleanup`, else from whether an editor ran (`strip` with an editor, `whitespace` without). Where that differs from what git does, the hook MAY write the trailer into a message git would discard; these known limits are the scenarios below.

#### Scenario: Known limit, no-op editor with a comment-only template
- **WHEN** `commit.template` holds only `# only comments`, `git commit` runs with `GIT_EDITOR=:` and `PREPUSH_CI=full`
- **THEN** git creates a commit whose message is only `Prepush-CI: full`, where git alone would abort it as empty

#### Scenario: Known limit, no-op editor with a template that has text
- **WHEN** `commit.template` holds `Subject here`, a blank line and `# describe why`, `git commit` runs with `GIT_EDITOR=:` and `PREPUSH_CI=full`
- **THEN** git creates a commit whose message is `Subject here` followed by the trailer `Prepush-CI: full`, where git alone would abort it as unedited

#### Scenario: Known limit, template given with -t
- **WHEN** `git commit -t <file>` opens an editor that leaves the template unchanged and `PREPUSH_CI=full`
- **THEN** git creates a commit whose message is the template's text followed by the trailer `Prepush-CI: full`, where git alone would abort it as unedited

#### Scenario: Known limit, no-op editor on a message of comment lines
- **WHEN** `git commit -m "#123 x" --edit` runs with `GIT_EDITOR=:` and `PREPUSH_CI=full`
- **THEN** git creates a commit whose message is only `Prepush-CI: full`, where git alone would abort it as empty

#### Scenario: Known limit, cleanup mode on the command line
- **WHEN** `git commit --cleanup=strip -m "#123 x"` runs with `PREPUSH_CI=full`
- **THEN** git creates a commit whose message is only `Prepush-CI: full`, where git alone would abort it as empty

#### Scenario: Automatic comment character
- **WHEN** `core.commentChar` is `auto` and a commit runs with `PREPUSH_CI=full`
- **THEN** git aborts the commit and the error says that `auto` is not supported with `PREPUSH_CI=full`

### Requirement: Hook does nothing unless opted in
With `PREPUSH_CI` unset, empty or `off`, the hook SHALL leave the message unchanged and exit 0 without reading the config.

#### Scenario: Variable unset
- **WHEN** a commit runs without `PREPUSH_CI` in the environment
- **THEN** the commit's message is exactly the message given

#### Scenario: Variable off
- **WHEN** a commit runs with `PREPUSH_CI=off`
- **THEN** the commit's message is exactly the message given

#### Scenario: Not opted in and no config
- **WHEN** a repository has no config and a commit runs without `PREPUSH_CI`
- **THEN** the commit succeeds with the message unchanged

### Requirement: Unknown variable values are refused
With `PREPUSH_CI` set to any value other than `full`, `off` or the empty string (compared exactly, case-sensitive), the hook SHALL print an error naming the allowed values `full` and `off`, leave the message unchanged and exit non-zero, so git aborts the commit.

#### Scenario: Misspelled value
- **WHEN** a commit runs with `PREPUSH_CI=ful`
- **THEN** git aborts the commit and the error names `full` and `off`

#### Scenario: Upper-case value
- **WHEN** a commit runs with `PREPUSH_CI=FULL`
- **THEN** git aborts the commit and the error names `full` and `off`

### Requirement: Full mode needs a valid config
With `PREPUSH_CI=full`, the hook SHALL fail as the `config` capability specifies when the config is missing or invalid, leaving the message unchanged, so git aborts the commit.

#### Scenario: Full mode without config
- **WHEN** a repository has no config and a commit runs with `PREPUSH_CI=full`
- **THEN** git aborts the commit and the error names `.prepush-ci.toml`

#### Scenario: Full mode with an invalid config
- **WHEN** the config contains an unknown key and a commit runs with `PREPUSH_CI=full`
- **THEN** git aborts the commit and the error names the unknown key
