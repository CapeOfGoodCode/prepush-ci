# Tasks

## 1. Reading origin

- [ ] 1.1 Read the URL of `origin` through `git remote get-url origin` and accept `ssh.github.com` as GitHub's host in every form, in the choice of the API address as well; verify with specs, each pinning `GITHUB_API_URL` and `GITHUB_REPOSITORY` where `main` would otherwise pass: an `insteadOf` alias whose raw form names no repository, a `pushInsteadOf` to another owner that is ignored, `ssh://git@ssh.github.com:443/…`, an ssh host alias that is refused without `GITHUB_REPOSITORY` and used with it, and a lookalike host
- [ ] 1.2 Run `sh scripts/ci` and verify it passes
