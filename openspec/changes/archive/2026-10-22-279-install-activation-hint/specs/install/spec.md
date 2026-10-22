## MODIFIED Requirements

### Requirement: The manager report
For a manager, `install` SHALL print each file it checked or wrote, relative to the worktree root. For pre-commit and lefthook it SHALL also print the command that activates the hooks, `pre-commit install` or `lefthook install`, unless the hooks are active (requirement "Active hooks"). For husky it SHALL print no activation command.

#### Scenario: Report for pre-commit
- **WHEN** `install` runs for pre-commit and `.git/hooks/commit-msg` and `.git/hooks/pre-push` do not exist
- **THEN** the output names `.pre-commit-config.yaml` and contains `pre-commit install`

#### Scenario: Report for lefthook that is not activated
- **WHEN** `install` runs for lefthook and `.git/hooks/pre-push` does not exist
- **THEN** the output names `lefthook.yml` and contains `lefthook install`

#### Scenario: Report for husky
- **WHEN** `install` runs for husky
- **THEN** the output names `.husky/commit-msg` and `.husky/pre-push` and contains no activation command

## ADDED Requirements

### Requirement: Active hooks
The hooks of pre-commit or lefthook SHALL count as active when the files `commit-msg` and `pre-push` in the directory git uses for hooks (the effective `core.hooksPath`, else the directory `git rev-parse --git-path hooks` prints) both exist, are executable and contain the manager's name, `pre-commit` or `lefthook`: the condition the `doctor` requirement "pre-commit and lefthook are activated" checks. When they are active, `install` SHALL print no activation command.

#### Scenario: Report for pre-commit that is activated
- **WHEN** `install` ran, `pre-commit install` ran, and `install` runs again for pre-commit
- **THEN** the output names `.pre-commit-config.yaml` and does not contain `pre-commit install`

#### Scenario: Only one hook is active
- **WHEN** `.git/hooks/commit-msg` is an executable script that contains `pre-commit`, `.git/hooks/pre-push` does not exist and `install` runs for pre-commit
- **THEN** the output contains `pre-commit install`

#### Scenario: Only the default hook type is active
- **WHEN** `install` ran, `pre-commit install --hook-type pre-commit` ran, and `install` runs again for pre-commit
- **THEN** the output contains `pre-commit install`

#### Scenario: Report for lefthook that is activated
- **WHEN** `.git/hooks/commit-msg` and `.git/hooks/pre-push` are executable scripts that contain `lefthook` and `install` runs for lefthook
- **THEN** the output names `lefthook.yml` and does not contain `lefthook install`

#### Scenario: Activated hooks in another hooks directory
- **WHEN** `core.hooksPath` is `.githooks`, the executable scripts `commit-msg` and `pre-push` there contain `pre-commit`, and `install` runs for pre-commit
- **THEN** the output does not contain `pre-commit install`
