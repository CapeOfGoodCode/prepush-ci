## ADDED Requirements

### Requirement: A temporary interpreter is reported
When `install` writes native hooks and the interpreter it records lies inside uv's cache directory, it SHALL print a warning on standard error that the interpreter is temporary and the hooks stop working when uv cleans its cache, and that names the fix, `uv tool install prepush-ci` followed by `prepush-ci install`. The warning SHALL NOT change the exit status, the files written or the `installed`, `updated` or `already installed` line.

#### Scenario: Interpreter in the uv cache
- **WHEN** `UV_CACHE_DIR` names a directory that contains the interpreter running `install`, and `install` runs
- **THEN** it exits 0, standard error contains `temporary` and `uv tool install prepush-ci`, and the hooks directory holds the hooks as without the warning

#### Scenario: Interpreter outside the uv cache
- **WHEN** `UV_CACHE_DIR` names a directory that does not contain the interpreter running `install`, and `install` runs
- **THEN** standard error does not contain `temporary`

#### Scenario: The warning comes back on a rerun
- **WHEN** `install` ran with the interpreter inside `UV_CACHE_DIR` and runs again
- **THEN** the second run prints `already installed` and standard error contains `temporary` again

### Requirement: Where uv's cache directory is
uv's cache directory SHALL be found as uv does: `UV_CACHE_DIR` when set and not empty, a relative value taken relative to the working directory; otherwise, on Windows, `%LOCALAPPDATA%\uv\cache`; otherwise `$XDG_CACHE_HOME/uv` when `XDG_CACHE_HOME` is set and not empty, else `$HOME/.cache/uv`, on every other platform.

#### Scenario: The default under XDG_CACHE_HOME
- **WHEN** `UV_CACHE_DIR` is unset, `XDG_CACHE_HOME/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: The default under HOME
- **WHEN** `UV_CACHE_DIR` and `XDG_CACHE_HOME` are unset, `$HOME/.cache/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: An empty UV_CACHE_DIR is ignored
- **WHEN** `UV_CACHE_DIR` is empty, `XDG_CACHE_HOME/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: A relative UV_CACHE_DIR
- **WHEN** `UV_CACHE_DIR` is `cache`, the working directory holds `cache/` with the interpreter running `install` inside, and `install` runs there
- **THEN** standard error contains `temporary`

### Requirement: Inside the cache means whole path components
The interpreter SHALL count as inside the cache directory only when the path components of the directory, as found or with its symbolic links resolved, are a prefix of the interpreter's path components. The interpreter's path SHALL be compared as written and never resolved. A directory that merely shares a name prefix with the cache directory SHALL NOT count.

#### Scenario: A sibling directory with the same name prefix
- **WHEN** `UV_CACHE_DIR` is `<base>/uv` and the interpreter running `install` is `<base>/uv2/bin/python`
- **THEN** standard error does not contain `temporary`

#### Scenario: A virtualenv interpreter that links out of the cache
- **WHEN** the interpreter running `install` is a symbolic link inside `UV_CACHE_DIR` that points to a Python outside it
- **THEN** standard error contains `temporary`

#### Scenario: The cache directory is a symbolic link
- **WHEN** `UV_CACHE_DIR` is a symbolic link to `<base>/real` and the interpreter running `install` is `<base>/real/archive-v0/x/bin/python`
- **THEN** standard error contains `temporary`

#### Scenario: The default cache lies behind a symbolic link
- **WHEN** `UV_CACHE_DIR` and `XDG_CACHE_HOME` are unset, `$HOME/.cache` is a symbolic link to `<base>/disk`, and the interpreter running `install` is inside `<base>/disk/uv`
- **THEN** standard error contains `temporary`

#### Scenario: A sibling of the link target
- **WHEN** `UV_CACHE_DIR` is a symbolic link to `<base>/real` and the interpreter running `install` is `<base>/real2/bin/python`
- **THEN** standard error does not contain `temporary`

#### Scenario: A cache directory that does not exist
- **WHEN** `UV_CACHE_DIR` names a directory that does not exist and the interpreter running `install` is outside it
- **THEN** standard error does not contain `temporary` and `install` exits as it would without the variable
