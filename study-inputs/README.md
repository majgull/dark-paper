# Study inputs

The experiment inputs the paper's numbers rest on. Each file below is copied
unchanged from the tool repository `dark` at tag `v0.1.0`, which no longer
ships these study artifacts; only the example limits file stayed there. A
limits file (here called an envelope) fixes the model calls, wall seconds and
thinking characters one run is cut off at.

`frozen/rq2-2026-09-05.toml` is the envelope the first RQ2 comparison set ran
under.
sha256 `e00bf0b866cf55eace0e37f4a3542df7db2940bd0094d877166985f6a2de4fce`.

`frozen/rq2b-2026-09-05.toml` is the envelope of the second RQ2 set, which
raised the call cap until it stopped binding either arm.
sha256 `aad3f8146bb4f8cb56c1b914ad8f06a8ee279a02c01278cc4e08862009e304b6`.

`frozen/rq3-2026-09-05.toml` is the envelope every RQ3 cell ran under.
sha256 `4fe9e97b19286a9b64ab18ebca1f6cd23ca0b404745da80831de4865cbc2d7c0`.

`frozen/rq2-2026-09-05-tasks.md` lists the eight tasks the RQ2 and RQ3
comparison sets share, with the rule that picked them.
sha256 `e1383b162dcded2ad7f1021a83a8b524af06ead3641b4fcc4dfeae217315a866`.

`admission/frozen-2026-09-04.md` is the admission table, the runner's answer
to which model tiers may take a run of a class, as it stood when one
comparison lane started.
sha256 `9ca248910f768f21520d7a432b4bc7cacf6908b923b84aea1b14151a4bd16f2f`.

`probes/thinking-2026-09-03.jsonl` is a sample of raw model replies to one
fixed prompt at three thinking levels, kept as the measurement behind the
reports' statements about thinking and tokens.
sha256 `ec0e40bc32db10dbe6e4752c03ef01dc3658eb2f6f0e92bc974652b1ab6bae35`.
