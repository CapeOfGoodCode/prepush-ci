## ADDED Requirements

### Requirement: The skill proposes the hook that shows the result after every push
After the documentation step the skill SHALL have the agent explain, in a sentence, a Claude Code hook that creates or updates the comment of the check on the pull request after every successful `git push` of a commit with the trailer, and ask the user for a yes. Without the yes the agent SHALL change no file, and the rule of the documentation step stays the fallback for agents without hooks.

#### Scenario: The proposal is made and needs a yes
- **WHEN** a reader looks at the step of the skill that proposes the hook
- **THEN** it says what the hook does, asks the user for a yes before it changes `.claude/settings.json`, and says to change nothing without it

#### Scenario: The rule stays as the fallback
- **WHEN** a reader looks at the step and at the documentation step
- **THEN** the documentation step still holds the instruction to run `report --markdown` after a push, and the proposal says it stays for agents without hooks

### Requirement: The hook is added to the settings
With the user's yes the skill SHALL have the agent add to `.claude/settings.json` one group in `hooks.PostToolUse`: `matcher` `Bash`, a `hooks` list with `{"type": "command", "command": …, "timeout": 30}`, the command running `prepush-ci hook post-push` with the directory `uv tool dir --bin` prints in front of `PATH`. It SHALL keep every other setting and add nothing when a command there already runs `hook post-push`. The invocation SHALL pass "Every command in the skill exists".

#### Scenario: The setting is spelled out
- **WHEN** a reader looks at that step
- **THEN** it shows the group for `hooks.PostToolUse` with the matcher `Bash`, a `timeout` of 30 and a command that runs `prepush-ci hook post-push` with `uv tool dir --bin` in front of `PATH`

#### Scenario: Nothing else changes
- **WHEN** a reader looks at that step
- **THEN** it says to keep every other setting and to add nothing when the hook is there already

#### Scenario: The invocation exists
- **WHEN** the check "Every command in the skill exists" reads the skill
- **THEN** it reports nothing for `hook post-push`

### Requirement: The hook command is silent where the tool is not installed
The command of the hook SHALL run `prepush-ci hook post-push` only when `prepush-ci` is found on the `PATH` it builds, and otherwise SHALL do nothing and exit 0, with nothing on either stream. It SHALL NOT put an empty entry, which the shell reads as the current directory, in front of `PATH` when `uv` is absent, fails or prints no directory.

#### Scenario: The tool is not installed
- **WHEN** the command of the skill's group runs through `sh -c` with a `PATH` that holds no `prepush-ci`, and a payload of a `git push` on standard input
- **THEN** it exits 0 and prints nothing

#### Scenario: The tool is installed
- **WHEN** the command runs with `prepush-ci` in the directory `uv tool dir --bin` prints
- **THEN** it runs `prepush-ci hook post-push` with the payload and exits 0, whatever status that command had

#### Scenario: uv is not installed
- **WHEN** the command runs with a `PATH` that has neither `uv` nor `prepush-ci`, in a directory that holds an executable file `prepush-ci`
- **THEN** it exits 0, prints nothing and does not run that file

#### Scenario: uv prints no directory
- **WHEN** the command runs with a `uv` that exits 0 and prints nothing, and a `PATH` without `prepush-ci`, in a directory that holds an executable file `prepush-ci`
- **THEN** it exits 0, prints nothing and does not run that file
