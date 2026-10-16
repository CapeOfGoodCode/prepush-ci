## ADDED Requirements

### Requirement: The agent step's prompt runs a command the CLI has and links to no skill on GitHub
The usage section SHALL have a `###` step whose heading names the agent (the agent step), so that the checks can find it. The code block of the agent step SHALL contain the prompt to hand the agent, and the check SHALL find in it the invocation `prepush-ci skill` and no command or option the CLI lacks. The agent step SHALL NOT link to `skills/prepush-ci-setup/SKILL.md` on GitHub: a link to the default branch drifts from the released skill.

#### Scenario: The agent step exists
- **WHEN** the check looks for a `###` step of the usage section whose heading names the agent
- **THEN** it finds exactly one, and reports a problem, not an exception, when it finds none

#### Scenario: No link to the skill on GitHub
- **WHEN** the check takes the links of the agent step
- **THEN** none of them is a link to `skills/prepush-ci-setup/SKILL.md` on the default branch

#### Scenario: The prompt's command exists
- **WHEN** the check reads the code block of the agent step
- **THEN** it finds the invocation `prepush-ci skill` and reports no unknown command or option

## REMOVED Requirements

### Requirement: The agent step hands the agent the skill command
**Reason**: Pins the place of the step and the words of its prompt (`follow`, the ask to set the repository up). What can drift, the prompt's command and the link to the default branch, moves to the new requirement "The agent step's prompt runs a command the CLI has and links to no skill on GitHub".
**Migration**: The scenarios "No link to the skill on GitHub" and "The prompt's command exists" carry over unchanged; "The agent step comes first" and "A prompt to hand over" are removed.

### Requirement: Each entry says what the command is for
**Reason**: Pins what the README says and how: one sentence per entry, "git runs it", an example per entry. That is prose, which the `readme` spec does not check (AGENTS.md, "The `readme` spec checks drift, not prose"). The synopsis of each entry is still required by "The reference lists every command and flag".
**Migration**: None.

### Requirement: The agent step names the other way and the manual path
**Reason**: Pins what the agent step names and says. Prose.
**Migration**: None. The command `prepush-ci skill --write` stays checked by "The README uses only what the CLI has".

### Requirement: The agent step says what the agent needs and delivers
**Reason**: Pins what the agent step says. Prose.
**Migration**: None.

### Requirement: The agent step says what the agent asks
**Reason**: Pins what the agent step says. Prose.
**Migration**: None.

### Requirement: The usage section walks from install to a push
**Reason**: Pins the order of the steps, the steps themselves and the wording of the gate step. Structure and prose.
**Migration**: None. The commands in the steps stay checked by "The README uses only what the CLI has".

### Requirement: The usage section says what to do about a refused push
**Reason**: Pins what the step names and the number of sentences. Prose.
**Migration**: None. `run`, `doctor` and `strip` stay checked by "The README uses only what the CLI has" and "The reference lists every command and flag".

### Requirement: The README says nothing of an unreleased state
**Reason**: Pins the wording of the README, not its agreement with the code; a stale status line is a README-only text change, a `Task`.
**Migration**: None.
