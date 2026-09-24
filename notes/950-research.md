# Research design: the questions, what is held fixed, what is varied, and what it costs

## Terms

- **hub**: the coordinating session that plans and reviews.
- **bouncer**: the agent harness with guards that a session runs under.
- **operator**: the person who owns the machine and the run.
- **pi**: the plain agent loop the session arm runs, with no guards.
- **bench**: the measuring instrument, which runs the same runner over isolated Git organisations.
- **runner**: the pipeline that runs one task to a verdict.

Written 2026-09-04 15:04 CEST by the hub, after the overnight run of 2026-09-03/04. Amended 2026-09-05 after the second overnight run: the envelope rule (one cap for both arms) was wrong, see RQ2 and the registry; status lines updated per question. This is the research document. It states the questions, the experimental setup that answers each one, the factors that must not move, and the real-world limits the design has to fit. It does not log what a session did on a given night, and it does not carry the decision menus; those live in the files below. When a design choice here changes, this file changes; when a run happens, the log changes.

## Why this study exists, and where it goes

Written down 2026-09-05 from operator, so that the reason is in the document and not in a conversation. Two things live in `dark`. The **pipeline** works a task unattended inside a throwaway virtual machine: a model pushes a branch, and a hidden judge decides; containment is the VM and the judge, not per-call guards. The **bench** is the pipeline's measuring instrument: the same runners, the same VMs, isolated Gitea organisations born and archived per experiment, so that a new model's capability can be tested quickly and rigorously, and what is learned there (which tier for which class of task, under which envelope, at what cost) feeds the pipeline's own choices. The research questions ask whether the pipeline's approach has the benefit it was built for, against a plain agent session under the same containment.

The arc past RQ4. Today the capable and expensive model, the hub that plans and reviews, works through bouncer with guards on the real host, and the guards are hard to balance (too strict and the agent gives up, too loose and it works around them). The mechanism that runs a session arm, a reference writer or a reviewer inside the throwaway VM (build item 5) is the same mechanism that can carry that hub role into a sandboxed but relaxed environment: everything inside the VM allowed, nothing outside reachable. Bouncer then shrinks to a thin agent outside the sandbox whose job is the person, not the work: understand needs and requirements, guide, answer questions, and coordinate the sandboxed roles. The arms of this study are points on one axis of tool access, from the pipeline's protocol loop with no tools, through the plain agent loop (pi) in the middle, to an agent loop with more tools or a whole hub role at the far end, and the stack lets a new point be added as one more arm without much effort. Every question here is read with that in mind: not only whether the pipeline beats a session, but what each step of tool access costs and buys under containment by VM instead of by guard.

## Which file is which

| kind | file | what it holds |
| --- | --- | --- |
| research design | `docs/950-research.md` (this file) | questions, setup, fixed and varied factors, constraints, status per question |
| decision menu | `reports/950-feasibility.md` | the options considered and the defaults chosen, with the reviewers' gaps in `reports/950-gaps/` |
| running log | `reports/950-rigor-plan.md` | one entry per step, written by the working session before the next step, with commit and shift ids |
| run reports | `reports/950-overnight-report.md`, `reports/950-chain.md` | what one night or one round did, numbers from the ledger |
| result tables | `reports/950-l2-tables.md`, `reports/950-l1-adjudication.md` | rendered tables, each number traceable to a ledger row or a trail |
| orders to sessions | `briefs/950-*.md` | what a delegated session is told to do and what counts as done |
| evidence store | `evidence/950/` | the raw records every table and claim rests on: ledger snapshots, exported session transcripts and full audit trails, launcher logs, each named with its sha256 by the report that cites it |

## The system in plain words

