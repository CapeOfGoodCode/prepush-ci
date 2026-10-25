## ADDED Requirements

### Requirement: The README names the landing example
The README SHALL name `docs/ci/land.yml`, and that file SHALL exist; it SHALL name every variable and secret the file reads through `vars.` and `secrets.`. The check fails when the README names a `docs/ci/` file that does not exist, or leaves out a name the example reads.

#### Scenario: The shipped README passes
- **WHEN** the check reads the `README.md` and `docs/ci/land.yml` of the repository
- **THEN** it finds nothing missing

#### Scenario: A name left out
- **WHEN** the check reads a README text that names `docs/ci/land.yml` and `PREPUSH_CI_APP_ID` but not `PREPUSH_CI_APP_KEY`
- **THEN** it reports `PREPUSH_CI_APP_KEY` as missing

#### Scenario: A file that does not exist
- **WHEN** the check reads a README text that names `docs/ci/merge.yml`
- **THEN** it reports that `docs/ci/merge.yml` does not exist
