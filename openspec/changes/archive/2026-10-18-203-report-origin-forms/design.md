# Design

## Context

Amends the `report` spec that #197 added; see its change for the command. This change only widens how the repository is read from `origin`.

## Decisions

- **Read `origin` with `git remote get-url origin`, not `git config --get remote.origin.url`.** The first applies `url.<base>.insteadOf`, so the URL is the one git fetches from; the second prints the alias. Cost: none visible, and a missing `origin` still reads as "no repository" (the command exits 2 then).
- **The fetch URL, not the push URL.** `url.<base>.pushInsteadOf` and `remote.origin.pushurl` rewrite only where git pushes; the repository whose commits the result belongs to is the one `origin` is fetched from. A user who pushes through a different address gets the repository of the fetch address.
- **`ssh.github.com` is GitHub; no other host is added.** It is GitHub's documented ssh endpoint over port 443, and the port is already accepted by the URL forms. The list stays two hosts rather than a pattern, so a lookalike (`ssh.github.com.example.test`) is not GitHub.
- **ssh host aliases stay out.** `git@github.com-work:acme/widgets.git` names a host only `~/.ssh/config` resolves; reading it with `ssh -G` would run a program for a convenience, and treating every unknown host as GitHub would send a token to whatever host the alias is. `GITHUB_REPOSITORY` already names the repository. Cost: those users set one variable.

## Run the tools

`git remote get-url` (git 2.39.5), with `url.https://github.com/.insteadOf gh:` and `url.git@github.com:.pushInsteadOf gh:`:

```
$ git remote add origin gh:acme/widgets
$ git config --get remote.origin.url
gh:acme/widgets
$ git remote get-url origin
https://github.com/acme/widgets
$ git remote get-url --push origin
git@github.com:acme/widgets
$ git remote remove origin; git remote get-url origin     # exit 2
error: No such remote 'origin'
$ git remote set-url origin ssh://git@ssh.github.com:443/acme/widgets.git
$ git remote get-url origin
ssh://git@ssh.github.com:443/acme/widgets.git
```

With `remote.origin.pushurl` set to another address, `git remote get-url origin` still prints the fetch URL.

## Risks / Trade-offs

- [A user who rewrites the fetch URL to a proxy of their own] → the host is no longer GitHub's, so the earlier rules apply: `GITHUB_API_URL` or `GITHUB_REPOSITORY` decides.
