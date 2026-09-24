#!/usr/bin/env python3
"""Write numbers.md by running every command it lists. Run from this directory.

One row per number quoted in paper.md: its id, the number,
the section it appears in, the file it comes from, and a command that re-derives
it. The number column is the output of that row's command, so the appendix
cannot state a number its own command does not reproduce, and a command that
fails or that disagrees with what the paper says stops the run.

The id is what binds a number to the paper: the paper source writes each number
as `{{num:<id>}}` and `tools/render.py` substitutes it, so a larger run
updates the paper by regenerating this file and re-rendering. Ids are derived
from the row's description, kebab-case, and a collision stops the run rather
than silently renaming a number the paper already cites.

    python3 appendix.py [--check] [--assert-rows FILE]

--check re-runs every command and compares it against the committed appendix by
id instead of rewriting it. Needs bash, jq and coreutils.

--assert-rows reads one reply-counter file and exits non-zero if any row in it
carries more distinct replies than calls. The same check runs before either of
the two modes above, over the snapshot the mechanism table of section 5.3 is
built from: a derived table whose numerator and denominator come from different
populations produces rows that cannot happen, and one that cannot happen is a
defect in the method rather than an outlier.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from numbers_table import escape, parse, slug, tokens

L5 = "evidence/ledger/2026-09-05.jsonl"
L6 = "evidence/ledger/2026-09-06.jsonl"
D = "evidence/derived/rq3-r1-distinct-calls.jsonl"
S2 = "evidence/launch/rq2c-full2-20260905-1553.log.shifts"
S3 = "evidence/launch/rq3-r1-20260905-1923.log.shifts"
S3B = "evidence/launch/rq3-r2-20260906-1416.log.shifts"
LOG3 = "evidence/launch/rq3-r1-20260905-1923.log"
LOG3B = "evidence/launch/rq3-r2-20260906-1416.log"
LOG2 = "evidence/launch/rq2c-full2-20260905-1553.log"
TABLE = "rq3-table.py"
OUT = "numbers.md"

# Every ledger query selects the runs of one question by its committed shift
# list, never by a date range: the snapshots hold other work from the same days.
SEL = 'select(.kind=="run.end")|.shift as $s|select(($S|split("\\n"))|index($s))'

ROWS = []


def q(shifts, ledger, filt, out="length"):
    return f"jq -rs --rawfile S {shifts} '[.[]|{SEL}|{filt}]|{out}' {ledger}"


def row(section, what, cmd, expect=None, rid=None):
    """One appendix row. The id defaults to the description in kebab-case; pass
    `rid` where two rows would describe themselves the same way."""
    ROWS.append((rid or slug(what), section, what, cmd, expect))


def pair_cmd(a, b, S3=S3):
    """Discordant pairs between two think levels, split by direction."""
    return (f"jq -rs --rawfile S {S3} '[.[]|{SEL}|{{k:((.tier|sub(\"-nonthink\";\"\"))+\"|\"+.task),"
            f"t:.think,p:(.outcome==\"pass\")}}]|group_by(.k)|"
            f"map({{a:(map(select(.t==\"{a}\"))[0].p),b:(map(select(.t==\"{b}\"))[0].p)}})|"
            f"[(map(select(.a and (.b|not)))|length),(map(select(.b and (.a|not)))|length)]|join(\" \")' {L6}")


def pair_total_cmd(a, b, S3=S3):
    """How many pairs disagree at all between two think levels."""
    return (f"jq -rs --rawfile S {S3} '[.[]|{SEL}|{{k:((.tier|sub(\"-nonthink\";\"\"))+\"|\"+.task),"
            f"t:.think,p:(.outcome==\"pass\")}}]|group_by(.k)|"
            f"map({{a:(map(select(.t==\"{a}\"))[0].p),b:(map(select(.t==\"{b}\"))[0].p)}})|"
            f"[(map(select(.a and (.b|not)))|length),(map(select(.b and (.a|not)))|length)]|add' {L6}")


def wall_dir_cmd(a, b):
    """Families whose think level `b` costs more wall time than level `a`."""
    return (f"jq -rs --rawfile S {S3} '[.[]|{SEL}|{{f:(.tier|sub(\"-nonthink\";\"\")),"
            f"t:.think,w:.wall_seconds}}]|group_by(.f)|"
            f"map({{a:(map(select(.t==\"{a}\"))|map(.w)|add),b:(map(select(.t==\"{b}\"))|map(.w)|add)}})|"
            f"map(select(.b>.a))|length' {L6}")


def exact_p(n, x, places=3):
    """Two-sided exact binomial p for x of n discordant pairs, at even odds."""
    return ("python3 -c 'from math import comb; "
            f"n={n}; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
            f"print(round(sum(v for v in p if v<=p[{x}]+1e-12),{places}))'")


# The two RQ3 rounds put side by side. A cell is one (model, think level) and
# its batch id ends in the same `rq3-<model>-<level>` suffix in both rounds, so
# the suffix is the pairing; a pair is one (cell, task), 144 of them per round.
# jq has no cross-file join of this shape, so this one is Python over the two
# committed batch lists and the one committed snapshot that holds both rounds.
RQ3_ROUNDS = (
    "python3 -c \"import json;"
    f"o=[l.strip().split('-',2)[2] for l in open('{S3B}') if l.strip()];"
    f"s1=set(l.strip() for l in open('{S3}') if l.strip());"
    f"s2=set(l.strip() for l in open('{S3B}') if l.strip());"
    f"rs=[json.loads(l) for l in open('{L6}')];"
    "rs=[r for r in rs if r.get('kind')=='run.end'];"
    "a={(r['arm'],r['task']):(r['outcome']=='pass') for r in rs if r['shift'] in s1};"
    "b={(r['arm'],r['task']):(r['outcome']=='pass') for r in rs if r['shift'] in s2};"
    "assert len(a)==144 and len(b)==144 and set(a)==set(b), 'the two rounds do not pair';"
    "ks=sorted(a);"
    "lvl=lambda c: c.rsplit('-',1)[1];"
    "ca={c:sum(v for (cc,t),v in a.items() if cc==c) for c in o};"
    "cb={c:sum(v for (cc,t),v in b.items() if cc==c) for c in o};"
    "print(%s)\"")


def cell_line(shift):
    """One row of the round-two per-cell table: passes, calls, seconds, net Wh,
    runs the seconds limit ended. Read off the per-run table of the table script,
    which is where the idle baseline is subtracted and where a baseline that came
    back impossible leaves the net figure not measured."""
    return (f"python3 {TABLE} --log {LOG3B} | awk -F'|' -v s={shift} "
            "'{for(i=1;i<=NF;i++) gsub(/^ +| +$/,\"\",$i)} "
            "$2==s {p+=($4==\"pass\"); c+=$6; t+=$7; cut+=($5==\"seconds\"); "
            "if($10==\"n/a\") na=1; else net+=$10} "
            "END {printf \"%d/8 | %d | %d | %s | %d\\n\", p, c, t, "
            "(na?\"n/a\":sprintf(\"%.3f\", net)), cut}'")


# RQ2 read with the rounds kept: round k of one arm ran next to round k of the
# other, so the shift list's order is the pairing. jq has no index-of-my-own-arm,
# so this one is Python over the same two committed files.
RQ2_PAIRS = (
    "python3 -c \"import json;"
    f"sh=[l.strip() for l in open('{S2}') if l.strip()];"
    "arm=lambda s: s.rsplit('-',1)[1];"
    "idx={s:(arm(s),[x for x in sh if arm(x)==arm(s)].index(s)) for s in sh};"
    f"rs=[json.loads(l) for l in open('{L5}')];"
    "d={(r['task'],idx[r['shift']][1],idx[r['shift']][0]):(r['outcome']=='pass')"
    " for r in rs if r.get('kind')=='run.end' and r.get('shift') in idx};"
    "ts=sorted({k[0] for k in d});"
    "pr=[(t,i,d[(t,i,'pipeline')],d[(t,i,'session')]) for t in ts for i in range(5)];"
    "print(%s)\"")


def build():
    # ---- sections 2 and 4: the system and the setup
    row("2", "think level scale, characters per call",
        "grep -o 'none 0, low 8000, medium 32000, high 64000' notes/950-research.md",
        "none 0, low 8000, medium 32000, high 64000")
    row("2", "the middle thinking budget, characters per call",
        "grep -o 'low 8000' notes/950-research.md | head -1 | grep -oE '[0-9]+'", "8000")
    row("abstract, 2", "the largest thinking budget run, characters per call",
        "grep -o 'medium 32000' notes/950-research.md | head -1 | grep -oE '[0-9]+'", "32000")
    row("9", "the commit the judge tag acceptance-v4 was cut from",
        "grep -o '7e4dec91821f330471c5e0e05e9ed86d75f4fbe4' notes/950-judge-v4.md | head -1",
        "7e4dec91821f330471c5e0e05e9ed86d75f4fbe4")
    # The id of this row is the paper's, and the paper's body may not carry a
    # commit id even inside an id: hence "the check version" and not the string.
    row("2, 4.1", "closing records carrying the check version, both questions",
        f"expr $({q(S2, L5, 'select(.tests==\"5d6f78a\")')}) + $({q(S3, L6, 'select(.tests==\"5d6f78a\")')})",
        "224")
    row("4.1", "hidden checks over the eight tasks under the amended judge",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.checks_total>0)|"
        f"{{t:.task,c:.checks_total}}]|unique|map(.c)|add' {L6}", "64")
    row("4.2, 6", "closing records asserting their virtual machine was destroyed, both questions",
        f"expr $({q(S2, L5, 'select(.asserts.vms_destroyed)')}) + $({q(S3, L6, 'select(.asserts.vms_destroyed)')})",
        "224")
    row("9", "distinct judge versions over the RQ3 runs",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|.tests]|unique|join(\",\")' {L6}", "5d6f78a")
    row("4.1, 5.3", "tasks in the set",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|.task]|unique|length' {L6}", "8")
    row("2, 4.1", "tasks per class",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|{{t:.task,c:.cls}}]|unique|group_by(.c)|"
        f"map(.[0].c+\" \"+(length|tostring))|join(\", \")' {L6}",
        "additive 3, mechanical 2, repair 3")
    row("2, 5.3", "models in the RQ3 round",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|(.tier|sub(\"-nonthink\";\"\"))]|unique|length' {L6}", "6")
    row("2", "models served here",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|(.tier|sub(\"-nonthink\";\"\"))]|unique|"
        f"map(select(startswith(\"my/\")))|length' {L6}", "4")
    row("2", "models served at a provider",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|(.tier|sub(\"-nonthink\";\"\"))]|unique|"
        f"map(select(startswith(\"my/\")|not))|length' {L6}", "2")
    row("8", "tier names in the RQ3 round",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|.tier]|unique|length' {L6}", "10")
    for task in ["csvstat-python", "duration-python", "hello-go", "intervals-go",
                 "rename-package-go", "roman-python", "semver-go", "split-module-python"]:
        row("4.1", f"{task}: class, and hidden checks when it reaches a verdict",
            f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.task==\"{task}\" and .checks_total>0)|"
            f"(.cls+\" \"+(.checks_total|tostring))]|unique|join(\",\")' {L6}")
    row("9", "RQ2 frozen envelope file and its sha256",
        f"jq -r 'select(.kind==\"run.start\" and .arm==\"rq2c-pipeline\")|.frozen|.file+\" \"+.sha256' {L5} | sort -u",
        "rq2b-2026-09-05.toml aad3f8146bb4f8cb56c1b914ad8f06a8ee279a02c01278cc4e08862009e304b6")
    row("9", "RQ3 frozen envelope file and its sha256",
        f"jq -r --rawfile S {S3} 'select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.frozen|.file+\" \"+.sha256' {L6} | sort -u",
        "rq3-2026-09-05.toml 4fe9e97b19286a9b64ab18ebca1f6cd23ca0b404745da80831de4865cbc2d7c0")
    row("4.3", "RQ3 envelope per task class: calls, seconds, reasoning characters",
        f"jq -r --rawfile S {S3} 'select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|\"\\(.cls) \\(.envelope.calls) \\(.envelope.seconds) "
        f"\\(.envelope.max_reasoning_chars)\"' {L6} | sort -u | paste -sd';' | sed 's/;/; /g'",
        "additive 24 900 40000; mechanical 16 300 10000; repair 24 900 40000")
    row("4.13", "distinct runner hosts on the RQ3 batch records",
        f"jq -r --rawfile S {S3} 'select(.kind==\"shift.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.host' {L6} | sort -u | "
        "awk 'END {print (NR==1 ? \"identical\" : \"different\")}'", "identical")
    row("4.4", "distinct power-sampling host pairs on the RQ3 records, and GPU count",
        f"jq -r --rawfile S {S3} '{SEL}|\"\\(.power.cpu_host)|\\(.power.gpu_host)|\\(.power.gpu_devices)\"' "
        f"{L6} | sort -u | awk -F'|' '{{n++; g=$3}} END {{print (n==1 ? \"the same pair,\" : n \" pairs,\"), g, \"cards\"}}'",
        "the same pair, 2 cards")
    row("9", "the GPU cards the local models ran on",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3} | grep '^{{' | jq -r '.gpu[].name' | sort -u",
        "NVIDIA GeForce RTX 2080 Ti")
    row("4.4", "idle samples taken, one before each local cell",
        f"grep -c 'idle baseline: 300s, no VM' {LOG3}", "12")
    row("4.4, 6", "CPU package watts of the eleven usable idle samples, lowest and highest",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3} | grep '^{{' | jq -r 'select(.cpu_watts>0)|.cpu_watts' "
        f"| sort -n | sed -n '1p;$p' | paste -sd' ' | awk '{{print $1, \"and\", $2}}'", "33.6 and 34.6")
    row("4.4", "GPU watts of the eleven usable idle samples, lowest and highest",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3} | grep '^{{' | jq -r 'select(.cpu_watts>0)|.gpu_watts' "
        f"| sort -n | sed -n '1p;$p' | paste -sd' ' | awk '{{print $1, \"and\", $2}}'", "20.3 and 24.4")
    row("4.6", "RQ3 cells that printed 0 mismatch(es)", f"grep -c '0 mismatch(es)' {LOG3}", "18")
    row("4.6", "RQ2 shifts that printed 0 mismatch(es)", f"grep -c '0 mismatch(es)' {LOG2}", "10")
    row("4.6", "mismatch lines in the RQ3 log that were not zero",
        f"grep -o '[0-9]* mismatch(es)' {LOG3} | grep -vc '^0 ' || true", "0")
    row("4.7", "sum of the seconds field over the RQ3 runs", q(S3, L6, ".seconds", "add"), "21434")
    row("4.7", "sum of the wall_seconds field over the RQ3 runs", q(S3, L6, ".wall_seconds", "add"), "27139")
    # The seven runs the seconds limit ended, as one number the body can carry:
    # how far past its class limit the latest of them ran. It replaces the
    # semicolon-joined shell aggregation the body pasted, "1 additive 904; 3
    # additive 905; 3 mechanical 304".
    row("4.7", "the largest overshoot past a class limit among the runs the seconds limit ended",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.fail_kind==\"seconds\")|"
        f"(.seconds-(if .cls==\"mechanical\" then 300 else 900 end))]|max' {L6}", "5")

    # The request counter, which section 4.7 asserted a retry above. It cannot
    # show one: the excess over the call counter is the recorded count of
    # budget-forcing cuts, run by run.
    row("4.7", "budget-forcing cuts recorded over the RQ3 round",
        q(S3, L6, ".cuts//0", "add"), "13")
    row("4.7", "requests over calls on the runs that recorded a request count",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select((.requests//0)>0)]|"
        f"(map(.requests)|add)-(map(.calls)|add)' {L6}", "13")
    row("4.7", "runs recording a request count whose excess over calls is not that run's own cut count",
        q(S3, L6, 'select((.requests//0)>0 and (.requests-.calls)!=(.cuts//0))'), "0")
    row("4.7", "runs recording no request at all against a positive call count",
        q(S3, L6, 'select((.requests//0)==0 and .calls>0)'), "7")

    # ---- 4.2, the class limits (the shorter mechanical ceiling, and what it ended; added in the last review round)
    row("4.2", "RQ2 thinking budget by task class",
        f"jq -rs --rawfile S {S2} '[.[]|select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.cls+\" \"+.envelope.think]|unique|join(\"; \")' {L6}",
        "additive low; mechanical none; repair low")
    row("4.2", "mechanical runs in the RQ3 round", q(S3, L6, 'select(.cls=="mechanical")'), "36")
    row("4.2", "runs the seconds limit ended on the mechanical limit of 300 seconds",
        q(S3, L6, 'select(.fail_kind=="seconds" and .cls=="mechanical")'), "3")
    row("4.2", "mechanical runs the call ceiling ended in the RQ3 round",
        q(S3, L6, 'select(.fail_kind=="calls" and .cls=="mechanical")'), "1")
    row("4.2", "round two, mechanical runs the call ceiling ended",
        q(S3B, L6, 'select(.fail_kind=="calls" and .cls=="mechanical")'), "0")

    # ---- 5.1
    row("5.1", "sonnet solution: tasks",
        "awk -F'|' '/refw2-sonnet. . claude/ {print $4+0}' notes/950-l1-adjudication.md", "8")
    row("5.1", "sonnet solution: disagreements",
        "awk -F'|' '/refw2-sonnet. . claude/ {print $7+0}' notes/950-l1-adjudication.md", "1")
    row("5.1", "glm solution: tasks",
        "awk -F'|' '/refw2-glm. . glm/ {print $4+0}' notes/950-l1-adjudication.md", "8")
    row("5.1", "glm solution: disagreements",
        "awk -F'|' '/refw2-glm. . glm/ {print $7+0}' notes/950-l1-adjudication.md", "0")
    row("abstract, 5.1", "reference solutions, checks run each",
        "awk -F'|' '/refw2-sonnet. . claude/ {print $5+0}' notes/950-l1-adjudication.md", "61")
    row("abstract", "sonnet reference, checks passed of 61",
        "awk -F'|' '/refw2-sonnet. . claude/ {print $6+0}' notes/950-l1-adjudication.md", "60")
    row("abstract", "glm reference, checks passed of 61",
        "awk -F'|' '/refw2-glm. . glm/ {print $6+0}' notes/950-l1-adjudication.md", "61")
    row("5.1", "mutants caught by a hidden check as first run",
        "awk -F'|' '/^. total . 29 ./ {print $4+0}' notes/950-l1-adjudication.md", "24")
    row("5.1", "mutants caught only by the tests in the tree as first run",
        "awk -F'|' '/^. total . 29 ./ {print $5+0}' notes/950-l1-adjudication.md", "3")
    row("abstract, 5.1", "mutants written",
        "awk -F'|' '/^. total . 29 ./ {print $3+0}' notes/950-l1-adjudication.md", "29")
    row("abstract", "mutants the suite as written missed",
        "awk -F'|' '/^. total . 29 ./ {print $6+0}' notes/950-l1-adjudication.md", "2")
    row("5.1", "mutants killed only by the tests in the tree after the amendments",
        "grep -o '2.. (was 3)' notes/950-judge-v4.md | grep -oE '^[0-9]+'", "2")
    row("5.1", "mutants caught by a hidden check after the two amendments",
        "grep -o '27.. (was 24)' notes/950-judge-v4.md | grep -oE '^[0-9]+'", "27")
    row("5.1", "mutants missed after the two amendments",
        "grep -o '0.. (was 2)' notes/950-judge-v4.md | grep -oE '^[0-9]+'", "0")
    row("5.1", "sonnet solution against the amended judge, checks passed of checks run",
        "grep -o '63/64' notes/950-judge-v4.md | head -1", "63/64")
    row("5.1", "glm solution against the amended judge, checks passed of checks run",
        "grep -o '64/64' notes/950-judge-v4.md | head -1", "64/64")
    # The abstract quotes the amended set, which is the set every run here was
    # scored under; the pre-amendment pair stays as the clause that motivates it
    # Same two figures, without the denominator inside them.
    row("abstract", "sonnet solution against the amended judge, checks passed",
        "grep -o '63/64' notes/950-judge-v4.md | head -1 | cut -d/ -f1", "63")
    row("abstract", "glm solution against the amended judge, checks passed",
        "grep -o '64/64' notes/950-judge-v4.md | head -1 | cut -d/ -f1", "64")
    row("5.1", "runs in the RQ1 smoke shift under the amended judge",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and .shift==\"20260905-143140-rq1-smoke-v4\")]|length' {L5}", "6")
    # One figure per reference solution rather than the six-way list the body
    # pasted, which carried the batch's own arm names, undefined in the paper.
    for ref, name in (("ref-glm", "the GLM 5.3 Flash reference solution"),
                      ("ref-sonnet", "the Claude Sonnet 5 reference solution")):
        row("5.1", f"that batch, {name}: checks passed of checks run over its three tasks",
            f"jq -rs '[.[]|select(.kind==\"run.end\" and .shift==\"20260905-143140-rq1-smoke-v4\" "
            f"and .arm==\"{ref}\")]|((map(.checks_ok)|add)|tostring)+\" of \"+"
            f"((map(.checks_total)|add)|tostring)' {L5}")
    row("5.1", "branches attempted for re-scoring",
        "grep -o '45 branches attempted' notes/950-round-zero.md | grep -oE '^[0-9]+'", "45")
    row("abstract, 5.1", "verdicts that changed when 41 branches were scored again",
        "grep -o '41 judged, 0 flipped' notes/950-round-zero.md | grep -oE '[0-9]+ flipped' "
        "| grep -oE '^[0-9]+'", "0")
    row("5.1", "branches scored again, counted in the ledger rather than in a report",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.shift|test(\"round-zero\")))]|length' {L5}", "41")
    row("5.1", "of those 41, the ones that came back a pass",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.shift|test(\"round-zero\")) and .outcome==\"pass\")]|length' {L5}",
        "21")
    row("5.1", "of those 41, the ones that came back a capability failure",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.shift|test(\"round-zero\")) and .outcome==\"fail:capability\")]|length' {L5}",
        "20")
    row("5.1", "of the 41, those the report records as a pass before and after",
        "awk -F'|' '/still .pass./ {print $3+0}' notes/950-round-zero.md", "21")
    row("5.1", "of the 41, those the report records as a capability failure before and after",
        "awk -F'|' '/still .fail:capability./ {print $3+0}' notes/950-round-zero.md", "20")
    row("5.1", "branches eligible for re-scoring, from which 41 were sampled",
        "grep -o '583 of the 871' notes/950-round-zero.md", "583 of the 871")
    row("5.1", "the seed the round-zero sample was drawn with",
        "grep -o 'drawn with seed 950' notes/950-round-zero.md | grep -oE '[0-9]+$'", "950")
    row("5.1", "how many branches each of the two round-zero batches scored",
        f"jq -r 'select(.kind==\"run.end\" and (.shift|test(\"round-zero\")))|.shift' {L5} "
        f"| sort | uniq -c | tr -s ' ' | sed 's/^ //' | cut -d' ' -f1 | paste -sd';' "
        f"| sed 's/;/ and /'", "36 and 5")
    row("5.1", "the second round-zero shift, the task its five branches belong to",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and .shift==\"20260905-073355-round-zero\")|.task]"
        f"|unique|join(\",\")' {L5}", "hello-go")
    row("5.1", "rule of three: 95 per cent upper bound on the flip rate, 0 of 41",
        "python3 -c 'print(round(3/41*100))'", "7")
    row("5.1", "chain set: tasks, checks run, checks passed, disagreements, per solution",
        "awk -F'|' '/ref-sonnet. . claude/ {printf \"%d, %d, %d, %d\\n\", $4, $5, $6, $7}' "
        "notes/950-l1-adjudication.md", "6, 174, 174, 0")
    row("5.1", "chain set: mutants, mutants caught, mutants missed",
        "awk -F'|' '/^. total . 23 ./ {printf \"%d, %d, %d\\n\", $3, $4, $5}' "
        "notes/950-l1-adjudication.md", "23, 23, 0")

    # ---- 5.2
    row("5.2", "shifts in the RQ2 set", f"wc -l < {S2}", "10")
    row("5.2", "runs in the RQ2 set", q(S2, L5, "."), "80")
    row("5.2", "opening records in the RQ2 set",
        f"jq -rs --rawfile S {S2} '[.[]|select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))]|length' {L5}", "80")
    row("9", "first and last shift record of the RQ2 set",
        f"jq -r --rawfile S {S2} 'select(.kind==\"shift.start\" or .kind==\"shift.end\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.iso' {L5} | sort | sed -n '1p;$p' | paste -sd' ' | awk '{{print $1, \"to\", $2}}'",
        "2026-09-05T15:54:05+02:00 to 2026-09-05T18:28:36+02:00")
    # The body used to print the record's outcome enum here. It says the same
    # thing as a count of the one outcome that would be neither a failed check
    # nor a spent limit.
    row("5.2", "RQ2 runs recorded as a structural failure",
        q(S2, L5, 'select(.outcome=="fail:structural")'), "0")
    row("5.2", "runs whose virtual machine was destroyed, of 80",
        q(S2, L5, "select(.asserts.vms_destroyed)"), "80")
    row("9", "tiers in the RQ2 set",
        f"jq -rs --rawfile S {S2} '[.[]|{SEL}|.tier]|unique|join(\",\")' {L5}", "deepseek-v4-flash:cloud")
    row("abstract, 5.2", "runs per arm in RQ2",
        q(S2, L5, 'select(.arm=="rq2c-pipeline")'), "40")
    for arm, name in (("rq2c-pipeline", "pipeline"), ("rq2c-session", "session")):
        row("5.2", f"{name}, tasks solved in at least one round of 8",
            f"jq -rs --rawfile S {S2} '[.[]|{SEL}|select(.arm==\"{arm}\")|"
            f"{{t:.task,p:(.outcome==\"pass\")}}]|group_by(.t)|map(select(any(.[];.p)))|length' {L5}")
    for task in ["csvstat-python", "duration-python", "hello-go", "intervals-go",
                 "rename-package-go", "roman-python", "semver-go", "split-module-python"]:
        for arm, name in (("rq2c-pipeline", "pipeline"), ("rq2c-session", "session")):
            row("5.2", f"{task}, {name} rounds passed of 5",
                q(S2, L5, f'select(.task=="{task}" and .arm=="{arm}" and .outcome=="pass")'))
    for arm, name in (("rq2c-pipeline", "pipeline"), ("rq2c-session", "session")):
        row("5.2", f"{name}, runs solved of 40",
            q(S2, L5, f'select(.arm=="{arm}" and .outcome=="pass")'))
        # The limit-excluded denominator that section 4.1's three outcomes ask
        # for: the runs of this arm that reached a check at all.
        row("5.2", f"{name}, runs that reached a check, of 40",
            q(S2, L5, f'select(.arm=="{arm}" and .fail_kind==null)'))
        row("5.2", f"{name}, model calls over the 40 runs",
            q(S2, L5, f'select(.arm=="{arm}")|.calls', "add"))
        row("5.2", f"{name}, median model calls per run",
            q(S2, L5, f'select(.arm=="{arm}")|.calls', "sort|(.[19]+.[20])/2"))
        row("5.2", f"{name}, most model calls in one run",
            q(S2, L5, f'select(.arm=="{arm}")|.calls', "max"))
        row("5.2", f"{name}, median seconds per run",
            q(S2, L5, f'select(.arm=="{arm}")|.seconds', "sort|(.[19]+.[20])/2"))
        row("5.2", f"{name}, median reasoning characters per run",
            q(S2, L5, f'select(.arm=="{arm}")|.reasoning_chars', "sort|(.[19]+.[20])/2"))
        row("5.2", f"{name}, most reasoning characters in one run",
            q(S2, L5, f'select(.arm=="{arm}")|.reasoning_chars', "max"))
        row("5.2", f"{name}, runs ended by the call ceiling",
            q(S2, L5, f'select(.arm=="{arm}" and .fail_kind=="calls")'))
        row("5.2", f"{name}, runs ended by the seconds limit",
            q(S2, L5, f'select(.arm=="{arm}" and .fail_kind=="seconds")'))
    for arm, name in (("rq2c-pipeline", "pipeline"), ("rq2c-session", "session")):
        for field, label in (("tokens_in", "tokens in"), ("tokens_out", "tokens out")):
            row("5.2", f"{name}, {label} over the 40 runs, in millions to two decimals",
                q(S2, L5, f'select(.arm=="{arm}")|.{field}', "add/1000000*100|round/100"))
    row("5.2", "session, median tool calls per run",
        q(S2, L5, 'select(.arm=="rq2c-session")|.tool_calls', "sort|(.[19]+.[20])/2"), "6")
    row("5.2", "session, most tool calls in one run",
        q(S2, L5, 'select(.arm=="rq2c-session")|.tool_calls', "max"), "10")
    row("5.2", "failures on duration-python, both arms, at 5 of 6 checks",
        q(S2, L5, 'select(.task=="duration-python" and .checks_ok==5 and .checks_total==6)'), "8")
    row("5.2", "session failures on semver-go at 2 of 3 checks",
        q(S2, L5, 'select(.task=="semver-go" and .arm=="rq2c-session" and .outcome!="pass" and .checks_ok==2)'), "3")
    # The check line itself was raw record text in the body. These two rows say
    # what it said.
    row("5.2", "duration-python in the no-tools arm: runs whose hidden reject check passed, of five",
        f"jq -rs --rawfile S {S2} '[.[]|{SEL}|select(.task==\"duration-python\" and .arm==\"rq2c-pipeline\")|"
        f"select(.detail|test(\"hidden-rejects ok\"))]|length' {L5}", "2")
    row("5.2", "duration-python in the no-tools arm: strings the three failing runs accepted, fewest and most",
        f"jq -rs --rawfile S {S2} '[.[]|{SEL}|select(.task==\"duration-python\" and .arm==\"rq2c-pipeline\")|"
        f"(.detail|capture(\"hidden-rejects fail \\\\((?<n>[0-9]+) accepted\\\\)\")|.n|tonumber)]|"
        f"[(min|tostring),\"and\",(max|tostring)]|join(\" \")' {L5}", "1 and 2")
    row("5.2", "the one run the call ceiling ended: calls, seconds, checks",
        f"jq -r --rawfile S {S2} '{SEL}|select(.fail_kind==\"calls\")|"
        f"\"\\(.calls) calls, \\(.seconds) seconds, \\(.checks_ok) of \\(.checks_total) checks\"' {L5}",
        "24 calls, 829 seconds, 0 of 0 checks")
    row("5.2", "exact two-sided p for one discordant task",
        "python3 -c 'print(min(1.0, 2*0.5**1))'", "1.0")
    row("5.2", "the 40 (task, round) pairs: solved by both, by neither, by pipeline only, by session only",
        RQ2_PAIRS % ("'%d, %d, %d and %d' % (sum(1 for t,i,a,b in pr if a and b),"
                     "sum(1 for t,i,a,b in pr if not a and not b),"
                     "sum(1 for t,i,a,b in pr if a and not b),"
                     "sum(1 for t,i,a,b in pr if b and not a))"),
        "31, 4, 4 and 1")
    # The arm names in the record are pipeline and session; the paper describes the
    # arms as no tools and shell, so this row is emitted in the paper's words.
    row("5.2", "the (task, round) pairs that disagree, and the arm that won each",
        RQ2_PAIRS % ("'; '.join(t+' round '+str(i+1)+' to '+('no tools' if a else 'shell')"
                     " for t,i,a,b in pr if a!=b)"),
        "duration-python round 3 to no tools; duration-python round 5 to no tools; "
        "roman-python round 2 to shell; semver-go round 1 to no tools; "
        "semver-go round 4 to no tools")
    row("5.2", "exact two-sided p on the five discordant (task, round) pairs, 4 against 1",
        "python3 -c 'from math import comb; n=5; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
        "print(round(sum(x for x in p if x<=p[4]+1e-12),3))'", "0.375")

    # ---- 5.3
    row("5.3", "cells in the RQ3 round", f"wc -l < {S3}", "18")
    row("5.3", "runs in the RQ3 round", q(S3, L6, "."), "144")
    row("5.3", "runs that passed", q(S3, L6, 'select(.outcome=="pass")'), "97")
    row("9", "first and last shift record of the RQ3 round",
        f"jq -r --rawfile S {S3} 'select(.kind==\"shift.start\" or .kind==\"shift.end\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.iso' {L6} | sort | sed -n '1p;$p' | paste -sd' ' | awk '{{print $1, \"to\", $2}}'",
        "2026-09-05T19:23:16+02:00 to 2026-09-06T04:09:13+02:00")
    row("5.3", "runs whose virtual machine was destroyed, of 144",
        q(S3, L6, "select(.asserts.vms_destroyed)"), "144")
    for think in ("none", "low", "medium"):
        row("5.3", f"tasks solved at think {think}, of 48",
            q(S3, L6, f'select(.think=="{think}" and .outcome=="pass")'))
        # Section 4.1 states three outcomes, so every headline count carries the
        # denominator that leaves the limit-ended runs out.
        row("abstract, 5.3", f"think {think}, runs that reached a check, of 48",
            q(S3, L6, f'select(.think=="{think}" and .fail_kind==null)'))
    for think in ("none", "low", "medium"):
        row("5.3", f"runs ended by the call ceiling at think {think}",
            q(S3, L6, f'select(.think=="{think}" and .fail_kind=="calls")'))
        row("5.3", f"runs ended by the seconds limit at think {think}",
            q(S3, L6, f'select(.think=="{think}" and .fail_kind=="seconds")'))
    row("5.3", "runs ended by the call ceiling, all levels", q(S3, L6, 'select(.fail_kind=="calls")'), "11")
    row("5.3", "runs ended by the seconds limit, all levels", q(S3, L6, 'select(.fail_kind=="seconds")'), "7")
    for fam in ["deepseek-v4-flash:cloud", "glm-5.3-flash:cloud", "my/qwen-3.5-9b",
                "my/qwen-3.6-27b", "my/qwen-3.8-27b", "my/qwen-3.6-35b"]:
        for think in ("none", "low", "medium"):
            row("5.3", f"{fam} at think {think}, tasks solved of 8",
                q(S3, L6, f'select((.tier|sub("-nonthink";""))=="{fam}" and .think=="{think}" and .outcome=="pass")'))
    row("abstract, 5.3", "runs per think level",
        q(S3, L6, 'select(.think=="none")'), "48")
    row("5.3", "discordant pairs, none against low", pair_total_cmd("none", "low"), "13")
    row("5.3", "discordant pairs, low against medium", pair_total_cmd("low", "medium"), "11")
    row("5.3", "discordant pairs, none against medium", pair_total_cmd("none", "medium"), "8")
    row("5.3", "none against medium: pairs won only by none, then only by medium",
        pair_cmd("none", "medium"), "0 8")
    row("5.3", "none against low: pairs won only by none, then only by low",
        pair_cmd("none", "low"), "4 9")
    row("5.3", "low against medium: pairs won only by low, then only by medium",
        pair_cmd("low", "medium"), "4 7")
    row("5.3", "exact two-sided p, 0 of 8 discordant pairs one way",
        "python3 -c 'from math import comb; n=8; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
        "print(round(sum(x for x in p if x<=p[0]+1e-12),4))'", "0.0078")
    row("5.3", "exact two-sided p, 4 of 13 discordant pairs",
        "python3 -c 'from math import comb; n=13; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
        "print(round(sum(x for x in p if x<=p[4]+1e-12),3))'", "0.267")
    row("5.3", "exact two-sided p, 4 of 11 discordant pairs",
        "python3 -c 'from math import comb; n=11; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
        "print(round(sum(x for x in p if x<=p[4]+1e-12),3))'", "0.549")
    row("5.3", "families improving from none to medium, of six",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|{{f:(.tier|sub(\"-nonthink\";\"\")),t:.think,"
        f"p:(.outcome==\"pass\")}}]|group_by(.f)|map({{n:(map(select(.t==\"none\" and .p))|length),"
        f"m:(map(select(.t==\"medium\" and .p))|length)}})|map(select(.m>.n))|length' {L6}", "6")
    row("5.3", "sign test p, six of six moving one way", "python3 -c 'print(round(2*0.5**6,3))'", "0.031")

    # The subset where the budget is the only thing that moved. A locally served
    # model runs its cell of none under a second deployment with thinking
    # switched off in the chat template; a model at a provider takes the budget
    # as one field of the same request, so its three cells differ in that field
    # and in nothing else.
    row("5.3, 6", "outcomes at each budget that come from the four locally served models",
        q(S3, L6, 'select(.think=="none" and (.tier|startswith("my/")))'), "32")
    row("abstract, 5.3", "the two models at a provider, runs per budget",
        q(S3, L6, 'select((.tier|test("cloud")) and .think=="none")'), "16")
    for think in ("none", "low", "medium"):
        row("abstract, 5.3", f"the two models at a provider, tasks solved at think {think}, of 16",
            q(S3, L6, f'select((.tier|test("cloud")) and .think=="{think}" and .outcome=="pass")'))
    row("5.3", "the two models at a provider, runs that reached a check at think none, of 16",
        q(S3, L6, 'select((.tier|test("cloud")) and .think=="none" and .fail_kind==null)'), "15")
    row("5.3", "the two models at a provider, none against medium: pairs won only by none, then only by medium",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.tier|test(\"cloud\"))|"
        f"{{k:(.tier+\"|\"+.task),t:.think,p:(.outcome==\"pass\")}}]|group_by(.k)|"
        f"map({{a:(map(select(.t==\"none\"))[0].p),b:(map(select(.t==\"medium\"))[0].p)}})|"
        f"[(map(select(.a and (.b|not)))|length),(map(select(.b and (.a|not)))|length)]|join(\" \")' {L6}",
        "0 2")
    row("abstract, 5.3", "the two models at a provider, discordant pairs none against medium",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.tier|test(\"cloud\"))|"
        f"{{k:(.tier+\"|\"+.task),t:.think,p:(.outcome==\"pass\")}}]|group_by(.k)|"
        f"map({{a:(map(select(.t==\"none\"))[0].p),b:(map(select(.t==\"medium\"))[0].p)}})|"
        f"[(map(select(.a and (.b|not)))|length),(map(select(.b and (.a|not)))|length)]|add' {L6}",
        "2")
    row("abstract, 5.3", "exact two-sided p, 0 of 2 discordant pairs one way", exact_p(2, 0), "0.5")
    # The round-one derived table leaves the body. Its two numbers came from
    # different populations, the run log's call counter and the assistant rows
    # of the uploaded conversation, so their difference is not a count of calls
    # What survives is its size, in section 7.
    row("6", "rows in the derived file, one per RQ3 run", f"wc -l < {D}", "144")
    row("6", "runs whose conversation was read of 144",
        f"jq -rs '[.[]|select(.distinct_calls!=null)]|length' {D}", "137")
    row("6", "runs whose conversation carries more assistant rows than the log carries calls",
        f"jq -rs '[.[]|select(.distinct_calls!=null and .assistant_rows>.calls)]|length' {D}",
        "41")
    row("6", "runs whose conversation carried more distinct replies than the log carried calls",
        f"jq -rs '[.[]|select(.distinct_calls!=null and .distinct_calls>.calls)]|length' {D}",
        "3")
    # The wall-time table of 5.3 is quoted whole rather than one family of it: the
    # two steps of the scale do not go the same way, so one row is not the round.
    for fam in ["deepseek-v4-flash:cloud", "glm-5.3-flash:cloud", "my/qwen-3.5-9b",
                "my/qwen-3.6-27b", "my/qwen-3.6-35b", "my/qwen-3.8-27b"]:
        for think in ("none", "low", "medium"):
            row("5.3, figure", f"{fam} at think {think}, wall seconds over its eight runs",
                q(S3, L6, f'select((.tier|sub("-nonthink";""))=="{fam}" and .think=="{think}")|.wall_seconds', "add"))
    for think in ("none", "low", "medium"):
        row("abstract, 5.3", f"think {think}, wall seconds over all six families",
            q(S3, L6, f'select(.think=="{think}")|.wall_seconds', "add"))
    row("abstract, 5.3", "families whose low costs less wall time than none, of six",
        wall_dir_cmd("low", "none"), "5")
    row("abstract, 5.3", "families whose medium costs more wall time than none, of six",
        wall_dir_cmd("none", "medium"), "5")
    for think in ("none", "low", "medium"):
        row("5.3", f"think {think}, model calls over the 48 runs",
            q(S3, L6, f'select(.think=="{think}")|.calls', "add"))
        row("5.3", f"think {think}, runs the seconds limit did not end, of 48",
            q(S3, L6, f'select(.think=="{think}" and .fail_kind!="seconds")'))
        row("5.3", f"think {think}, calls per run over the runs the seconds limit did not end",
            q(S3, L6, f'select(.think=="{think}" and .fail_kind!="seconds")|.calls',
              "(add/length*100|round)/100"))
    row("5.3", "exact two-sided p had one of the eight discordant pairs gone the other way",
        "python3 -c 'from math import comb; n=8; p=[comb(n,i)*0.5**n for i in range(n+1)]; "
        "print(\"%.3f\" % sum(x for x in p if x<=p[1]+1e-12))'", "0.070")
    row("5.3, 6", "local cells with a usable idle sample, of twelve",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3} | grep '^{{' | jq -rs '[.[]|select(.cpu_watts>0)]|length'", "11")

    # ---- 5.4: the second round of RQ3, and the two rounds side by side.
    # Every row here reads the committed snapshot and the committed round-two
    # launcher log. Round one's rows above are left as they are.
    row("5.4", "cells in RQ3 round two", f"wc -l < {S3B}", "18")
    row("5.4", "runs in RQ3 round two", q(S3B, L6, "."), "144")
    row("9", "first and last shift record of RQ3 round two",
        f"jq -r --rawfile S {S3B} 'select(.kind==\"shift.start\" or .kind==\"shift.end\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.iso' {L6} | sort | sed -n '1p;$p' | paste -sd' ' "
        f"| awk '{{print $1, \"to\", $2}}'",
        "2026-09-06T14:16:29+02:00 to 2026-09-06T23:00:39+02:00")
    row("5.4", "cells of round two whose batch id ends in the same suffix as round one's, of eighteen",
        f"paste -d' ' <(sed 's/^[0-9-]*-rq3-/rq3-/' {S3}) <(sed 's/^[0-9-]*-rq3-/rq3-/' {S3B}) "
        f"| awk '$1==$2' | wc -l", "18")
    row("5.4", "RQ3 round two frozen envelope file and its sha256",
        f"jq -r --rawfile S {S3B} 'select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))|.frozen|.file+\" \"+.sha256' {L6} | sort -u",
        "rq3-2026-09-05.toml 4fe9e97b19286a9b64ab18ebca1f6cd23ca0b404745da80831de4865cbc2d7c0")
    row("5.4", "opening records of round two, all carrying that one file and hash",
        f"jq -rs --rawfile S {S3B} '[.[]|select(.kind==\"run.start\")|.shift as $s|"
        f"select(($S|split(\"\\n\"))|index($s))]|length' {L6}", "144")
    row("5.4", "distinct check versions over the round two runs",
        f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|.tests]|unique|join(\",\")' {L6}", "5d6f78a")
    row("5.4", "runs of round two whose virtual machine was destroyed, of 144",
        q(S3B, L6, "select(.asserts.vms_destroyed)"), "144")
    row("5.4", "the runner commit round two ran under",
        "grep -o '| runner commit | .40fa4cb. |' notes/950-rq3-r2.md | grep -o '40fa4cb'", "40fa4cb")
    row("5.4", "round two cells that printed 0 mismatch(es)", f"grep -c '0 mismatch(es)' {LOG3B}", "18")
    row("5.4", "mismatch lines in the round two log that were not zero",
        f"grep -o '[0-9]* mismatch(es)' {LOG3B} | grep -vc '^0 ' || true", "0")
    row("5.4", "runs of any other kind inside the round two window",
        f"grep -o '[0-9]* overlapping run(s)' {LOG3B} | grep -oE '^[0-9]+'", "0")
    row("5.4", "runs that passed in round two, of 144", q(S3B, L6, 'select(.outcome=="pass")'), "101")
    row("5.4", "outcomes recorded in round two",
        f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|.outcome]|unique|join(\", \")' {L6}",
        "fail:budget, fail:capability, fail:structural, pass",
        rid="rq3-r2-outcomes-recorded")
    for think in ("none", "low", "medium"):
        row("5.4", f"round two, tasks solved at think {think}, of 48",
            q(S3B, L6, f'select(.think=="{think}" and .outcome=="pass")'))
    row("5.4", "round two, runs ended by the seconds limit",
        q(S3B, L6, 'select(.fail_kind=="seconds")'), "6")
    row("5.4", "round two, runs the seconds limit ended on the mechanical limit of 300 seconds",
        q(S3B, L6, 'select(.fail_kind=="seconds" and .cls=="mechanical")'), "3")
    for think in ("none", "low", "medium"):
        row("5.4", f"round two, runs ended by the seconds limit at think {think}",
            q(S3B, L6, f'select(.think=="{think}" and .fail_kind=="seconds")'))
    row("5.4, r2 report", "round two, the runs the seconds limit ended, by cell and task",
        f"jq -r --rawfile S {S3B} '{SEL}|select(.fail_kind==\"seconds\")|"
        f"\"\\(.arm|sub(\"rq3-\";\"\")) \\(.task)\"' {L6} | sort | paste -sd';' | sed 's/;/; /g'")
    row("5.4, r2 report", "round two, the cells whose idle sample came back impossible",
        f"python3 {TABLE} --log {LOG3B} | awk '/^INVALID BASELINE/ {{print $3}}' "
        f"| sed 's/^[0-9]*-[0-9]*-rq3-/rq3-/' | paste -sd' ' | sed 's/ / and /'")
    row("5.4", "round two, seconds recorded by the runs the seconds limit ended, by task class",
        f"jq -r --rawfile S {S3B} '{SEL}|select(.fail_kind==\"seconds\")|\"\\(.cls) \\(.seconds)\"' {L6} "
        f"| sort | uniq -c | tr -s ' ' | paste -sd';'")
    row("5.4", "runs the round two log marks reasoning characters NOT MEASURED for",
        f"grep -o \"reasoning characters NOT MEASURED for \\[[^]]*\\]\" {LOG3B} "
        f"| grep -o \"'[^']*'\" | wc -l", "6")
    row("5.4", "round two, runs whose reasoning character count is null",
        q(S3B, L6, "select(.reasoning_chars==null)"), "6")
    row("5.4", "round two, runs ended by the call ceiling",
        q(S3B, L6, 'select(.fail_kind=="calls")'), "6")
    for think in ("none", "low", "medium"):
        row("5.4", f"round two, runs ended by the call ceiling at think {think}",
            q(S3B, L6, f'select(.think=="{think}" and .fail_kind=="calls")'))
    row("5.4", "round two, runs recorded as a structural failure",
        q(S3B, L6, 'select(.outcome=="fail:structural")'), "1")
    row("5.4", "the structural failure of round two: its cell, task and what the record says ended it",
        f"jq -r --rawfile S {S3B} '{SEL}|select(.outcome==\"fail:structural\")|"
        f"\"\\(.tier) at think \\(.think), \\(.task), fail_kind \\(.fail_kind)\"' {L6}")
    row("5.3, 5.4", "round one, runs recorded as a structural failure",
        q(S3, L6, 'select(.outcome=="fail:structural")'), "0")
    row("5.4", "round two, hello-go, passes over the eighteen cells",
        q(S3B, L6, 'select(.task=="hello-go" and .outcome=="pass")'), "18")
    row("5.4", "round two, split-module-python, passes over the eighteen cells",
        q(S3B, L6, 'select(.task=="split-module-python" and .outcome=="pass")'), "6")
    row("5.4", "round two, idle samples taken, one before each local cell",
        f"grep -c 'idle baseline: 300s, no VM' {LOG3B}", "12")
    row("5.4", "round two, local cells with a usable idle sample, of twelve",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3B} | grep '^{{' | jq -rs '[.[]|select(.cpu_watts>0)]|length'",
        "10")
    row("5.4", "round two, the idle samples that came back impossible, CPU watts",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3B} | grep '^{{' | jq -r 'select(.cpu_watts<0)|.cpu_watts' "
        f"| paste -sd' ' | sed 's/ / and /'", "-183.9 and -183.8")

    # The two rounds side by side, at cell level and at pair level.
    row("5.4", "pairs of a cell and a task, in each round", RQ3_ROUNDS % "len(ks)", "144")
    row("5.4", "cells whose pass count moved between the rounds, of eighteen",
        RQ3_ROUNDS % "sum(1 for c in o if ca[c]!=cb[c])", "11")
    row("5.4", "cells that passed more tasks in round two",
        RQ3_ROUNDS % "sum(1 for c in o if cb[c]>ca[c])", "8")
    row("5.4", "cells that passed fewer tasks in round two",
        RQ3_ROUNDS % "sum(1 for c in o if cb[c]<ca[c])", "3")
    row("5.4, r2 report", "the cells that moved, round one count to round two count",
        RQ3_ROUNDS % "'; '.join(c[4:]+' '+str(ca[c])+' to '+str(cb[c]) for c in o if ca[c]!=cb[c])")
    row("5.4", "the largest move by any cell between the rounds, in tasks",
        RQ3_ROUNDS % "max(abs(cb[c]-ca[c]) for c in o)", "2")
    row("5.4", "pairs that gave the same verdict in both rounds",
        RQ3_ROUNDS % "sum(1 for k in ks if a[k]==b[k])", "128")
    row("5.4", "pairs that passed in round one and failed in round two",
        RQ3_ROUNDS % "sum(1 for k in ks if a[k] and not b[k])", "6")
    row("5.4", "pairs that failed in round one and passed in round two",
        RQ3_ROUNDS % "sum(1 for k in ks if b[k] and not a[k])", "10")
    row("5.4", "pairs that flipped between the rounds, either way",
        RQ3_ROUNDS % "sum(1 for k in ks if a[k]!=b[k])", "16")
    row("5.4, r2 report", "the pairs that passed in round one and failed in round two",
        RQ3_ROUNDS % "'; '.join(k[0][4:]+' '+k[1] for k in ks if a[k] and not b[k])")
    row("5.4, r2 report", "the pairs that failed in round one and passed in round two",
        RQ3_ROUNDS % "'; '.join(k[0][4:]+' '+k[1] for k in ks if b[k] and not a[k])")
    for think in ("none", "low", "medium"):
        row("5.4, r2 report", f"pairs at think {think} that flipped, pass to fail then fail to pass",
            RQ3_ROUNDS % ("str(sum(1 for k in ks if lvl(k[0])=='%s' and a[k] and not b[k]))"
                          "+' '+str(sum(1 for k in ks if lvl(k[0])=='%s' and b[k] and not a[k]))"
                          % (think, think)))

    # Round two read on its own terms: the same paired reading section 5.3 makes.
    row("5.4", "round two, none against medium: pairs won only by none, then only by medium",
        pair_cmd("none", "medium", S3B), "3 8")
    row("5.4", "round two, pairs the smallest budget won and the largest lost",
        pair_cmd("none", "medium", S3B) + " | cut -d' ' -f1", "3")
    row("5.4", "round two, pairs the largest budget won and the smallest lost",
        pair_cmd("none", "medium", S3B) + " | cut -d' ' -f2", "8")
    row("5.4", "round one, pairs the largest budget won and the smallest lost",
        pair_cmd("none", "medium") + " | cut -d' ' -f2", "8")
    row("5.4", "round two, runs per think level", q(S3B, L6, 'select(.think=="none")'), "48")
    row("5.4", "round two, discordant pairs none against medium",
        pair_total_cmd("none", "medium", S3B), "11")
    row("5.4", "round two, exact two-sided p, 3 of 11 discordant pairs", exact_p(11, 3), "0.227")
    row("5.4, r2 report", "round two, none against low: pairs won only by none, then only by low",
        pair_cmd("none", "low", S3B), "6 9")
    row("5.4, r2 report", "round two, discordant pairs none against low",
        pair_total_cmd("none", "low", S3B), "15")
    row("5.4, r2 report", "round two, exact two-sided p, 6 of 15 discordant pairs", exact_p(15, 6), "0.607")
    row("5.4, r2 report", "round two, low against medium: pairs won only by low, then only by medium",
        pair_cmd("low", "medium", S3B), "2 4")
    row("5.4, r2 report", "round two, discordant pairs low against medium",
        pair_total_cmd("low", "medium", S3B), "6")
    row("5.4, r2 report", "round two, exact two-sided p, 2 of 6 discordant pairs", exact_p(6, 2), "0.688")
    row("5.4", "round two, models solving more from none to medium, of six",
        f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|{{f:(.tier|sub(\"-nonthink\";\"\")),t:.think,"
        f"p:(.outcome==\"pass\")}}]|group_by(.f)|map({{n:(map(select(.t==\"none\" and .p))|length),"
        f"m:(map(select(.t==\"medium\" and .p))|length)}})|map(select(.m>.n))|length' {L6}", "4")
    row("5.4", "round two, models solving fewer from none to medium, of six",
        f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|{{f:(.tier|sub(\"-nonthink\";\"\")),t:.think,"
        f"p:(.outcome==\"pass\")}}]|group_by(.f)|map({{n:(map(select(.t==\"none\" and .p))|length),"
        f"m:(map(select(.t==\"medium\" and .p))|length)}})|map(select(.m<.n))|length' {L6}", "0")
    row("5.4", "round two, models solving the same number at none and at medium, of six",
        f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|{{f:(.tier|sub(\"-nonthink\";\"\")),t:.think,"
        f"p:(.outcome==\"pass\")}}]|group_by(.f)|map({{n:(map(select(.t==\"none\" and .p))|length),"
        f"m:(map(select(.t==\"medium\" and .p))|length)}})|map(select(.m==.n))|length' {L6}", "2")
    row("5.4", "round two, sign test p on the four models that moved from none to medium",
        "python3 -c 'print(round(2*0.5**4,3))'", "0.125")

    # The repeated-reply counters, which round two's own records carry: written
    # by the executor over the calls the call counter counts, so numerator and
    # denominator are one population. This is the table section 5.3 reads, and
    # the round-one derived file is no longer a table in the paper at all.
    for think in ("none", "low", "medium"):
        row("5.3", f"round two, think {think}, runs carrying the reply counters, of 48",
            q(S3B, L6, f'select(.think=="{think}" and .distinct_calls!=null)'))
        row("5.3", f"round two, think {think}, calls over the runs carrying the counters",
            q(S3B, L6, f'select(.think=="{think}" and .distinct_calls!=null)|.calls', "add"))
        row("5.3", f"round two, think {think}, distinct replies over those runs",
            q(S3B, L6, f'select(.think=="{think}" and .distinct_calls!=null)|.distinct_calls', "add"))
        row("5.3", f"round two, think {think}, calls that repeated a reply the run had already sent",
            q(S3B, L6, f'select(.think=="{think}" and .distinct_calls!=null)|.repeat_calls', "add"))
        row("5.3", f"round two, think {think}, per cent of those calls that repeated a reply",
            f"jq -rs --rawfile S {S3B} '[.[]|{SEL}|select(.think==\"{think}\" and .distinct_calls!=null)]|"
            f"(map(.repeat_calls)|add)/(map(.calls)|add)*100|round' {L6}")
    row("5.3", "round two, runs carrying the reply counters, of 144",
        q(S3B, L6, 'select(.distinct_calls!=null)'), "138")
    row("5.3", "round two, fewest distinct replies in a run that spent the whole 24-call ceiling",
        q(S3B, L6, 'select(.calls==24 and .distinct_calls!=null)|.distinct_calls', "min"), "1")

    # One row per cell of round two, each the row the round-two report prints.
    for shift in Path(S3B).read_text().split():
        cell_id = shift.split("-", 2)[2][len("rq3-"):]
        row("5.4, r2 report",
            f"round two, cell {cell_id}: passes, calls, seconds, net Wh, runs cut on the seconds limit",
            cell_line(shift), rid=f"rq3-r2-cell-{cell_id}")

    # ---- 6
    row("6", "hello-go, passes over the eighteen cells",
        q(S3, L6, 'select(.task=="hello-go" and .outcome=="pass")'), "18")
    row("6", "split-module-python, passes over the eighteen cells",
        q(S3, L6, 'select(.task=="split-module-python" and .outcome=="pass")'), "6")
    row("6", "families passing split-module-python at all three levels",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.task==\"split-module-python\")|"
        f"{{f:(.tier|sub(\"-nonthink\";\"\")),p:(.outcome==\"pass\")}}]|group_by(.f)|"
        f"map(select(all(.[];.p)))|length' {L6}", "2")
    row("5.3", "my/qwen-3.5-9b runs that spent the whole 24-call ceiling",
        q(S3, L6, 'select((.tier|sub("-nonthink";""))=="my/qwen-3.5-9b" and .fail_kind=="calls")'), "5")
    for fam in ["glm-5.3-flash:cloud", "deepseek-v4-flash:cloud"]:
        row("6", f"{fam}, duration-python passes over its three cells",
            q(S3, L6, f'select((.tier|sub("-nonthink";""))=="{fam}" and .task=="duration-python" '
                      'and .outcome=="pass")'))
    row("6", "the idle sample that came back impossible, CPU watts",
        f"grep -A1 'idle baseline: 300s, no VM' {LOG3} | grep '^{{' | jq -r 'select(.cpu_watts<0)|.cpu_watts'", "-183.8")
    row("6", "implied mean CPU watts over the 144 runs, lowest and highest",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.wh_cpu!=null)|(.wh_cpu*3600/.wall_seconds)]|"
        f"[(min|floor|tostring),\"and\",(max|ceil|tostring)]|join(\" \")' {L6}", "35 and 58")
    row("6", "closing records anywhere in either snapshot with a negative energy figure",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and .wh!=null and .wh<0)]|length' {L6}", "0")
    # A corrected wrap on a run row cannot show up as a negative figure, so the
    # row above is a check on the baseline path and not on the run path. What
    # bears on the run path is the wattage each cell implies.
    row("6", "implied watts of the local cell with the largest gross figure",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.tier|startswith(\"my/\"))|"
        f"{{s:.shift,wh:.wh,ws:.wall_seconds}}]|group_by(.s)|"
        f"map((map(.wh)|add)*3600/(map(.ws)|add))|max*10|round/10' {L6}", "372.8")
    row("6", "implied watts of the other eleven local cells, lowest and highest",
        f"jq -rs --rawfile S {S3} '[.[]|{SEL}|select(.tier|startswith(\"my/\"))|"
        f"{{s:.shift,wh:.wh,ws:.wall_seconds}}]|group_by(.s)|"
        f"map((map(.wh)|add)*3600/(map(.ws)|add))|sort|.[0:-1]|"
        f"[((.[0]*10|round/10)|tostring),\"and\",((.[-1]*10|round/10)|tostring)]|join(\" \")' {L6}",
        "217.4 and 320")
    row("6", "RQ3 runs whose reasoning character count is null",
        q(S3, L6, "select(.reasoning_chars==null)"), "7")
    row("6", "of those, the ones at think medium",
        q(S3, L6, 'select(.reasoning_chars==null and .think=="medium")'), "6")
    row("6", "discarded RQ2 set A, pipeline runs solved of 40",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.arm|startswith(\"rq2-pipeline-r\")) and .outcome==\"pass\")]|length' {L5}", "31")
    row("6", "discarded RQ2 set A, session runs solved of 40",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.arm|startswith(\"rq2-session-r\")) and .outcome==\"pass\")]|length' {L5}", "20")
    row("6", "discarded RQ2 set A, session runs ended by the call ceiling",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.arm|startswith(\"rq2-session-r\")) and .fail_kind==\"calls\")]|length' {L5}", "16")
    row("6", "discarded RQ2 set A, pipeline runs ended by the call ceiling",
        f"jq -rs '[.[]|select(.kind==\"run.end\" and (.arm|startswith(\"rq2-pipeline-r\")) and .fail_kind==\"calls\")]|length' {L5}", "3")

    # ---- 7
    for path in (L5, L6, D, LOG3, LOG2, S2, S3, LOG3B, S3B):
        row("7", f"sha256 of {path}", f"sha256sum {path} | cut -d' ' -f1")
    # The four notes section 5.1 rests on: hashed here because the paper hashes
    # what it takes a number from, and these are where section 5.1's come from.
    for path in ("notes/950-l1-adjudication.md", "notes/950-judge-v4.md",
                 "notes/950-round-zero.md", "notes/950-research.md"):
        row("7", f"sha256 of {path}", f"sha256sum {path} | cut -d' ' -f1")
    row("4.8", "the later snapshot holds the earlier one as a byte-for-byte prefix",
        f"head -c $(stat -c%s {L5}) {L6} | cmp -s - {L5} && echo PREFIX-OK", "PREFIX-OK")


SRC = "paper.src.md"


def label_round_two():
    """Section 5.4's rows are read by two documents: the paper, and the note
    notes/950-rq3-r2.md, which carries the round cell by cell and takes every
    number in it from this appendix by id. A row the paper source does not spend
    is relabelled `r2 report`, so that the linter's unused-number warning keeps
    its meaning: an id no reader of this appendix spends is still a mistake, and
    one only the note spends says so in its own section column."""
    spent = {name for name, _, _ in tokens(Path(SRC).read_text())}
    for i, (rid, section, what, cmd, expect) in enumerate(ROWS):
        if section.startswith("5.4"):
            ROWS[i] = (rid, "5.4" if rid in spent else "r2 report", what, cmd, expect)


# The file the mechanism table is built from. Round two's executor writes the
# reply counters into the closing record, so they live in the same snapshot as
# every other row of that round; the check reads every row of it that carries
# them, which is a superset of the round and costs nothing extra.
RQ3B_ROWS = L6


def impossible_rows(path):
    """Rows of a reply-counter file where the distinct replies outnumber the
    calls. Both counters are written by the executor over the same calls, so a
    row like that cannot happen; when one does, the two numbers were taken over
    different populations and their difference counts nothing. Round one's
    derived file has three of them, which is why the paper's mechanism table is
    round two's records and why this runs before the table is built.
    """
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("kind") not in (None, "run.end"):
            continue
        if r.get("distinct_calls") is not None and r["distinct_calls"] > r["calls"]:
            out.append(r)
    return out


def assert_no_impossible_row(path):
    """Exit non-zero, naming the rows, when a reply-counter file carries one."""
    bad = impossible_rows(path)
    if not bad:
        print(f"{path}: no row carries more distinct replies than calls")
        return 0
    print(f"IMPOSSIBLE ROWS IN {path}: {len(bad)} carry more distinct replies than calls, "
          "so the two counters did not run over the same calls")
    for r in bad[:10]:
        print(f"  {r.get('run', '?')}: {r['calls']} calls, {r['distinct_calls']} distinct")
    return 1


def run(cmd):
    r = subprocess.run(["bash", "-o", "pipefail", "-c", cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed ({r.returncode}): {cmd}\n{r.stderr}")
    return r.stdout.strip()


def cell(s):
    return escape(s)


HEADER = """# Numbers in the paper, and the command that re-derives each one

