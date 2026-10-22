## Context

`publish_pass` pushes the result ref to `origin` from the pre-push hook and, when git fails, prints `the result was not shared through origin, so another clone runs the check again: <git's stderr>`. Git's stderr is several lines and depends on the transport.

## Verified with the tools

git 2.39.5, a push of `refs/prepush-ci/results/t-k` with `--no-verify`:

```
$ git push <bare repo whose pre-receive hook refuses refs outside refs/heads/> +refs/prepush-ci/results/t-k:…
remote: refusing refs/prepush-ci/results/t-k
To <path>
 ! [remote rejected] refs/prepush-ci/results/t-k -> refs/prepush-ci/results/t-k (pre-receive hook declined)
error: failed to push some refs to '<path>'

$ git push http://127.0.0.1:18403/x.git +…            # a server that answers every request with 403
fatal: unable to access 'http://127.0.0.1:18403/x.git/': The requested URL returned error: 403

$ git push /nonexistent/x.git +…
fatal: '/nonexistent/x.git' does not appear to be a git repository
fatal: Could not read from remote repository.
```

The wording of the status differs by transport (`error: 403` from curl at the first request, `RPC failed; HTTP 403` from a later one in the trial of #268), so the status is read from either.

## Decisions

- **The cause is read from git's output, in three classes.** A status of 400 to 599 after `HTTP` or `error:`, read only from a line of git's output that does not start with `remote:` (that text is the remote author's, not the transport's), gives `origin refused the ref, HTTP <status>`; a `[remote rejected]` line gives `origin rejected the ref`; anything else gives `git could not push it`. Git's wording is not an interface, so the fallback claims nothing about why.
- **"The push goes on", not "went through".** The hook runs before git sends the branch, so the push has not happened yet when the warning prints; what is true is that the warning does not stop it.
- **Raw output behind `PREPUSH_CI_DEBUG`.** A non-empty value appends git's lines after the warning, unchanged. An environment variable, not a config key: it is for the person looking at one push, and a config key would be committed for everyone.
- **Only this warning.** The lookup failure, the cache write failure and the cleanup failure also carry a reason, but the issue and the trial concern the shared-ref push; they stay as they are.
