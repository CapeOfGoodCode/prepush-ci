## ADDED Requirements

### Requirement: The README says nothing of an unreleased state
`README.md` SHALL NOT say the tool is under construction or unreleased, and SHALL NOT send the reader to install or run it from the git repository instead of PyPI. It SHALL NOT contain the phrases `under construction`, `Nothing here is released yet` or `until the first release`, nor the address `git+https://github.com/CapeOfGoodCode/prepush-ci`. The phrases are matched ignoring case and with every run of whitespace, a line break included, read as one space; the address is matched as it is.

#### Scenario: The shipped README has no pre-release wording
- **WHEN** the check reads the `README.md` of the repository
- **THEN** it finds none of `under construction`, `Nothing here is released yet`, `until the first release` and `git+https://github.com/CapeOfGoodCode/prepush-ci`

#### Scenario: A leftover status box
- **WHEN** the check reads a README text with the line `> **Status: under construction.**`
- **THEN** it reports `under construction` as pre-release wording

#### Scenario: A phrase in other case or across a line break
- **WHEN** the check reads a README text with `Until the first release is on PyPI` at the start of a sentence, and another with `nothing here is\nreleased yet` broken over two lines
- **THEN** it reports `until the first release` in the first and `Nothing here is released yet` in the second as pre-release wording

#### Scenario: A leftover install from git
- **WHEN** the check reads a README text with the code line `uv tool install git+https://github.com/CapeOfGoodCode/prepush-ci`
- **THEN** it reports the address as pre-release wording

## REMOVED Requirements

### Requirement: The agent step has a form that runs before the first release
**Reason**: The first release is on PyPI (0.1.0), so `uvx prepush-ci skill` runs as the prompt gives it; the requirement pinned the sentence for the time before, which the new requirement "The README says nothing of an unreleased state" now forbids.
**Migration**: None; the prompt, the plugin commands and `skill --write` of the agent step are unchanged.