- **Pipeline**: an unattended run. A model gets a task text inside a throwaway virtual machine, works, pushes a branch, and a hidden test script judges the branch. Nobody watches.
- **Session**: the same model in a free agent loop (pi) with tools, inside the same throwaway VM, handing in whatever it ends with. Unattended too. Bouncer, the operator harness with guards, cells and audit, is not part of either arm: guards refuse commands and change what the model does next, and that makes a run depend on policy rather than on the model. Bouncer launches lanes and keeps the trail; it is never the thing measured.
- **Tier**: one model at one place, for example `my/qwen-3.6-35b` on the local host or `deepseek-v4-flash:cloud`.
- **Think level**: a budget of visible thinking characters per model call, cut live by the runner, the same scale for every tier: none 0, low 8000, medium 32000, high 64000. Claude through its proxy ignores the level and reports no token usage.
- **Envelope**: the limits one run is cut off at: seconds, reasoning characters, and a model-call ceiling. The runner can take it from a fixed file (hard) or compute it from the tier's recent passes in the ledger (soft). A model call is not the same size on every arm: the pipeline answers a task in a median of one call, a session spends one call per tool round-trip and a median of seven, so the seconds cap is the limit that compares arms and the call ceiling is only a stop for a runaway, set high enough that it bound no run in the last measured set.
- **Admission**: the rule that picks which tier tries a task first, from past pass rates. **Escalation**: one retry on the next tier after a failure.
- **Judge**: the hidden test script for a task, at a tagged version. **Reference**: a solution written from the task text alone by a model that is not under test, used to check the judge.
- **Ledger**: the append-only record on the runner host; every number in every table comes from it or from a session trail.

## The questions, in the order they must be answered

Each question is answered by one launch on its own, with nothing else running on the host or the cloud account. The order is by dependency: a later question's numbers are only readable once the earlier one holds.

### RQ1. How much of a verdict is the judge rather than the work?

**Why first.** Every later table is a count of judge verdicts. A judge that is wrong on two tasks shifts every row by two, for every model, and repeating runs does not show it.

**Setup.** Two parts. (a) Two references per task, from different model families (sonnet, deepseek), each written from the specification alone; every hidden check runs against both; every disagreement gets one row with the ruling (specification amended, check amended, reference amended) and the sentence of the specification that decides it, ruled by a reader, never by vote. Plus mutation both directions: per specification clause one deliberately violating variant that must fail, and the set of correct variants that must pass. (b) Round zero: the branches already delivered in earlier rounds are judged again with the tagged judge; the number of verdicts that flip is the judge's contribution to any table built before the tag.

**Fixed.** Specification text, judge version, task starting tree. **Varied.** Nothing; this measures the instrument.

**Output.** One table per task: checks, disagreements by ruling, mutants caught, correct variants accepted, judge tag after. One line for round zero: branches re-judged, flips, listed.

