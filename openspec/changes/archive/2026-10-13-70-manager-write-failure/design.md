## Context

The manager install reads and edits every file in memory first, so a refusal the command decides itself leaves all files alone. The writes come after, one file at a time. A write can still fail for a reason only the operating system knows: permissions, a full disk, a path component that is not a directory.

## Decisions

- **Undo instead of a pre-check.** Checking writability first (`os.access`) is wrong for a user who is root, on Windows, and on file systems that refuse later; only an attempted write tells the truth. So the command writes, and on the first `OSError` puts back what it wrote. Rationale: the guarantee ("no file of the manager changed") then holds whatever the cause.
- **Undo is best effort.** If restoring a file fails too, the command still reports the original failure first; it adds a line of its own after the message naming each file it could not restore (stated in the requirement), so the user knows what to repair by hand. This path has no scenario: a failure of the undo cannot be set up the same way on every platform.
- **The message names the file and the reason**, in the form of the existing refusals (`prepush-ci install: <file>: <reason>`), with the file relative to the worktree root.
- **One cause covered by the scenarios.** An unwritable `.husky` ends in the same `OSError` at the first write as a read-only file does later; a directory permission cannot be set up the same way on Windows or for root, so only the read-only file has scenarios.
