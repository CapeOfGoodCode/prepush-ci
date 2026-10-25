## ADDED Requirements

### Requirement: A recorded pass names the config it ran with
When the tool records a pass, the message of the result commit SHALL end with the paragraph `config <digest>`, the digest being the first 32 hex digits of the SHA-256 of the JSON list of `check`, `preflight`, `require_env` and `require_up_to_date` of the config the run used (the inputs of the key, less the output of the preflight). A ref without that paragraph SHALL stay a valid pass for `run`, the pre-push hook and `land`.

#### Scenario: The digest is recorded
- **WHEN** `prepush-ci run` passes with `check = "true"`
- **THEN** the message of the result commit ends with a paragraph `config ` and 32 hex digits

#### Scenario: Another check, another digest
- **WHEN** a pass is recorded for a tree, the ignored worktree config changes `check` to another command and that passes on the same tree
- **THEN** the two refs record two digests

#### Scenario: A pass without a digest
- **WHEN** the result ref points at a commit whose message names the checked commit and holds no `config` paragraph
- **THEN** pushing that tree skips the check, as for any cached pass

#### Scenario: The facts are still read
- **WHEN** a pass is recorded with facts
- **THEN** the post-push hook reads the facts of that ref, with the `config` paragraph after them
