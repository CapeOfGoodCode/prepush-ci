## MODIFIED Requirements

### Requirement: The agent step says what the agent asks
The agent step SHALL say that the agent always stops to ask the user to confirm the full check command and what pre-push should do on their own machines, and asks more only where the repository leaves something open: the hook manager when there are two, the default branch when `origin` is missing, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and a yes before it removes a hook.

#### Scenario: What the agent always asks
- **WHEN** a reader looks at the agent step
- **THEN** it says the agent always asks the user to confirm the check command and what pre-push should do locally

#### Scenario: What the agent asks only sometimes
- **WHEN** a reader looks at the agent step
- **THEN** it says the agent also asks which hook manager to use when there are two, for the default branch when `origin` is missing, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and for a yes before it removes a hook, and not otherwise
