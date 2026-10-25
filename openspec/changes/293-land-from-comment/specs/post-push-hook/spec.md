## ADDED Requirements

### Requirement: Only a pass of the committed config is shown
The comment names the `check` and the `preflight` committed in `HEAD`, so the hook SHALL treat as a recorded pass only a ref of the tree whose `config` digest (see `run-cache`) is that of the config committed in `HEAD`. A pass of another config, or with no digest, SHALL be no pass here: the other requirements, the pass that is shown and the latest pass for the facts, SHALL leave it out. When none is left, the hook SHALL do nothing, print nothing and send no request.

#### Scenario: A pass of a check that is not the committed one
- **WHEN** the config committed in `HEAD` has `check = "scripts/ci"`, an ignored worktree config has `check = "true"`, and a trailer commit was pushed with the hook, which passed `true`
- **THEN** it prints nothing and sends no request

#### Scenario: Another require_env
- **WHEN** the ignored worktree config adds a variable to `require_env` that the committed config lacks, and the pushed trailer commit passed
- **THEN** it prints nothing and sends no request

#### Scenario: A pass without a digest
- **WHEN** the only result ref of the tree has no `config` paragraph
- **THEN** it prints nothing and sends no request

#### Scenario: An older pass of the committed config
- **WHEN** a pass of the committed config exists for the tree and a later pass of another config exists for the same tree
- **THEN** the body holds the facts of the first
