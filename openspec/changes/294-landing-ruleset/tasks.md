## 1. The request

- [x] 1.1 The builder holds no administration rights, so the request is tested against a local API only; say in the proof that no ruleset was created on GitHub, and that the first real run is the owner's (#296), who checks the ids with `doctor --ruleset`

## 2. The manifest

- [ ] 2.1 Add `--land` to `app setup`: the permissions, the printed next step; verify with specs named after the scenarios of "The landing app", "The landing app names the next step", "The app asks for its permissions" and "The app's name"

## 3. The ruleset command

- [x] 3.1 Add the pure body and its reading to `core/`, the three requests to `github_api.py` and `app_ruleset_command.py` with its subcommand in `cli.py`; verify with specs against a local API named after the scenarios of the requirements "The ruleset command takes one bypass actor", "The ruleset", "The bypass actor", "The token and the repository", "A ruleset that exists is kept" and "The exit status of the ruleset command"

## 4. The doctor check

- [ ] 4.1 Add `--ruleset` to `doctor` and the seventh check; verify with specs named after the scenarios of "The report", "The closing line and the exit status" and "The ruleset check reads the ruleset", "The ruleset check passes only for the landing ruleset" and "The ruleset check passes only for one bypass actor that can push"

## 5. Archive

- [ ] 5.1 Run `sh scripts/ci` and verify it passes
