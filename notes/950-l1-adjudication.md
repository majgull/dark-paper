# Ground truth for the obs chain's hidden tests

## Terms

- **hub**: the coordinating session that plans and reviews.
- **operator**: the person who owns the machine and the run.
- **bench**: the measuring instrument, which runs the same runner over isolated Git organisations.
- **runner**: the pipeline that runs one task to a verdict.
- **factory**: an earlier name for the pipeline, kept in session names and paths below.

Written 2026-09-04 01:50 by the hub session `factory-rigor-plan`, from the runs recorded below. L1 is the second rung of the validation ladder (feasibility D29): before any number is collected from the tests, show that the tests measure the specification rather than one solution's habits.

## What the words mean here

A **task** is one ticket with a written specification. Its **oracle** is the reference solution the bench ships, which exists only to validate the tests. Its **hidden acceptance** is the set of checks that judge a run; it is not in the tree a model works in. A **second reference** is a solution to the same specification written by a different model that never saw the oracle, the acceptance, or the first reference. A **mutant** is the oracle with one clause of the specification broken on purpose. A **disagreement** is a check that fails on a solution the specification says is correct, or passes one it says is wrong.

## The two directions, and what each answered

**Direction one: does the acceptance reject a correct solution?** Two second references were written from the specification text alone, one per model, each in a workspace holding the task's starting tree and `SPEC.md` and nothing else (`tools/refwork.py` in the bench repository). Both were then judged by the same hidden acceptance the runner uses, rebuilt as a git repository so the history-dependent checks ran too (`tools/refcheck.py` in the bench repository).

| reference | model | tasks | checks run | checks passed | disagreements |
|---|---|---|---|---|---|
| `ref-dsf` | deepseek-v4-flash:cloud, session `t950-l1-reference-dsf` | 6 | 174 | 174 | 0 |
| `ref-sonnet` | claude-sonnet-5, session `t950-l1-reference-sonnet` | 6 | 174 | 174 | 0 |

Per task, both references: obs-01-parse 11 of 11, obs-02-count 24 of 24, obs-03-package 26 of 26, obs-04-tzfix 25 of 25, obs-05-report 37 of 37, obs-06-typehints 51 of 51, and `.factory/verify.sh` green in every tree. **No check failed on either reference, so there is no adjudication row of the first kind.** The table has none because none was earned, not because none was looked for: the run is reproducible with the two working copies kept as the session's scratchpad trees `ref-dsf` and `ref-sonnet` and the JSON results beside them.

**Direction two: does the acceptance accept a wrong solution?** 23 mutants, each the oracle with one named clause broken and a `WHY` file quoting the sentence it violates (`tasks/<id>/mutants/` in the bench repository, driver `tools/mutants.py`). A mutant that only `visible-tests` catches counts as missed: that check runs the tests in the tree, which under a mutant are the oracle's own, and a model writes its own.

| task | mutants | caught by a hidden check | missed |
|---|---|---|---|
| obs-01-parse | 5 | 5 | 0 |
| obs-02-count | 6 | 6 | 0 |
| obs-03-package | 3 | 3 | 0 |
| obs-04-tzfix | 2 | 2 | 0 |
| obs-05-report | 5 | 5 | 0 |
| obs-06-typehints | 2 | 2 | 0 |
| total | 23 | 23 | 0 |

The first run of that set found 23 of 23 caught only after one amendment, described next.

## The one check that was amended, and why

| task | check | reference outcome | ruling | the sentence that decides it |
|---|---|---|---|---|
| obs-01-parse | `parse-crlf` (new) | both references pass it | **check amended** | "A `\r` right before the `\n` is dropped (CRLF input parses like LF input)." |

Before the amendment, two clauses of obs-01 were caught by nothing the acceptance owned. The mutant `crlf-kept` (keep the carriage return) was caught only by the oracle's own `test_journal.py`, which a model solving the task does not have, so a model that made the same mistake and wrote no CRLF test of its own would have passed. The mutant `last-equals` (split on the last `=` instead of the first) made the acceptance die with a traceback inside `check_parse` rather than print a verdict: red, but naming no clause. `parse-crlf` now parses the same text with both line endings and compares the records, which covers both sentences directly. Every copy of `common.py` carries it (one per step; the steps are tarred separately), landed as bench `b0d3d22`.

No specification sentence was amended and no reference was amended: rulings are one `check amended`, zero `spec amended`, zero `reference amended`.

## What the two references disagree about, which the tests do not see

The references agree with the tests, and with each other, everywhere the tests look. They disagree in one place the tests do not look, found by reading their decision notes and then confirmed by running both:

- A file that is not valid UTF-8. `obs.py count` and `obsreport.py` exit **1** in `ref-dsf` and the oracle, and **2** in `ref-sonnet`. Both print `error: ` and the decoding message to stderr, both print nothing to stdout. The specification says "a file that cannot be opened or read prints `error: ` ... exits 2; a file `parse` rejects (ValueError) prints `error: ` ... exits 1", and a `UnicodeDecodeError` is both: it is a read failure and it is a `ValueError`. `ref-sonnet` recorded the ambiguity in its notes before choosing; `ref-dsf` did not name the case.
  **Ruling: not adjudicated tonight, recorded as under-specified.** Amending the specification would change what the September rows were asked to do, and the choice is operator's, not the hub's. Neither reading is currently a failure, because no hidden check reads a file that is not UTF-8. Whichever way it is settled, the fix is one sentence in obs-02's and obs-05's specifications plus one check; until then the clause is a known hole and this report is the record of it.

Everything else in the notes is a decision the specification leaves open and both references took the same way, or took differently with no observable difference: a whitespace-only line is not a blank line (both), a repeated key keeps its last value (both), the import spelling inside the moved package (differs, invisible to every check by design), the annotation of a private helper (differs: `dict[str, str]` against `dict[str, str | int]` for `_finish`'s parameter, and the specification says only "the annotations its use implies", so both satisfy it).

## What L1 does not say

- Six tasks of one chain, not the 27 of the whole bench. The 22 single tasks have no second reference, so their tests remain a consistency check with one reference behind them.
- One mutant per clause, and only for the clauses named in the table above: 23 clauses of perhaps twice that many. A clause with no mutant is untested in the second direction, and the mutant directories name exactly which clauses have one.
- The two references were written by two models. They agree with the tests, which is evidence the tests are not tuned to the oracle; it is not evidence that a third model would agree, and it is not evidence about a specification a person would write differently.
- `obs-all` (the six specifications as one ticket, judged by the union of the behaviour checks) validates on its oracle and rejects its starting tree, but no model has run it, so nothing here says whether its checks agree with its specification.

## Runs to re-judge (round zero's list)

`parse-crlf` is an added check, so every earlier run judged without it was judged by a weaker acceptance. It cannot turn an earlier pass into a fail unless that solution mishandled CRLF, and it cannot turn a fail into a pass. The runs to re-judge are every `run.end` of `obs-01-parse` through `obs-06-typehints` and of `obs-all` recorded before bench `b0d3d22` (2026-09-04 01:33). From this commit on, every run records the test version that judged it (`tests` on `run.end`, runner `6ceee8f`), so the list is a query and not a date guess for every future round.

## Provenance

Runner `6ceee8f` on git-host, bench `dc06973` pushed and deployed as `70d39b5` (the runner host's checkout carries one digest commit per shift on top). Reference sessions: `t950-l1-reference-dsf` (deepseek-v4-flash:cloud, finished, six commits, 751 insertions) and `t950-l1-reference-sonnet` (claude-sonnet-5, finished, 85 turns, 656 s, $2.47, seven commits). Their own reports are `reports/950-l1-ref-dsf.md` and `reports/950-l1-ref-sonnet.md`; the sonnet session was refused the write to that path (outside its worktree), reported the refusal, and committed the report in its worktree, from where it was copied here.

# Ground truth for the eight tasks of the tools and thinking questions, 2026-09-05

The same two directions, asked of the eight tasks the RQ2 and RQ3 comparison sets use (`frozen/rq2-2026-09-05-tasks.md` in the bench repository). Written 2026-09-05 by the hub session `factory-rigor-plan` from the runs below.

The second families are claude-sonnet-5 and glm-5.3-flash, not the deepseek used for the obs chain. deepseek is the model under test in RQ2, and a reference written by the arm under test would bias the instrument that judges it toward that arm's own style.

## Direction one: does the acceptance reject a correct solution?

Both references were written from `SPEC.md` and the starting tree alone (`tools/refwork.py`), then judged by the runner's own hidden acceptance rebuilt as a git repository (`tools/refcheck.py`).

| reference | model | tasks | checks run | checks passed | disagreements |
|---|---|---|---|---|---|
| `refw2-sonnet` | claude-sonnet-5, session `t950-l1-ref2-sonnet` | 8 | 61 | 60 | 1 |
| `refw2-glm` | glm-5.3-flash:cloud, session `t950-l1-ref2-glm` | 8 | 61 | 61 | 0 |

Per task, checks passed of checks run, both references except where the row says otherwise: csvstat-python 17 of 17, semver-go 3 of 3, hello-go 3 of 3, split-module-python 11 of 11, rename-package-go 9 of 9, roman-python 8 of 8, intervals-go 4 of 4, duration-python 6 of 6 for glm and **5 of 6 for sonnet**. `.factory/verify.sh` was green in all sixteen trees.

### The one disagreement

| task | check | reference outcome | ruling | the sentence that decides it |
|---|---|---|---|---|
| duration-python | `hidden-rejects` | sonnet's reference accepts `"١s"` and returns 1; glm's raises ValueError | reference amended | "each part a non-negative integer in ASCII digits 0-9 followed by one unit letter" |

What happened, in plain words. The check feeds thirteen strings the specification calls invalid and requires every one to raise ValueError. Twelve were rejected by both references. The thirteenth is the Arabic-Indic digit one followed by `s`. Python's `\d` in a regular expression matches any Unicode decimal digit, not only 0 to 9, and `int()` converts those digits happily, so a pattern written as `(\d+)h` accepts it. The sonnet reference used `\d`; the glm reference used `[0-9]` and rejected it.

The ruling is against the reference and not against the check, because the specification names ASCII digits 0 to 9 in the sentence quoted above and admits no second reading. The check is doing exactly what the sentence says. Nothing in the bench changes.

This is worth keeping rather than deleting, because it is the failure mode the exercise exists to find, running the other way: a check that looks over-strict at first sight is over-strict only if the specification is silent, and here it is not.

## Direction two: does the acceptance accept a wrong solution?

29 mutants over all eight tasks, each the task's own oracle with one named clause of the specification broken and a `WHY` file quoting the sentence it violates (bench `4166551`, driver `tools/mutants.py`).

| task | mutants | caught by a hidden check | caught by the tests in the tree | missed |
|---|---|---|---|---|
| csvstat-python | 6 | 6 | - | 0 |
| semver-go | 4 | 4 | - | 0 |
| intervals-go | 3 | 3 | - | 0 |
| hello-go | 2 | 2 | - | 0 |
| duration-python | 4 | 3 | 1 | 0 |
| roman-python | 3 | 1 | 2 | 0 |
| split-module-python | 4 | 3 | - | 1 |
| rename-package-go | 3 | 2 | - | 1 |
| total | 29 | 24 | 3 | 2 |

### The two that were missed are the same clause twice

| task | mutant | the sentence it violates | what the acceptance did |
|---|---|---|---|
| split-module-python | `reformatted-move` | "with their code moved unchanged ... no reformatting of the moved code" | passed it, 11 of 11 |
| rename-package-go | `changed-more-than-package-line` | "with the content of internal/util/util.go ... changed only in the `package` line" | passed it, 9 of 9 |

Both mechanical tasks say the moved code must arrive unchanged, and no hidden check reads the moved code at all: what is checked is behaviour, the public API, the files that must be gone and the files that must not exist. A solution that rewrote the body of every function it moved would be accepted by the judge and refused by the specification.

This does not favour either arm of RQ2, since both are judged by the same checks. It means the pass counts on those two tasks are more generous than the words they are scored against.

### The three caught by the tests already in the tree

`duration-python/empty-accepted` (returns 0 for `""`), `roman-python/lowercase-accepted` (accepts `"iv"`) and `roman-python/range-4000` (accepts 4000). The driver counts a catch by `visible-tests` alone as a miss, because on an additive task the tests in the tree are the model's own and prove nothing. On these three repair tasks they are the task's own fixed tests, the specification forbids editing them, and a separate hidden check (`tests-untouched`) confirms they were not edited. So these are real catches and the driver's rule is the thing that needs the exception, not the tasks.

The narrowest of the three is `duration-python`: its hidden reject list holds thirteen invalid strings and `""` is not one of them. Adding it would close the gap without relying on the visible tests.

### Two mutants were thrown away rather than reported

Both would have been findings about my own work rather than about the tests.

`csvstat-python/short-row-skipped` dropped the cells of short rows instead of filling them with the empty string, and the acceptance passed it. The two programs are the same program: empty cells are filtered out one line later, so nothing observable differs. It was replaced by `short-row-zero`, which counts a missing cell as `0`, and that one is caught.

`roman-python/bool-accepted` made `to_roman(True)` return `"I"`. The specification says any value other than an int 1 to 3999 raises, and in Python `True` is an int equal to 1, so the specification does not decide the case; the oracle is stricter than its own words. A variant that disagrees only with the oracle is not a mutant.

The rule both cases point at: a mutant must be observably wrong against the specification, or a MISSED line says nothing about the tests.

### Nothing was amended

All of this arrived while the RQ2 rounds were already running under this acceptance. Moving the judge underneath a round in flight is the defect this ladder exists to stop, so the checks stand as they are tonight and the fixes are listed for operator instead.

## Provenance

Trees kept at `<scratchpad>/refw2-sonnet` and `<scratchpad>/refw2-glm`, eight commits each, one per task; results at `<scratchpad>/refcheck-sonnet.json` and `<scratchpad>/refcheck-glm.json`. Task list and its selection rule in `frozen/rq2-2026-09-05-tasks.md` in the bench repository (bench `54af6c5`). Writers' own reports at `reports/950-l1-ref2-sonnet.md` and `reports/950-l1-ref2-glm.md`; neither is the evidence here, the acceptance runs are.
