## Decisions

- **The command is `git symbolic-ref refs/remotes/origin/HEAD`, the full ref.** It prints `refs/remotes/origin/main`, still one `git` call without a shell (the suite also runs on Windows). `--short` prints the shortest unambiguous name, which is `remotes/origin/trunk` when a local branch `origin/trunk` exists, and `init` would accept that wrong name; the full ref never depends on other refs. An agent that forgets to remove the prefix meets the config's refusal with `use "<name>"` (#111). A branch such as `release/1` keeps its slash.
- **Without `origin/HEAD` the agent asks.** The command then fails (`git` exits 128). Omitting the flag would make `init` write nothing and the hooks assume `main`, which is wrong for a repository whose default branch is another one, and a wrong name is the failure #111 closed. The user's answer goes in as given; `init` rejects a value that is not a bare name.

## Tools run

- `git symbolic-ref refs/remotes/origin/HEAD` and its `--short` form with `origin/HEAD` set to `trunk` and to `release/1`, with a local branch `origin/trunk` next to it, and without `origin/HEAD`, to confirm the output and the exit status stated in the scenarios.
