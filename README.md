# A model alone in a throwaway machine

*How its work was judged, what tools changed, and what more thinking bought.* A language model wrote code on its own, inside a virtual machine that existed for one task and was deleted when the task ended, judged by tests it never saw. Measured on 8 small tasks, 6 models and 368 runs: the hidden tests were validated before they judged anything; a shell and file tools changed no verdict and cost three and a half times the model calls; every model solved more with a thinking budget, and a model with no budget spends its calls repeating itself. Every number re-derives from the run log with one command. The two-page summary is [summary.md](summary.md); the paper is [paper.md](paper.md).

This repository is the study: the paper, its two-page summary, the appendix that binds every number to a command, the figure script, five working notes and three exported runs. The pipeline that produced the runs, the **runner**, and its measuring instrument, the **bench**, are the tool repository [dark](https://github.com/majgull/dark); this paper describes them at its tag `v0.1.0`. The 31 tasks with their hidden tests are the repository [dark-tasks](https://github.com/majgull/dark-tasks) at its tag `v1.0`, the set the run records name `acceptance-v4`. The raw evidence, 12 MB of run log, launcher logs and one derived table, is the dataset [dark-evidence](https://huggingface.co/datasets/majgull/dark-evidence), pinned to one revision by `evidence/MANIFEST.txt`.

## The claim, and the command that checks it

Every number in the paper re-derives from the run log. Two commands fetch the evidence and run every row of the appendix again, stopping on the first disagreement:

```
python3 tools/fetch-evidence.py             # 40 files from the pinned dataset revision, sha256 checked
python3 appendix.py --check                 # 375 rows, 0 disagree
```

They need Python 3, `jq`, `bash`, coreutils and `git`; the second takes a few minutes. `docs/fresh-container.md` is the transcript of a bare Debian container running them. The run log is two snapshots of one append-only file; the later one contains the earlier one as a byte-for-byte prefix, and the appendix checks that too. The tool repository's own two commands, its 362 tests and its task check, are in its README.

## How this was made

By one person and several language models, and the split is stated so a reader can weigh it. majgull chose the questions, the task classes, the models, the limits and the licence, took the decisions the paper records as decisions, and reviewed every draft with inline comments. Claude, running as a coding agent on his machine, coordinated: it planned and launched every batch, wrote the appendix and figure scripts, and wrote the paper. Delegated sessions of DeepSeek, GLM and Claude Sonnet models wrote the runner and the bench, the tasks with their gold solutions and mutants, and reviewed the tree. No line of code or prose in this repository was typed by a person. Section 8 of the paper says the same in more detail, and says why the repository is dedicated to the public domain rather than licensed.

## What the study found

Three questions, on one fixed set of 8 small Go and Python tasks with 64 hidden tests, each stated in section 3 of the paper with what it varies, what it holds fixed and what counts as its answer:

- **Are the hidden tests right?** Two reference solutions written by models not under test pass 63 and 64 of the 64 tests. 29 deliberately broken copies were all caught after two fixes to the tests; the tests as first written let 2 through. Scoring 41 older results again changed 0 verdicts.
- **Do tools help?** One model, 40 runs with no tools and 40 with a shell and file tools, under the same limits. 35 solved against 32, no paired test separates them, and the tool arm made three and a half times the model calls.
- **Does more thinking help?** Six models at three thinking budgets, run twice. Solved runs rose from 28 of 48 with no reasoning to 36 of 48 with the largest budget, every model improved, and the second round repeated the direction but not its sharpness. The mechanism is visible in the record: with no reasoning budget, 41 per cent of calls re-sent a reply the run had already sent.

The paper states what moved besides the variable under test, what is not recorded, and what a stranger would still need to rebuild the serving side. Section 7 is the list of every known defect in the data. Not a benchmark for ranking models: 8 tasks and 6 models are the instrument's first calibration, not a leaderboard. Not a security result: isolation is the premise and the paper says it was not tested.

## Layout

```
paper.md, summary.md     the paper and its two-page summary, rendered
paper.src.md, summary.src.md, numbers.md
                         their sources; every number is a token bound to a row of numbers.md
appendix.py              writes numbers.md by running every row's command; --check re-runs them all
figs.py, rq3-table.py    the figures (figs/, SVG) and the full RQ3 tables
tools/                   fetch-evidence.py, manifest.py, the renderer and the linter
evidence/MANIFEST.txt    the dataset revision and a sha256 per evidence file; the files themselves are fetched
notes/                   five working notes, four of which section 5.1 rests on, shipped as written
runs/                    three runs exported end to end, one per task class
docs/                    the fresh-container transcript
```

`evidence/ledger`, `evidence/launch`, `evidence/derived` and the three run directories are not in git. `tools/fetch-evidence.py` downloads them from the dataset at the revision the manifest names and refuses any file whose hash differs. Anything that changes a number in the paper changes a hash in the manifest, and the manifest is in git.

## Provenance

The evidence files are the ones the experiments wrote, with one kind of change: private identifiers (network addresses, account names, and the names of private repositories and tools) were replaced by role names or generic words before the hashes were taken, the same substitution on every file. Section 8 of the paper states this and lists the hashes. This repository starts at one import commit from the private tree the paper was written in.

## How to cite

The citation target is the tagged release `v1.0`, at https://github.com/majgull/dark-paper/releases/tag/v1.0; the tag names the commit the paper was rendered from, and a revised paper gets a later tag. Cite it as: majgull, *A model alone in a throwaway machine: how its work was judged, what tools changed, and what more thinking bought*, release `v1.0` of github.com/majgull/dark-paper, September 2026.

## License

The whole repository, paper, scripts and notes, and the dataset it points to, are dedicated to the public domain under CC0 1.0 Universal; `LICENSE` is its text. Most of this repository was generated by language models, and section 8 of the paper says, with the sources, that under EU, German and US law such material is mostly outside copyright already; the dedication gives away whatever remains, with a fallback licence for any right the law does not let a person waive, and disclaims warranty. Nothing asks for attribution. A citation of the paper is welcome and not required. Anyone carrying code or text from here into a project with its own rules on model-written contributions should treat it as model-written, because it is.