**Status 2026-09-05.** Done for the eight tasks RQ2 and RQ3 use, and for the six chain tasks. Chain tasks: 174 checks, both references pass all, 23 mutants. Eight tasks: 61 checks, references by sonnet and glm (glm rather than deepseek, because deepseek is the model under test in RQ2), 61 of 61 and 60 of 61, the one disagreement ruled against the reference on the specification text; 29 mutants, 27 caught, 2 missed (`reports/950-l1-adjudication.md`). Round zero done by copy, never unarchive: 41 branches re-judged, 0 flips, same check counts (`reports/950-round-zero.md`). Two check amendments followed from the specification text and are applied, judge tag `acceptance-v4` (bench 7e4dec9, tests version 5d6f78a): the two mechanical tasks (`split-module-python`, `rename-package-go`) say the moved code is unchanged, and a check now reads it, which is what let 2 mutants through; `duration-python` says ASCII digits and its hidden reject list now holds the empty string. The six reference branches re-run under v4 on 2026-09-05 (shift `20260905-143140-rq1-smoke-v4`): five pass, the sixth is the ruled disagreement (sonnet's reference accepts an Arabic-Indic digit). The 14 remaining single tasks have no ground truth; nothing planned uses them.

### RQ2. Does the harness change the outcome? Pipeline versus session, same model, same limits.

**Setup.** One model, deepseek-v4-flash. Both arms run in the same VM image on the same starting tree and read the same frozen envelope: seconds, reasoning characters, think level, and a call ceiling that binds neither arm. The seconds cap is the shared limit; the call ceiling is a runaway stop only, set from measurement (the loose set of 2026-09-05 saw session medians of 7 calls under a ceiling of 24 and no run cut off), and a run that hits it is reported in its own column. The task set is the eight tasks chosen for RQ3, so the two questions read against one judge tag. The session arm is a plain pi session, no bouncer, no guards; its own session record supplies the tool-call count and the provider's token usage. No escalation, no retry on either side. Five rounds per arm on the same task set, launched alternating pipeline, session, pipeline, session, so anything that drifts during the night hits both arms alike. Each round is verified against ledger, digest and Gitea before it counts.

**Fixed.** Model, task set, judge tag, envelope, think level, host load (nothing else running), the day's call quota untouched by anything else. **Varied.** The arm only.

**Output.** One paired table: per task, passes out of five for each arm; a last line with the count of tasks only the pipeline ever passed and only the session ever passed. A second line for cost: median seconds per task per arm, and provider tokens where the arm records them; the session arm's tokens are NOT MEASURED unless its trail carries usage.

**Extension.** claude-sonnet-5 both ways, two rounds, only after the deepseek pair is clean. It costs money and inherits every flaw above if run earlier. Its think level cannot be set through the proxy, so that cell is reported as "level uncontrolled".

**Status 2026-09-05.** Run once as designed on the night of 2026-09-04/05 (`reports/950-overnight-2-report.md`, `reports/950-rq2-tables.md`): five alternating rounds per arm, frozen file, session arm as pi in the VM, 80 runs, 0 structural failures, 0 ledger mismatches. The result is that the design's envelope rule was wrong: the one call cap of 6 pinned for both arms cut the session arm off in 16 of its 40 runs and the pipeline in 3, so set A (pipeline 31 of 40, session 20 of 40) measures the cap, not the harness. Among runs that finished on their own the arms passed at 31 of 37 and 20 of 24. A second set with the ceiling raised to 24 and nothing else changed, two rounds per arm, saw no run cut off, pipeline 14 of 16 and session 15 of 16. That is the shape the setup above now specifies. The five-round run under it has since run and is reported in `reports/950-rq2-v4.md` with tables in `reports/950-rq2-tables-v4.md`: RQ2 now has a quotable answer, and it is that giving the model tools and a loop solved nothing the tool-less protocol could not, at six times the calls. The 2026-09-04 rounds (session under bouncer, no envelope) stay discarded. Sonnet extension not run.

**Deferred, see RQ4.** The guard layer's own cost is a question of its own and waits for the baseline.

### RQ3. Can local models do the work, at what think level, and at what energy, against the cheap cloud tiers under the same limits?

**Setup.** Pipeline only; no session on local models, because a session's context and wall time are not affordable locally. Every cell is one tier at one think level, with the same envelope, no escalation, no retry: one tier does the whole task or fails. Eight tasks from the 22, chosen by class (about three additive, two mechanical, three repair) and by spread (two that no local tier passed, two that every tier passed), three rounds per cell. Host alone; idle baseline (five minutes, no VM) before each local round.

| tier | none | low | medium |
| --- | --- | --- | --- |
| qwen-3.5-9b | yes | yes | yes |
| qwen-3.6-27b | yes | yes | yes |
| qwen-3.8-27b | yes | yes | yes |
| qwen-3.6-35b | yes | yes | yes |
| deepseek-v4-flash | yes | yes | yes |
| glm-5.3-flash | yes | yes | yes |

Eighteen cells (the 3.8-27b none preset answers, checked 2026-09-05). High is excluded: 64,000 characters of thinking per call does not fit the seconds cap on local hardware and would produce only budget failures.

**Fixed.** Task set, judge tag, envelope, response length, model presets and quantisation, host alone. **Varied.** Tier and think level.

**Output.** One table, one row per cell, no footnotes: solved of 24, capability fails, budget fails, Wh per solved (local rows, gross and net of idle, labelled uncalibrated), cents per solved (cloud rows), median seconds. Appendix: task by cell, passes out of three.

**Status 2026-09-05.** Unrun. The only local numbers (2026-09-04, 35b and 9b at level none, 22 tasks) predate both the frozen envelope and the reasoning-budget retune of 2026-09-03 19:32 UTC and do not count. The 27b presets answer on the router (all six, `reports/950-prep-b.md`). The envelope for every cell is the RQ2 shape: seconds cap shared, call ceiling non-binding (`frozen/rq3-2026-09-05.toml`; copied here at `study-inputs/frozen/rq3-2026-09-05.toml`). Plan for the weekend of 2026-09-05, decided with operator: a two-cell smoke the night of the 5th, then one round of all eighteen cells on the 6th, cloud cells first and local cells during the day (the host may run in daytime now); rounds two and three on the following nights. One round per cell is the early result and is reported as such.

### RQ4, deferred until RQ2 holds. Does isolation replace guards?

**Why it is on the list.** The pipeline came out of a problem in using bouncer: the guards are hard to balance. Too strict and the agent gives up, so there are no unattended runs; too loose and it works around the guard, for example by taking over the shell tool it was given, and does things nobody wanted. The pipeline's answer is to contain by a throwaway VM and a hidden judge instead of by per-call policy, so nothing the model does inside can matter outside. Whether that trade actually holds is a measurable question, and it needs RQ2's clean baseline first.

**Setup, when it is run.** Same model, same VM, same tasks and envelope, three arms: pi plain (the RQ2 session arm), pi under bouncer at the everyday guard profile, pi under bouncer at a strict profile. Per run, from the trail: refusals, runs that ended without a delivery (gave up), and commands that reached for something a guard had refused by another path (workaround attempts, counted by a reader from the trail against a written list). **Varied.** The guard profile only.

**Output.** One table, one row per profile: solved, gave up, refusals, workaround attempts, median seconds. The question it answers: does the VM give the same containment for less cost in outcomes than the guards do.

### RQ5, added 2026-09-05. Does the shape of the specification change the outcome? Plain task text against a constitution, a spec and a feature file.

**Why it is on the list.** The arms so far vary who does the work and how much it may touch: the model, its think level, its energy, its tools. They all receive the task the same way, as a paragraph of plain text with the visible tests. The practice now called spec-driven development gives an agent more than that: a project constitution of numbered rules in EARS form (ubiquitous, WHEN, WHILE, IF/THEN) under RFC 2119 words, a spec per feature with numbered requirements and a schema-checked header, a Gherkin feature file that names the scenario each requirement is verified by, and a rule that the agent cites the constitution rule that constrained a decision. operator's draft of that layer is kept privately (constitution, spec guide, one worked example). Whether that structure changes what a model solves, or only what it costs, is a measurable question on a new axis: the specification, with everything else held fixed. It is also the layer the pipeline would adopt for real work if it pays, so the answer feeds the pipeline directly.

**Setup.** One model (deepseek-v4-flash, the RQ2 model), the pipeline arm (the harness RQ2 found no worse than the session arm), the same eight tasks, the same VM image, the same frozen envelope and judge tag as RQ2 and RQ3. Two arms that differ only in what the model is given:

- **plain**: the task text and visible tests, as every arm so far.
- **spec**: the same, preceded by a constitution for the task set (one file, the rules that apply to all eight tasks: language, no new files beyond those named, tests stay green, no secrets in output), a spec for the task (numbered requirements R-n in EARS form, restating the task text and nothing more, with the traceability table left for the model to fill), and a feature file naming the scenarios. The model is told to cite rule IDs in its commit message and to fill the traceability table. Nothing else in the prompt changes.

The specs are authored inputs, written from the task text by the hub and checked against the task text and the hidden acceptance the way the RQ1 references were adjudicated: a spec may not state a requirement the task text does not, and may not omit one the judge checks. They live in the bench outside `tasks/` (`specs/<task>/`), so the judge's tests version does not move. A lint over the spec files (header schema, EARS form, every R-n named in the feature file) runs as a visible check on the spec arm and its result is a recorded output, never part of the verdict.

**Varied.** The specification layer only. **Held.** Model, harness, envelope, judge, tasks, VM, adaptation off. **Read from the ledger.** Solved per task and per arm, paired as in RQ2; calls, seconds, tokens in and out, reasoning characters; on the spec arm also whether the traceability table was filled and whether rule IDs appear in the commit message, both read from the delivered branch by a script, as measured outputs. Five rounds per arm, alternating, each verified before it counts.

**Output.** The RQ2 paired table with the two arms, plus two columns for the spec arm's self-reported traceability and rule citations against the judge's verdict on the same run. The question it answers: does telling a model more, in a disciplined form, get more solved on the same limits, and what does the discipline cost. A second question it prepares but does not answer: the same two arms with other agents (Claude Code, Codex, pi) as the executor, on the tool-access axis, once their providers are reachable from inside the VM.

**Status 2026-09-05.** Designed, unrun. Build before launch: the `specs/<task>/` layout in the bench with the eight specs, the constitution and eight feature files, and the lint; a stager switch on the runner that puts the spec files in the model's prompt when the arm asks for it, and a registry entry for the two arms. Size: one delegated session for the runner switch and the lint, one hub window to write and adjudicate the eight specs, one run of about two and a half hours on the RQ2 pattern, one hub window to verify and report. It runs after RQ3's first round and the early-results report, and before RQ3's later rounds only if the runner host is otherwise idle, because it needs no local model.

### Not asked now

Whether the admission table transfers from single tasks to chains, and how escalation should pick its tier. Both are tuning questions for the tool, not measurement questions, and they cannot be answered until RQ1 to RQ3 hold.

## The fixed-factor registry

Everything the runner reads from the ledger or the clock before a run starts, and what the study does with it. This list is taken from the runner's source (`budgets.toml`, `dark/budget.py`), not from a design document; the overnight run missed the envelope because no such list existed.

| factor | what moves it normally | in the study |
| --- | --- | --- |
| envelope (seconds, reasoning chars, call ceiling) | soft mode recomputes from recent passes | pinned in a frozen file, recorded on every `run.start`; the seconds cap is the limit shared across arms, the call ceiling is set so that it bound no run in the last measured set (a call is one solution on the pipeline and one tool round-trip on a session) |
| think level | class default | pinned per cell, same scale on local and cloud |
| admission | pass rates in the ledger | off; the tier is named on the command line |
| escalation, retry | one retry on the next tier | off |
| judge | test version in the bench | tagged, tag recorded per run |
| task set | task list | committed list per question |
| host load | other shifts, operator's own GPU use | host alone, overlap of run windows printed from the ledger |
| cloud call quota | shared by every shift on the account | sized to fit with margin; nothing else draws on it that night |
| response length | `max_tokens` default | left at the default, recorded |

## Evidence: where the source of every number lives

Added 2026-09-05 after operator's rule: nothing a report relies on may exist only inside a bouncer session, a worktree, a scratchpad or `/tmp`. The failure this closes is real: the two reference-writer sessions of 2026-09-05 (`refw2-sonnet`, `refw2-glm`) already have empty transcripts, so the process that produced the L1 references survives only as the branches they pushed and the adjudication report. A study keeps its raw data, its lab notebook and its analysis code so that a reader can re-derive every table; here that is:

| kind | produced where | kept where | how a report cites it |
| --- | --- | --- | --- |
| ledger | the runner host's ledger directory, append-only JSONL | `evidence/950/ledger/<date>.jsonl`, one snapshot per night, copied by the hub before the morning report; a new snapshot must contain the previous one as a prefix | shift id and run id; the report names the snapshot file and its sha256 |
| session transcript and full audit trail | bouncer, per session, on the hub | `evidence/950/sessions/<name>.transcript.md` and `<name>.audit.txt`, exported by the hub in its verification step, before the session's worktree is dropped; audit exported whole, never the default tail (the 2026-09-04 erratum came from that tail) | session name, model, brief file, export sha256 |
| launcher and smoke logs | the hub's scratch directory | `evidence/950/launch/<name>` copied the same morning | file name and sha256 |
| delivered branches | Gitea, moved to a read-only archive organisation after a set | stay on Gitea; the ledger's `run.end` names branch and commit | branch and commit sha from the ledger |
| judge | bench repository | tagged; the tag's commit sha is the `tests_version` on every `run.end` | tag and sha |
| references and mutants | bench repository and branches | committed; a reference is a branch named in the adjudication report | branch, commit, report |
| rendered tables | `tools/report.py` in the bench repository, over a ledger snapshot | the report names the renderer's commit and the snapshot | commit and file |

Rules that follow. A reviewer or judge that runs as a bouncer session is cited by its session name, and its export is the hub's job at verification time, not the delegate's. A report is not committed until every file it cites is in the store; `hub-evidence` (in `bin/`) does the export and prints the sha256 lines the report pastes. Where the trail is already gone the report says TRAIL LOST and lists what survives; nothing is reconstructed. Working copies (a delegate's clone, a scratchpad, a worktree) are never evidence. The store is in this repository so that a commit is the retention policy and the history is the audit of the store itself.

## Hard constraints the design fits inside

- **Cloud daily window**: the runner holds each cloud provider to a window per local calendar day in `budgets.toml` (calls and tokens), a placeholder for the subscription's real bound, which is not measured. Admission reserves the worst case in front of every run, calls times context plus reply, 983040 tokens for a 24-call class, so a run parks when less than that is left however cheap it really is. Measured 2026-09-05: one RQ2 round pair on deepseek is about 70 calls and 470k tokens; the day's twelve overnight rounds plus round zero spent 3.13M tokens by 15:50, which parked the afternoon relaunch under the old 4M window. On 2026-09-05 at 16:10 operator removed every budget for the weekend (runner a8f18a1: windows and watts set to values nothing reaches; the reservation code stays and never binds). A provider refusal ends a run structurally and the ledger shows it. The claude proxy reports no usage, so a sonnet run would be charged its reservation; sonnet is held this weekend on operator's instruction after the claude plan's session limit was hit by the day's delegated sessions.
- **Local host time**: a 22-task local round took about 110 minutes; the RQ3 matrix at eight tasks and three rounds is about three nights. The host is operator's daytime machine; local energy rounds were night-only until 2026-09-05, when operator allowed daytime runs for the weekend.
- **Energy**: RAPL and GPU counters, host-wide, uncalibrated, no wall meter. Cloud rows never carry Wh. Local Wh is published gross and net of a fresh idle baseline (2026-09-04: 33.4 W CPU package, 21.5 W across two GPUs) and labelled uncalibrated until a wall-meter cross-check exists.
- **Claude proxy**: ignores the think level, reports no tokens. Sonnet cells carry "level uncontrolled" and tokens NOT MEASURED.
- **Money**: only the sonnet extension costs more than cents; two rounds, stop if one round exceeds twice the first deepseek round's list price.
- **Archive**: delivered branches are archived read-only by design; round zero must copy, not unarchive.

## What must be built before the next launch

Done on 2026-09-05 (runner `4fb2c2c`, `1f3208a`, `50ec392`; bench `0144754` to `4166551`): frozen mode with the file's name and hash on every `run.start`; the off switch for admission, escalation and retry (`--no-adapt`); the session arm as pi inside the VM, calling from the runner host and counting its own calls; RQ1 part (a) and round zero for the eight tasks; the eight-task list; the cut-off column in every round table; the 23-against-22 row count explained (one voided run). Still open:

1. A frozen file for RQ2 with the seconds cap shared and the call ceiling at 24, and the same shape for RQ3.
2. The two RQ1 check amendments above, then the judge retagged; mutants moved out of the directory that defines the test version, so that pulling them does not move the version string with no check changing.
3. The launch script names the arm once per set, not per round, so the ledger reads two arms and not ten.
4. The check that the three 27b presets load on the router. Done 2026-09-05 by the hub: all six 27b presets answer (`reports/950-prep-b.md`), so RQ3 is eighteen cells.
5. Every model that judges, writes a reference or reviews runs inside the throwaway VM with no bouncer, the way the session arm does (operator, 2026-09-05: zero dependency on the hub, reproducible from image, brief, model and envelope). Two parts. (a) The session arm keeps pi's JSON stream instead of only counting it: the stream, the brief and the task record are pushed as files to a records repository on Gitea, and `run.end` carries their path and sha256. (b) A review mode of the same executor: the input is a brief file and a set of files to read, the deliverable is a report file pushed the same way, so adjudication, spec review and second opinions become ledger rows with kept transcripts. References need no new mode: a reference is a session-arm run on a tier not under test, with the specification as its only input, and the stream kept.
6. One entry point over a written manifest, `dark bench <manifest>`, with five selectable phases: bootstrap (the rebirth of the organisations and checkouts), smoke (the manifest's subset through the same path, acceptance read from the ledger), run, report, archive into a results repository that carries the manifest, the ledger snapshot, the report and a script that re-derives the tables from the snapshot. Design in `docs/950-bench-e2e.md` (operator, 2026-09-05: a person runs a quick round, writes their task set, says go, and gets a clean report and the raw data on Gitea to audit).

## Size and order

RQ1 done. Remaining, in the order decided 2026-09-05 for the weekend: the RQ2 five-round set on deepseek (relaunched 15:54 after the window incident, one hub window to verify), the RQ3 two-cell smoke as soon as the runner is idle (operator allows daytime runs), one round of all eighteen RQ3 cells the same night, the early-results report, then RQ3 rounds two and three on the following nights unattended, with RQ5 (added 2026-09-05, one delegated session to build, one hub window for the specs, one run of about two and a half hours) slotted in wherever the runner host is idle and needs no local model. Build item 5 lands between the deepseek and sonnet sets; item 6 is dispatched in parallel and drives the later rounds. operator's decisions so far: the envelope shape (seconds cap shared, call ceiling non-binding), one round per cell as the early RQ3 result, daytime local runs, no budgets, sonnet held until after the weekend (claude session limit, 2026-09-05 18:10).