One row per number quoted in [paper.md](paper.md). Run every command from the root of this repository, the directory this file is in, in a POSIX shell, with `jq`, coreutils and `git` on the path. The pipe characters inside the command column are written `\\|` so that the table renders; copy them back to `|` when you run one.

The `id` column binds a number to the paper: the paper source writes each number as `{{num:<id>}}` and `tools/render.py paper.src.md numbers.md paper.md` substitutes it, so a larger run updates the paper by regenerating this file and re-rendering rather than by retyping.

Every ledger query selects the runs of one question by that question's committed shift list rather than by a date range, because the snapshots also hold other work from the same days. This file is generated by `actions/950-paper-numbers.py`, which runs every command below and writes its output into the number column, so no number here can disagree with its own command. `python3 actions/950-paper-numbers.py --check` re-runs them all against this file.

| id | number | section | source file | what it is | command |
|---|---|---|---|---|---|"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="re-run every command against the committed file instead of rewriting it")
    ap.add_argument("--assert-rows", metavar="FILE",
                    help="check one reply-counter file for rows where the distinct replies "
                         "outnumber the calls, and exit non-zero if any exists")
    args = ap.parse_args()
    if args.assert_rows:
        return assert_no_impossible_row(args.assert_rows)

    # The mechanism table of section 5.3 is built from round two's closing
    # records. Before any of it is written, the rows that would be impossible if
    # its two counters came from different populations are checked for.
    if assert_no_impossible_row(RQ3B_ROWS):
        return 1

    build()
    label_round_two()

    seen = {}
    for rid, section, what, _, _ in ROWS:
        if rid in seen:
            sys.exit(f"DUPLICATE ID: {rid}\n  {seen[rid]}\n  {section}: {what}\n"
                     "  pass rid= to one of the two rows; an id names one number")
        seen[rid] = f"{section}: {what}"

    results = []
    for rid, section, what, cmd, expect in ROWS:
        got = run(cmd)
        if expect is not None and got != expect:
            sys.exit(f"MISMATCH: {what}\n  command: {cmd}\n  expected {expect!r}\n  got      {got!r}")
        results.append((rid, section, what, got, cmd))

    if args.check:
        rows = parse(Path(OUT).read_text())
        misses = 0
        for rid, section, what, got, cmd in results:
            committed = rows.get(rid)
            if committed is None:
                print(f"NOT IN {OUT}: no row with id {rid} ({what})")
                misses += 1
            elif committed["number"] != got or committed["section"] != section:
                print(f"DISAGREES IN {OUT}: {rid}: committed "
                      f"{committed['number']!r} in section {committed['section']!r}, "
                      f"command gives {got!r} in section {section!r}")
                misses += 1
        for rid in rows:
            if rid not in seen:
                print(f"STALE IN {OUT}: id {rid} is no longer generated")
                misses += 1
        print(f"{len(results)} rows checked, {misses} disagree with {OUT}")
        return 1 if misses else 0

    lines = [HEADER]
    for rid, section, what, got, cmd in results:
        source = re.findall(r"(evidence/[^\s')]+|notes/[^\s')]+\.md)", cmd)
        src = ", ".join(f"`{s}`" for s in dict.fromkeys(source)) or "computed"
        lines.append(f"| {rid} | {cell(got)} | {cell(section)} | {src} | {cell(what)} | "
                     f"`{cell(cmd)}` |")
    Path(OUT).write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}, {len(results)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
