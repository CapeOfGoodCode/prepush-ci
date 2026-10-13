Issue: #157

## Why

The commit-msg hook hands the configured trailer to `git interpret-trailers` as an argument. On `main`, under an ASCII locale (`LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`), a trailer value such as `jä` cannot be encoded as an operating system string: the hook ends in a `UnicodeEncodeError` traceback and git aborts the commit. Terminator found it while attacking #147 (#157).

The code of #151 (PR #154) already fixes it: every subprocess argument goes through `text_io`, which converts it with `to_os`, and the requirements of `text-encoding` already say that conversion is exact. What #154 lacks is a scenario that holds this case: no test hands git a non-ASCII value from the config. This change adds that one scenario to the requirement that names the hooks and non-ASCII arguments.

## What Changes

- The requirement "Every command handles non-ASCII names the same way" of `text-encoding` also names a non-ASCII config value that a command hands on to git (the trailer), and gets one scenario: a trailer value `jä` is written as UTF-8 by the commit-msg hook, with no traceback.
- No new requirement: the rule (the tool's text is UTF-8, the locale decides only the operating system's strings) is #154's.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `text-encoding`: one requirement modified, one scenario added. The capability is created by #151 (PR #154); this change is built and archived after that one.

## Impact

- `tests/integration/commit_msg_hook_spec.py`: one scenario, run in both variants of #154. It passes on top of #154 and fails on `main`.
- No change to `src/`, apart from what #154 has already done.
