# Design

## Context

The hooks of #9 start `<python> -m prepush_ci` with the interpreter recorded by `install`, and fail closed (push) or open (commit) when it is gone. See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** a user who installs through `uvx` learns at install time that the hooks will stop working, and what to do.

**Non-Goals:** making hooks survive a cache prune by themselves, changing what the hooks do when the interpreter is gone (specified in #9), the manager entries (#10), the wording of the skill (#15).

## Decisions

- **Warn; do not refuse and do not rewrite the hooks.** The hooks work until the cache is pruned, and `install` cannot know a better interpreter: `PATH` may hold a different version, and `uvx` cannot be called per hook without a network and a pinned version. Refusing would break a working setup for a risk that may never come; the warning names the one-line fix.
- **"Temporary" means inside uv's cache directory, by path alone.** `install` does not run `uv`: standard library only, and a test needs no uv. The directory follows uv's own lookup: `UV_CACHE_DIR` when set and not empty (a relative value is relative to the working directory, as in uv), otherwise on Windows `%LOCALAPPDATA%\uv\cache`, otherwise `$XDG_CACHE_HOME/uv` when set, else `$HOME/.cache/uv` (uv uses this on macOS too, not `~/Library/Caches`). `uvx` runs with `UV_CACHE_DIR` unset, so the default lookup is the case that matters; the variable is the test hook. This covers `uvx` and `uv run --with`; an interpreter from `uv tool install` lives in uv's tools directory, outside the cache, and is persistent.
- **The interpreter's path is compared as written, never resolved; the cache directory is taken as found and with its links resolved.** The hooks run the recorded path, so only that path vanishes, and a virtualenv interpreter in the cache is a symlink to a persistent Python: resolving it would hide the problem. uv, however, records the interpreter under the real path of its cache, and a cache behind a link (`~/.cache` on another disk, a linked `UV_CACHE_DIR`) is common, so the directory is tried in both forms. A directory that cannot be resolved (it does not exist yet) is used as found. "Inside" means the cache directory is a whole-component prefix of the path, so `…/uv2/bin/python` is not inside `…/uv`.
- **The warning goes on every run, standard error, exit 0.** An `already installed` run is still a temporary setup; staying silent there would let the first run's warning scroll away. The `installed`/`updated`/`already installed` line and the idempotence guarantee are untouched.
- **The check is a pure function in `core/`** (path, cache directory → bool), so the unit tier covers it; the lookup of the cache directory from the environment sits next to the command.

## Risks / Trade-offs

- [A cache directory that only uv sees (`cache-dir` in `uv.toml`, `uvx --cache-dir`, `--no-cache` and `UV_NO_CACHE`, whose cache is a temporary directory) is not seen by an environment-variable lookup] → no warning in those cases; the hooks still fail as specified in #9 and `doctor` (#14) can report the vanished interpreter.
- [A path-only check misses other temporary interpreters (a tmp directory, a CI workspace)] → out of scope; only the documented `uvx` path is the problem reported.
