# Tasks

## 1. The hooks directory

- [x] 1.1 Add `prepush-ci install`: find the git directories, record the interpreter and the previous hooks directory, write the `commit-msg` and `pre-push` scripts and set the local `core.hooksPath`; verify with integration specs that make real commits and pushes in temporary repositories (trailer written, check run on push, no `prepush-ci` on `PATH`)
- [x] 1.2 Keep what existed: run the previous hook first for both scripts with the same arguments and standard input, abort when it fails, forward the other hooks of the previous directory, ignore `*.sample`, leave the previous directory untouched; verify with specs for `.git/hooks` and for an existing `core.hooksPath`
- [x] 1.3 Make it idempotent and report `installed`, `updated` or `already installed`; fail with a message outside a git repository; verify with specs that run `install` twice, from another interpreter, and after a new hook appeared
- [ ] 1.4 Handle a missing interpreter: `pre-push` refuses naming `prepush-ci install`, `commit-msg` warns and lets the commit go; verify with specs
- [ ] 1.5 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 9-install-native-hooks`) before the pull request is marked ready.
