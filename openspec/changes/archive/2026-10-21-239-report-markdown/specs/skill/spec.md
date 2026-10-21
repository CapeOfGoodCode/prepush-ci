## ADDED Requirements

### Requirement: The documentation section has every session show its result on the pull request
The section that the skill has the agent add to `CLAUDE.md` or `AGENTS.md` (the documentation step), which every later session reads, SHALL tell the agent: after a push of a commit with the trailer to a branch with a pull request, run `prepush-ci report --markdown --result passed --tree "$(git rev-parse 'HEAD^{tree}')"` and put its output into the one comment of that check on the pull request. The invocation SHALL pass "Every command in the skill exists".

#### Scenario: The instruction is in the section later sessions read
- **WHEN** a reader looks at the documentation step of the skill
- **THEN** the section it has the agent write holds the instruction to run that command after a push, written as an agent runs it

#### Scenario: Without a pull request
- **WHEN** a reader looks at that instruction
- **THEN** it says to post nothing when the branch has no pull request

#### Scenario: The invocation exists
- **WHEN** the check "Every command in the skill exists" reads the skill
- **THEN** it reports nothing for `report --markdown`

### Requirement: The comment is updated, found by its marker
The instruction SHALL tell the agent to find the comment of the pull request whose body holds the marker line `<!-- prepush-ci:`, followed by the check's name, update it, and create a comment only when none holds the marker. It SHALL tell the agent not to use `--edit-last`, which edits the last comment of the user whatever it says.

#### Scenario: Update, not add
- **WHEN** a reader looks at that instruction
- **THEN** it names the marker `<!-- prepush-ci:`, says to update the comment that holds it and to create one only when none does

#### Scenario: The wrong comment is not edited
- **WHEN** a reader looks at that instruction
- **THEN** it names `--edit-last` as not to be used and says why
