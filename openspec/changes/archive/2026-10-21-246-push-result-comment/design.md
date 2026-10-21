## Context

`PostToolUse` hooks of Claude Code run a command after a tool call, with a JSON object on standard input; the fields this change reads are `tool_name`, `tool_input.command` and `cwd`. The cloud session's API proxy supplies credentials for `api.github.com` and refuses GraphQL (#232, #239).

## Verified with the tools

Claude Code 2.1.301 (the binary names `PostToolUseFailure` as its own event, "Run after tool fails", beside `PostToolUse`): a hook registered for `PostToolUse` only is not run for a command that failed. I could not run a hook payload here (the session is not logged in), so the exact payload is not shown; the trial below checks it.

`git` 2.39.5, a push updates the remote-tracking ref only for what it pushed:

```
$ git push -q origin main; git rev-parse --short refs/remotes/origin/main HEAD
ca476a5
ca476a5
$ git push -q origin HEAD:other; git rev-parse -q --verify refs/remotes/origin/topic || echo none
none                      # HEAD is branch topic; nothing named topic went up
$ git push -q origin topic; git rev-parse --short refs/remotes/origin/topic HEAD
21f04a0
21f04a0
$ git switch -q --detach; git symbolic-ref -q --short HEAD || echo "detached: exit $?"
detached: exit 1
```

`gh` 2.102.0, the REST calls the command makes, against this repository:

```
$ gh api -X GET repos/CapeOfGoodCode/prepush-ci/pulls -f state=open -f head=CapeOfGoodCode:docs/244-release-without-main-wait -f per_page=100 --jq '.[]|{number,head:.head.ref}'
{"head":"docs/244-release-without-main-wait","number":245}
$ gh api -X GET repos/CapeOfGoodCode/prepush-ci/pulls -f state=open -f head=CapeOfGoodCode:no-such-branch --jq length
0
$ gh api -X GET repos/CapeOfGoodCode/prepush-ci/issues/243/comments -f per_page=100 -f page=1 --jq length   # 3
$ ... -f page=9 --jq length                                                                                 # 0
```

Python 3.13 `shlex.shlex(command, posix=True, punctuation_chars=True)` with `whitespace_split` yields `['git', 'commit', '-m', 'fix; git push']` for `git commit -m "fix; git push"` and `['cd', 'x', '&&', 'git', 'push', '-u', 'origin', 'b']` for `cd x && git push -u origin b`. A line break is whitespace to it, not a separator: the builder splits lines first.

## Decisions

- **A subcommand `hook post-push`, not `report --comment`.** The eleven requirements of `report` that speak of posting would have to be limited once more (#239 did it for `--markdown`); a command of its own leaves them alone, and the hook is one command that reads the payload and decides.
- **Only the skill proposes the hook; `init` does not write it.** It changes what an agent does in every session, so it asks for the user's yes, and `init` runs without asking. The SessionStart script is different: nothing visible depends on it.
- **A push is recognized from the command string, and confirmed by git.** Words are read like a shell reads them (quotes keep a word whole); a command is a push when some command of the line has `push` as its git subcommand (after `-C <path>` and `-c <k=v>`) and neither `--dry-run`/`-n` nor `--delete`/`-d`. Wrapped invocations (`sh -c "git push"`, an alias) are not recognized: no comment, nothing breaks. Then git decides whether it landed: `refs/remotes/origin/<branch>` must be `HEAD`. This also answers `git push || true` and a push that was refused. GitHub's own pull-request head lags a push by a moment, so it is not used for this.
- **Evidence is the run cache, not the command.** A command string cannot say whether the pre-push hook ran: `--no-verify` and `-c core.hooksPath=…` skip it, and the comment would show `passed` for a state nobody checked (the principle of `report`'s "A result never shows on a state it did not check"). The hook therefore posts only when a result ref for the tree of `HEAD` exists (`refs/prepush-ci/results/<tree>-*`), which only a passing check or a result reused from `origin` leaves. It does not recompute the whole key: that holds the preflight's output, and running the preflight in a `PostToolUse` hook is slow and has effects. Since the config is committed and the push needed a clean worktree, a result for the tree is a result for the committed `check`. Cost: with `cache = false` nothing is posted, and a `--no-verify` push of a tree that passed before still shows that earlier, true pass.
- **The trailer is whatever the pre-push hook demands.** The rules of the `pre-push-hook` capability (`trailer.key`, `legacy_keys`, the tip's and the worktree's config, case-insensitive) decide, so a repository with another key gets its comment.
- **The whole run is bounded at 15 seconds, and the settings carry a `timeout` of 30.** One run makes at least three requests of up to 30 seconds each; a proxy that never answers would otherwise make Claude Code kill the hook (exit not 0). The hook gives up itself, with one line; the setting's `timeout` is the backstop.
- **`git -C <path> push` is read as a push, but the hook looks at the worktree of `cwd`.** If that is another repository than the one pushed, `refs/remotes/origin/<branch>` is not `HEAD` and the hook does nothing; if it is a coincidence of the same sha the body names that sha, which is true.
- **Success is the event, not a field.** The hook is registered for `PostToolUse` only, so a command that failed never runs it; `tool_response` is not read.
- **The pull request is the open one whose head is the current branch in the repository of `origin`** (`GET /pulls?state=open&head=<owner>:<branch>`). A pull request from a fork is not found; nothing is posted.
- **The result is `passed`, the tree is `HEAD^{tree}`, the name is the default, there are no result files.** The pre-push hook let the push through, which is what the trailer commit promises; the text is the same as `report --markdown --result passed --tree <tree of HEAD>` prints, and so is read and checked the same way.
- **Credentials: the token if there is one, else none.** `GITHUB_TOKEN`, then `GH_TOKEN`; with neither the request goes without an `Authorization` header, because the cloud session's proxy adds the credentials. Elsewhere the API answers 401 and that is the one line.
- **A comment that already says the same is not written again.** The Markdown holds the sha and no time, so a push of the same commit sends no update.
- **Silent when there is nothing to show, one line when posting failed.** No push, no trailer, no pull request, no config, no repository on GitHub: nothing on any stream. A request that fails: one line on standard error naming the status and GitHub's message; the exit status is 0 in every case, so the agent's command is never blocked.
- **The hook command guards itself; the skill does not install the tool.** A missing `prepush-ci` would exit 127 after every Bash command, and the settings file is committed, so every teammate gets the hook (found by the attack, #247). The command is `d=$(uv tool dir --bin 2>/dev/null) && [ -n "$d" ] && PATH="$d:$PATH"; command -v prepush-ci >/dev/null 2>&1 && prepush-ci hook post-push || true`: it adds the directory only when `uv` succeeds and prints one (an empty entry in `PATH` is the current directory, where a cloned repository could plant a `prepush-ci`, and the exit status alone lets a `uv` that prints nothing give `PATH=":…"`), runs the hook only when the tool is found, and turns any other status into 0. Installing the tool from the skill would change the user's machine for a hook the user may not want; the hook does nothing until the user installs it (`uv tool install prepush-ci`), and the step says so.

## Open for the trial before 0.2.0

Whether the cloud proxy lets this command's own requests through to the comments API is not verified (the trial of #239 showed `POST /statuses` refused and comments through the agent's tools allowed), and neither is the payload a real `PostToolUse` hook receives. Before the release, in a Claude Code cloud session with the hook installed: push a trailer commit to a branch with a pull request and see the comment appear and update on a second push; push on a branch without a pull request and see nothing. The result goes into #246.
