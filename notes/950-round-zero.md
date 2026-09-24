# Round zero, 2026-09-05: how much of a verdict comes from the hidden tests?

## Terms

- **operator**: the person who owns the machine and the run.
- **runner**: the pipeline that runs one task to a verdict.

Every table of pass counts is a table of judge verdicts. A judge that has changed since a round ran shifts every row of that round, and running the round again does not show it: the new run is judged by the new judge. Round zero asks the question directly. Take branches an earlier round already delivered, judge them again with the acceptance as it stands now, and count the verdicts that change.

## What was judged, and what was not

operator's decision was to copy, never to unarchive. The delivered branches live in two archive organisations, whose repositories are read-only in Gitea, and judging writes a branch. Each branch was mirrored into a fresh organisation and judged there. **The archive was only ever read.** `actions/950-round-zero.py` is the script; the runs are in the ledger under shifts `20260905-070834-round-zero` and `20260905-073355-round-zero`, arm `rejudge-<the original arm>`.

The archive holds 457 delivered branches, which is eight to eleven hours of staging machines and does not fit a night. Three filters make it a measurement rather than an endurance test.

- Only branches whose `run.end` recorded **no test version**. The runner did not record which acceptance judged a run until 2026-09-04, so 583 of the 871 delivered branches do not say. Those are the only ones where a changed verdict could mean the judge moved rather than the branch. A branch already stamped `b0d3d22` would be judged by the same version it was judged by.
- Only the **eight tasks** the RQ2 and RQ3 tables rest on, so the number is about the figures being published rather than about the archive at large.
- A **fixed-seed sample spread evenly over the outcomes**, because a flip runs both ways and a sample of passes could only ever show one of them.

Structural failures were excluded: they are a fault in the harness, they are excluded from every rate, and their branches carry no verdict to change.

## The result

**45 branches attempted, 41 judged, 0 flipped.**

| | count |
|---|---|
| branches judged | 41 |
| originally `pass`, still `pass` | 21 |
| originally `fail:capability`, still `fail:capability` | 20 |
| **verdicts that changed** | **0** |
| judged branches whose check counts also matched exactly | **41 of 41** |

Not one verdict moved, and not one branch's count of passed checks moved either: every re-judged branch scored the same checks out of the same total as when it was delivered. The 41 span eight tasks, ten model tiers and twenty different arms, and the oldest were delivered on 2026-09-02.

## What the four unjudged branches were

Four branches of `t-hello-go` in the first archive organisation came back `COPY FAILED` with `src refspec ... does not match any`. The cause was a defect in the script rather than in the archive: it cached each mirror clone under the repository's name, and `t-hello-go` exists in both archive organisations, so the second organisation's repository was handed the first one's mirror, which does not hold its branches. Fixed by keying the cache on the organisation as well, and five `hello-go` branches were then judged with the same result: 0 flips.

## What this says, and what it does not

For these eight tasks, on this sample, **the judge contributes nothing to the verdicts of earlier rounds**. A pass counted in a September table is still a pass under today's acceptance, and a capability failure is still a capability failure, check for check.

It does not say the acceptance is correct. That is the other half of L1, and it found two clauses no hidden check enforces (`reports/950-l1-adjudication.md`). It says the acceptance is **stable**: whatever it was measuring in September, it is measuring the same thing now, so tables from different nights can be read against each other.

It is a sample of 41 out of 583 eligible branches, drawn with seed 950. A flip rate of 0 in 41 is consistent with a true rate under about 7 in 100 at the usual confidence; it is not consistent with the tables being materially wrong. The remaining 542 can be judged the same way whenever a night has the machine time, and the script takes `--sample` for exactly that.
