# Changelog

All notable changes to this repository are recorded here. A version names a
tagged release: `v1.0` is the first release, and `v1.1` is the errata release
being prepared and not yet tagged.

## v1.1 (unreleased)

Errata. The paper's numbers are unchanged. The corrections are to the shipped
notes and to one sentence in the paper that misdescribed where one of its
numbers came from.

- The five working notes were redacted and repointed. The credential-store
  path and the ssh detail are gone, private absolute paths became role names,
  each note opens with a short list of the terms it uses, and the review tags
  were stripped.
- The study inputs were added under `study-inputs/`, copied byte for byte
  from `dark` at tag `v0.1.0`: `frozen/rq2-2026-09-05.toml`,
  `frozen/rq2b-2026-09-05.toml`, `frozen/rq3-2026-09-05.toml`,
  `frozen/rq2-2026-09-05-tasks.md`, `admission/frozen-2026-09-04.md` and
  `probes/thinking-2026-09-03.jsonl`. `study-inputs/README.md` describes each
  file and gives its sha256.
- Section 5.3's sentence about the Qwen 3.5 9B ceiling count now reads the
  count from the committed run log, which the appendix re-derives, and keeps
  the readable-file-block reading as the working-note part.

## v1.0

First release. The paper, its two-page summary, the appendix that re-derives
every number, the figure script, five working notes and three exported runs,
rendered from the commit the `v1.0` tag names.
