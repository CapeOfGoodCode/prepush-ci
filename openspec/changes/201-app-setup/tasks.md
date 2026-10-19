# Tasks

## 1. The command

- [ ] 1.1 Add `app setup` with `--org`, `--name` and `--timeout`: the loopback page that posts the manifest, the check of the callback's `state`, the exchange of the code and the exit statuses; verify with unit specs for the manifest, the name and the callback decision and integration specs for each scenario of "Setup serves one page on the loopback address", "The app asks for one permission", "GitHub's answer completes the setup" and "The exit status says whether the app was created"
- [ ] 1.2 Save the key outside the repository and print the result; verify with the scenarios of "The key is saved outside the repository", "Secrets stay out of the output" and "The result names what report needs", including the one that runs `report` with the printed values

## 2. README and archive

- [ ] 2.1 Add the entry for `app setup` to the README's reference and the paragraph on setting the app up (design.md, "The README paragraph is not pinned by a requirement"); verify with the `readme` drift specs
- [ ] 2.2 Run `sh scripts/ci` and verify it passes
