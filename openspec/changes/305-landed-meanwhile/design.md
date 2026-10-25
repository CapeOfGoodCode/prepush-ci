## Decisions

- **Ask the branch, not the tip's identity.** After a refused push, "the tip changed" says only that someone else pushed. The question that decides the answer is whether the head is on the branch now. A head that is the tip or an ancestor of it is landed, whoever pushed it; this is the same test the spec already uses before the push ("Only a head on top of the tip lands"), so one rule serves both moments.
- **Fetch the new tip.** `ls-remote` gives only a sha, and a tip that another run pushed is not in the clone, so `land` fetches it before asking whether the head is an ancestor. A tip it cannot fetch, or a branch it cannot list, is not evidence of a landing: the refusal answer stands (exit 1), because the line must not claim what `land` did not see.
- **Success, not a new line.** The loser of the race gets the same `landed: <sha> already on <branch>` and exit 0 as a later run does. Workflows and scripts that read the status then see the same answer whenever the head is on the branch, whatever the timing.
- **No retry of the push.** A tip that does not contain the head is the existing moved branch; `land` never rebases, so a second push could not succeed.
