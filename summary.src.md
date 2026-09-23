# A model alone in a throwaway machine: how its work was judged, what tools changed, and what more thinking bought

**The paper in five minutes.** A language model wrote code alone, in a virtual machine made for one task and deleted after it, judged by tests it never saw. {{num:tasks-in-the-set}} small tasks, {{num:models-in-the-rq3-round}} models, {{num:runs-in-the-rq2-set}} runs on the tools question and {{num:runs-in-the-rq3-round}} per round on the thinking question, run twice. One command, given at the end, re-derives every number here from the committed run log.

Language models wrote the code, ran the rounds and wrote the text; one person set the questions, took the decisions and read every draft (section 8 of the paper says who did what). Public domain. The paper: [paper.md](paper.md).

## The setup, as a picture

![Figure 1: one run, from task to verdict, and the boundary around it](figs/f1-system.svg)

- One virtual machine per task, deleted when the task ends; nobody watches, nobody approves a command.
- Tests the model never sees decide the result, in a second fresh machine.
- Limits frozen in a file before the round, its name and hash on every run's opening record.
- One append-only log, an opening and a closing row per run, committed with its hash.

## The tests were tested before they judged anything

![Figure 2: how the hidden tests were checked before they judged anything](figs/f2-tests.svg)

- Two solutions written by models not under test pass {{num:sonnet-solution-against-the-amended-judge-checks-passed}} and {{num:glm-solution-against-the-amended-judge-checks-passed}} of the {{num:hidden-checks-over-the-eight-tasks-under-the-amended-judge}} hidden tests; the one failure is a ruling against the solution, on an Arabic-Indic digit.
- {{num:mutants-written}} deliberately broken solutions all fail the tests; as first written they let {{num:mutants-the-suite-as-written-missed}} through, and two fixes closed both holes before any measurement.
- Scoring {{num:branches-scored-again-counted-in-the-ledger-rather-than-in-a-report}} older results again under the fixed tests changed {{num:verdicts-that-changed-when-41-branches-were-scored-again}} verdicts.

## A shell and file tools changed no verdict, and cost three and a half times the calls

![Figure 3: every run of the tools comparison, one mark each](figs/f3-rq2-outcome-grid.svg)

| | no tools | shell |
|---|---|---|
| runs solved, of {{num:runs-per-arm-in-rq2}} | {{num:pipeline-runs-solved-of-40}} | {{num:session-runs-solved-of-40}} |
| runs solved, of the runs that reached a test | {{num:pipeline-runs-solved-of-40}} of {{num:pipeline-runs-that-reached-a-check-of-40}} | {{num:session-runs-solved-of-40}} of {{num:session-runs-that-reached-a-check-of-40}} |
| tasks solved in at least one of five rounds, of {{num:tasks-in-the-set}} | {{num:pipeline-tasks-solved-in-at-least-one-round-of-8}} | {{num:session-tasks-solved-in-at-least-one-round-of-8}} |
| model calls, total | {{num:pipeline-model-calls-over-the-40-runs}} | {{num:session-model-calls-over-the-40-runs}} |

No paired test separates the arms. One model, eight tasks, five rounds per arm; the arms also differ in reasoning spent under the same cap, so this round cannot say which a verdict follows.

## Every model solved more with a thinking budget, the middle budget was cheaper than none, and a model with no budget repeats itself

![Figure 4: in round one, every model solved more tasks with a thinking budget than without one](figs/f4-rq3-solved.svg)

- Solved runs: {{num:tasks-solved-at-think-none-of-48}}, {{num:tasks-solved-at-think-low-of-48}} and {{num:tasks-solved-at-think-medium-of-48}} of {{num:runs-per-think-level}} at no reasoning, the middle budget and the largest; six of six models improved from none to the largest (sign test p = {{num:sign-test-p-six-of-six-moving-one-way}}).
- The middle budget cost less wall time than no reasoning in {{num:families-whose-low-costs-less-wall-time-than-none-of-six}} of the six models.
- The mechanism, from the record: with no reasoning budget, {{num:round-two-think-none-per-cent-of-those-calls-that-repeated-a-reply}} per cent of calls repeated a reply the run had already sent, against {{num:round-two-think-medium-per-cent-of-those-calls-that-repeated-a-reply}} per cent at the largest budget.

For four of the six models the chat template moved with the budget, so two things moved at once. Run a second time, the direction held and the sharpness did not (p = {{num:round-two-exact-two-sided-p-3-of-11-discordant-pairs}} on the differing pairs).

## What is not claimed, and what comes next

- Nothing here generalises to other kinds of task, to larger repositories, or to models outside the six named.
- Two rounds are two observations: counts, not a variance, an interval or an effect size.
- Not a security result: isolation is the premise, checked once from inside a live machine, never tested.
- Next round, in order: the no-reasoning cells through the same deployment as the other budgets; sampling parameters and a timestamp per call in every record; more rounds per cell; a tools comparison that holds reasoning spent level; then the two designed questions, isolation against approval per command, and the shape of the task text.

## How this was made

By one person and several language models, and the split is stated so a reader can weigh it. majgull chose the questions, the task classes, the models, the limits and the licence, took the decisions the paper records as decisions, and reviewed every draft with inline comments. Claude, running as a coding agent on his machine, coordinated: it planned and launched every batch, wrote the appendix and figure scripts, and wrote the paper. Delegated sessions of DeepSeek, GLM and Claude Sonnet models wrote the runner and the bench, the tasks with their gold solutions and mutants, and reviewed the tree. No line of code or prose in this repository was typed by a person. Section 8 of the paper says the same in more detail, and says why the repository is dedicated to the public domain rather than licensed.

The whole repository, code, paper and evidence, is dedicated to the public domain under CC0; nothing asks for attribution, and a citation is welcome.

## Check it yourself

With Python, git, jq and pytest, from the root of this repository and of the tool's:

```
python3 tools/fetch-evidence.py                # the run log, from the dataset, hashes checked
python3 appendix.py --check                    # every number, re-derived
cd ../dark/runner && python3 -m pytest -q tests  # the pipeline
cd ../bench && python3 tools/check_tasks.py    # the task set
```
