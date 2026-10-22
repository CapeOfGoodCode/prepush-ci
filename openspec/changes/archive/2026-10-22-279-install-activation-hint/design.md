## Context

`install` reports each manager file it checked or wrote and ends with `next: run `<manager> install` to activate the hooks`. `doctor` already decides whether a manager's hooks are active ("pre-commit and lefthook are activated"): the hook of the name in the directory git uses for hooks exists, is executable and contains `pre-commit` or `lefthook`.

How pre-commit behaves (checked with pre-commit 4.7.0 in an empty repository with `.pre-commit-config.yaml`):

```
$ pre-commit install
pre-commit installed at .git/hooks/pre-commit
$ pre-commit install --hook-type commit-msg --hook-type pre-push
pre-commit installed at .git/hooks/commit-msg
pre-commit installed at .git/hooks/pre-push
$ ls -l .git/hooks/pre-push; grep -c pre-commit .git/hooks/pre-push
-rwxr-xr-x 1 loop loop 639 ... .git/hooks/pre-push
5
```

Before the first install `.git/hooks` holds no `commit-msg` or `pre-push`; the default install writes only `pre-commit`, so the hooks `install` adds are not active until `default_install_hook_types` (which `install` writes) makes the next `pre-commit install` write all three.

## Decisions

- **Same test as `doctor`, not a new one.** Silence about activation then never contradicts `doctor`: when `install` is silent, `doctor` passes the activation check, and the reverse. Both hooks must be active for silence; one missing prints the command.
- **Lefthook gets the same rule.** The issue names pre-commit, but the report is one requirement for both managers and `doctor` treats them alike; leaving lefthook with a line that is sometimes wrong would be a second bug of the same kind.
- **Nothing replaces the line.** When the hooks are active `install` prints no activation line at all, as it does for husky.
