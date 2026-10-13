## Context

`require_env` is a list of strings, and the preflight step refuses a push when one of them is unset or empty. An entry that the tool can never see makes that refusal permanent. Today:

```
$ printf 'check = "true"\nrequire_env = [""]\n' > .prepush-ci.toml
$ prepush-ci doctor
ok config: loaded from .prepush-ci.toml
...
fail preflight: these environment variables are unset or empty:
  fix: set  (`require_env` in the config); the command was not run

$ prepush-ci init --non-interactive --check true --require-env "" --hooks none
written: .prepush-ci.toml          # require_env = [""]
```

An invalid value of another key is reported at load, with the key named:

```
$ printf 'check = "true"\ntrailer = { value = "" }\ncache = "yes"\n' > .prepush-ci.toml
$ prepush-ci doctor
fail config: .prepush-ci.toml: `trailer.value` must be a non-empty single line ...; .prepush-ci.toml: `cache` must be a boolean
```

## Decisions

### What a valid name is

A name is valid when it matches `[A-Za-z_][A-Za-z0-9_]*`.

Why: the pre-push hook is `#!/bin/sh`, and where `sh` is dash (Debian, Ubuntu) it drops every environment variable whose name is not a shell identifier before the tool starts. A name such as `DATABASE URL` or `MY-VAR` can be set in a process, but a push through the hook never sees it: the push is refused as "unset or empty" with the variable set, while `doctor` run directly says `ok`. Terminator found this in the attack on the first round of this change, which allowed such names. The portable form is the only one that works the same in the hook, in `doctor` and in `run`.

```
$ env 'DATABASE URL=x' MY-VAR=y DATABASE_URL=z bash probe.sh
'x' 'y' 'z'
$ env 'DATABASE URL=x' MY-VAR=y DATABASE_URL=z sh probe.sh      # /bin/sh -> dash
None None 'z'
```

`probe.sh` is `#!/bin/sh` and runs a Python that prints `os.environ.get` of the three names. Under bash all three arrive; under dash only the identifier does. An entry with `=` or an empty one cannot be set at all (`env 'A=B=1'` sets `A`).

### Where it is checked

Only in config loading. `init` already refuses a config that does not load (exit 1, nothing written), for the flag and for the interactive answer, so the one check covers `init --require-env ""`.

Why: one rule in one place, and no second copy in `init` to drift.
