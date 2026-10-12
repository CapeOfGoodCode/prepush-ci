Issue: #58

## Why

`install` records the interpreter that ran it, and the hooks start the tool through that interpreter. Under `uvx prepush-ci install`, the documented way, that interpreter lives in uv's cache. The first `uv cache prune` deletes it, and from then on every trailer commit loses its trailer and every push of one is refused until someone reruns `install`. `install` reports success and says nothing about this.

## What Changes

- When the interpreter `install` records for the native hooks lies inside uv's cache directory, `install` prints a warning on standard error that the interpreter is temporary, with the fix: `uv tool install prepush-ci`, then `prepush-ci install`.
- The warning is added on every run, including `already installed`; exit status, written files and the other output do not change.
- No other interpreter triggers it, and the manager entries of #10 (which call `prepush-ci` from `PATH`) never do.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: adds the requirement "A temporary interpreter is reported".

## Impact

- `install` gains a pure check (is this path inside that directory) and one `stderr` line; no new files, no runtime dependencies.
- The setup skill (#15) and `init` (#12) should recommend `uv tool install prepush-ci` over `uvx prepush-ci install`; that wording belongs to those slices, noted on #15.
