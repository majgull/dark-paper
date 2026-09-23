# Three runs a reader can open end to end

The run log proves the paper's numbers but does not let a person follow a run. This directory holds three runs of RQ3 round two, one per task class, exported so that a reader can see what a pass looks like from the task text to the verdict without reaching any private service.

| directory | task class | model | thinking budget | outcome |
|---|---|---|---|---|
| `hello-go-20260906-164057` | additive | Qwen 3.5 9B, served locally | low | pass, 3 of 3 checks |
| `rename-package-go-20260906-152559` | mechanical | GLM 5.3 Flash, at a provider | low | pass, 11 of 11 checks |
| `duration-python-20260906-143716` | repair | DeepSeek V4 Flash, at a provider | low | pass, 6 of 6 checks |

The three were chosen as the first passing run at the low budget in round two for one task of each class, taking three different models so that a local model and both provider models are represented. Nothing else was selected for.

Each directory holds:

- `task.md`: the issue body the run was opened with, which is the task text as given to the model, its class, and the limits it ran under.
- `task.toml`: the task's own definition in the bench repository at the check version the paper uses.
- `acceptance.sh`: the hidden check script the staging machine ran, at that same version. The model never sees this file.
- `oracle/`: the reference solution the checks were written against.
- `diff.patch` and `diff.stat`: what the run delivered, as the diff from the task's starting tree to the branch the run pushed.
- `transcript.txt`: the conversation the run uploaded to its own issue before its machine was destroyed, one JSON object per line, in the order the messages were sent.
- `comments.md`: the issue comments the runner and the staging machine wrote: liveness, done, staging result with the check lines, and the run-end verdict.
- `record.json`: the run's closing row from the committed run log snapshot `../evidence/ledger/2026-09-06.jsonl`.

Two substitutions were made and nothing else was edited: private network addresses in `task.md`, `comments.md` and `transcript.txt` are replaced by the role name `git-host`, and the two account-at-address strings the record carries for its power counters are replaced by `cpu-host` and `gpu-host` in `record.json`. The unedited row is the one in the snapshot, findable by its `run` value.

Produced by an export script on the runner host, which is not part of this repository because it reads private services, which reads the archived work organisation, the bench repository at the check tag and the run's issue, with the record added from the snapshot afterwards.
