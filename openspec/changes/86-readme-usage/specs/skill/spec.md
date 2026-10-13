## ADDED Requirements

### Requirement: The skill has the user confirm the check and works on a branch
Before it runs `init`, the skill SHALL have the agent ask the user to confirm the command that is the full check and the CI steps it covers, and SHALL NOT let it continue without that confirmation. The skill SHALL tell the agent to work on a branch and open a pull request with the result, and not to push to the default branch. The README states both (`readme` capability).

#### Scenario: The check is confirmed
- **WHEN** the steps of the skill are read in order
- **THEN** the step that has the user confirm the check command and the steps it covers comes before the step that runs `init`, and says not to continue without a confirmed check

#### Scenario: Work on a branch
- **WHEN** a reader looks at the opening of the skill
- **THEN** it says to work on a branch, open a pull request with the result and not to push to the default branch

### Requirement: The skill has the agent find the check and set up the services
The skill SHALL have the agent read the CI definitions of the repository and find, or write, one command that runs the steps pull request CI runs. It SHALL have the agent list the services and variables CI provides and put them in the preflight so that a missing service fails the full check, and SHALL NOT allow a suite that skips its tests for a missing service. The README states these (`readme` capability).

#### Scenario: One command for the check
- **WHEN** a reader looks at the first step of the skill
- **THEN** it has the agent read the CI definitions and find or write one command that runs the pull request steps

#### Scenario: A missing service fails the check
- **WHEN** a reader looks at the services and preflight step of the skill
- **THEN** it says a missing service fails the full check and the tests are never skipped for it
