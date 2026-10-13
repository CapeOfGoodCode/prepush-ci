Issue: #70

## Why

`install --hooks husky` writes two files. When the second cannot be written (a read-only `.husky/pre-push`, a `.husky` the user may not write to) the command dies with a Python traceback after the first file already holds the block. The user is left with half an install and no message saying which file to fix. The spec promises that a refused run writes no file of the manager, but only for refusals the command decides itself, not for a write the operating system refuses.

## What Changes

- A write the operating system refuses during a manager install ends the command with exit 1 and one message that names the file and the reason, without a traceback.
- Every file the run already wrote is put back as it was: contents restored, a file the run created removed.
- The same holds for all three managers: the write loop is shared.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: adds the requirement "A refused write is undone" and narrows "Manager installs are idempotent": its sentence on a refused run now covers refusals `install` decides before the first write; a write the operating system refuses falls under the new requirement.

## Impact

- The write loop of the manager install gains an undo step; no new files, no runtime dependencies, no change when every write succeeds.
- Native hooks (`core.hooksPath`) are not touched: they write into the git directory, which the command already needs to create, and the issue reports no failure there.
