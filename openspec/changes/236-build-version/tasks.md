# Tasks

## 1. Print where the build came from

- [x] 1.1 Add a function to `core/` that turns the text of `direct_url.json` into the suffix (` (git <12 characters>)`, ` (direct install)` or nothing), and make `--version` read the record of the installed distribution and print the version with the suffix; verify with unit specs for a git record, a record with a short, missing, non-string or non-hex `commit_id`, another or a non-string VCS, a directory record (editable or not), an archive record, invalid JSON, a value that is not an object, a known key that is not an object and no record, each with exit 0 and an empty standard error, and with an integration spec that runs `--version` from a source checkout and from a wheel installed with a git record
- [ ] 1.2 Run `sh scripts/ci` and verify it passes
