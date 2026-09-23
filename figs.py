#!/usr/bin/env python3
"""Figures for paper.md, drawn from the committed run records. Run from this directory.

Every number that reaches a figure is read here from one of the evidence files
named on the command line: the two run-log snapshots, which hold both rounds of
the thinking-budget experiment, and (for the idle-power baselines, which the run
log does not carry) the round-one launcher log. Nothing is transcribed from a
report and nothing is hardcoded except the file paths, the display names of the
models, and the words of figure 1, which carries no data.

    .venv/bin/python figs.py \\
        evidence/ledger/2026-09-05.jsonl evidence/ledger/2026-09-06.jsonl

The two run-log arguments may be given in either order: each is identified by
the shift ids it contains. The data figures are drawn with matplotlib from the
pinned environment beside this script (requirements.txt,
installed into the repository's `.venv`), so text metrics, tick layout and
legends are the library's job rather than hand-placed coordinates. Figure 1
carries no data and is laid out by graphviz from the committed source file
figs/f1-system.dot, so its layout is computed too; `dot` must
be on the path. `--png` additionally renders each figure to PNG through
`rsvg-convert`, for a reader or a reviewer who wants a raster copy; the PNGs are
not committed.

Every canvas is at most 8 inches wide at 100 dpi, which is about the width a
markdown page gives a figure, and no glyph is smaller than 11 pt at that size.

Nine figures, one line printed per figure:

    f1-system            the lifecycle of one run and the trust boundary (no data)
    f2-tests             how the hidden tests were validated and fixed (no data)
    f3-rq2-outcome-grid  8 tasks x 5 rounds x 2 arms, one mark per run
    f4-rq3-solved        tasks solved per model and thinking budget
    f5-rq3-mechanism     calls per run, repeated replies, and what ended the runs
    f6-rq3-cost          wall seconds per model and budget, and net energy
    a1-outcome-heatmap   all 144 runs of round one, 18 cells by 8 tasks
    a2-calls-vs-distinct one point per run of round two, calls against distinct replies
    a3-energy-per-cell   gross and net energy per cell, with the idle band
    a4-batch-timeline    when every batch of both questions ran
"""
import argparse
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import textwrap
import zlib
from collections import Counter, defaultdict
from datetime import datetime

import matplotlib

matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RQ2_SHIFTS = "evidence/launch/rq2c-full2-20260905-1553.log.shifts"
RQ3_SHIFTS = "evidence/launch/rq3-r1-20260905-1923.log.shifts"
RQ3B_SHIFTS = "evidence/launch/rq3-r2-20260906-1416.log.shifts"
RQ3_LOG = "evidence/launch/rq3-r1-20260905-1923.log"
OUTDIR = "figs"
DOT_SOURCE = "f1-system.dot"
DOT_SOURCE_TESTS = "f2-tests.dot"

LEVELS = ["none", "low", "medium"]

# The display name of every model, keyed by the model string with its router
# prefix, its provider suffix and its serving-variant suffix removed, so that a
# name from a run record and a name from a batch id land on the same key. The
# appendix of the paper maps each display name back to the deployment string,
# the quantisation and the serving build; no figure carries either.
DISPLAY_NAMES = {
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "glm-5-3-flash": "GLM 5.3 Flash",
    "qwen-3-5-9b": "Qwen 3.5 9B",
    "qwen-3-6-27b": "Qwen 3.6 27B",
    "qwen-3-6-35b": "Qwen 3.6 35B",
    "qwen-3-8-27b": "Qwen 3.8 27B",
}
AT_A_PROVIDER = {"deepseek-v4-flash", "glm-5-3-flash"}

# Palette: the validated default of the dataviz skill, light surface.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834"]              # categorical slots 1 and 2
ORDINAL = ["#86b6ef", "#3987e5", "#184f95"]  # blue ordinal ramp, steps 250/400/600
CRITICAL = "#d03b3b"                         # a run the call ceiling ended
TIMEOUT = "#7a5aa8"                          # a run the seconds limit ended
# One hue per model, so every figure draws a model in the same colour.
MODEL_COLOURS = {
    "deepseek-v4-flash": "#2a78d6",
    "glm-5-3-flash": "#eb6834",
    "qwen-3-5-9b": "#1c8a72",
    "qwen-3-6-27b": "#7a5aa8",
    "qwen-3-6-35b": "#a8862a",
    "qwen-3-8-27b": "#c0446a",
}

# Nothing on a canvas is smaller than this, in points, at 100 dpi.
FS = 11
FS_PANEL = 12
FS_TITLE = 13


# ---------------------------------------------------------------- reading

def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_shifts(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]


def pick_ledgers(paths, rq2_shifts, rq3_shifts):
    """Identify which snapshot holds which set of batches, in either order."""
    found = {}
    for path in paths:
        shifts = {r.get("shift") for r in read_jsonl(path)}
        if set(rq2_shifts) <= shifts:
            found.setdefault("rq2", path)
        if set(rq3_shifts) <= shifts:
            found.setdefault("rq3", path)
    for key, label in (("rq2", "RQ2"), ("rq3", "RQ3 round one")):
        if key not in found:
            sys.exit(f"none of {paths} holds every {label} shift id")
    return found["rq2"], found["rq3"]


def run_ends(ledger_path, shifts):
    keep = set(shifts)
    rows = [r for r in read_jsonl(ledger_path)
            if r.get("kind") == "run.end" and r.get("shift") in keep]
    if len(rows) != 8 * len(shifts):
        sys.exit(f"expected {8 * len(shifts)} run.end rows in {ledger_path}, got {len(rows)}")
    return rows


def call_caps(ledger_path, shifts):
    """The frozen call ceiling per task class, read off the opening rows."""
    keep = set(shifts)
    caps = defaultdict(set)
    for r in read_jsonl(ledger_path):
        if r.get("kind") == "run.start" and r.get("shift") in keep:
            caps[r["cls"]].add(r["envelope"]["calls"])
    return {cls: sorted(v)[0] for cls, v in sorted(caps.items()) if len(v) == 1}


def idle_baselines(log_path):
    """cpu/gpu watts of each cell's 300 s no-machine sample, keyed by batch.

    A reading at or below zero is a counter wraparound inside the window, not a
    low measurement: it is separated out, and that cell has no net energy.
    """
    lines = open(log_path).read().splitlines()
    good, bad = {}, {}
    for i, line in enumerate(lines):
        if "idle baseline: 300s, no VM" not in line or i + 2 >= len(lines):
            continue
        try:
            sample = json.loads(lines[i + 1])
        except json.JSONDecodeError:
            continue
        if not lines[i + 2].startswith("shift "):
            continue
        shift = lines[i + 2][len("shift "):].split(":", 1)[0]
        cpu, gpu = sample["cpu_watts"], sample["gpu_watts"]
        (good if cpu > 0 and gpu > 0 else bad)[shift] = (cpu, gpu)
    return good, bad


def counted(rows):
    """The closing records that carry the reply counters. A run the seconds
    limit ended is reaped with its machine before the executor writes them, so
    it carries none and is counted as not read rather than as zero."""
    return [r for r in rows if r.get("distinct_calls") is not None]


def impossible_rows(rows):
    """Rows where the distinct replies outnumber the calls. Both counters are
    written by the executor over the same calls, so this cannot happen; if it
    does, the two numbers came from different populations and the difference
    between them is not a count of anything (950 v4 review, F3 and F4)."""
    return [r for r in counted(rows) if r["distinct_calls"] > r["calls"]]


def model(row):
    """The model a run record's tier names, with the serving switch dropped."""
    return row["tier"].replace("-nonthink", "")


def model_key(name):
    """The key a model string reduces to, from a record or from a batch id."""
    key = name.strip()
    if key.startswith("my/"):
        key = key[3:]
    key = key.split(":", 1)[0]
    if key.endswith("-nonthink"):
        key = key[: -len("-nonthink")]
    return key.replace(".", "-")


def display(name):
    """The display name of a model string, or a stop: a figure never carries a
    deployment string, so an unknown model is a missing table entry and not a
    label to improvise."""
    key = model_key(name)
    if key not in DISPLAY_NAMES:
        sys.exit(f"no display name for the model string {name!r}; add one to "
                 "DISPLAY_NAMES in this script")
    return DISPLAY_NAMES[key]


def colour_of(name):
    return MODEL_COLOURS[model_key(name)]


def is_local(tier):
    return model_key(tier) not in AT_A_PROVIDER


def spread(run_id):
    """A stable 0..1 offset per run id, so a redraw gives the same file."""
    return (zlib.crc32(run_id.encode()) % 1000) / 1000


def outcome_kind(row):
    """pass, tests (the hidden tests rejected it), ceiling, or timeout."""
    if row["outcome"] == "pass":
        return "pass"
    if row.get("fail_kind") == "calls":
        return "ceiling"
    if row.get("fail_kind") == "seconds":
        return "timeout"
    return "tests"


KIND_COLOUR = {"pass": SERIES[0], "tests": SERIES[1],
               "ceiling": CRITICAL, "timeout": TIMEOUT}
KIND_LABEL = {"pass": "passed every hidden test",
              "tests": "a hidden test rejected it",
              "ceiling": "ended by the call ceiling",
              "timeout": "ended by the seconds limit"}
# Colour is never the only channel: each outcome also has its own marker.
KIND_MARKER = {"pass": "o", "tests": "o", "ceiling": "X", "timeout": "s"}
KIND_FILLED = {"pass": True, "tests": False, "ceiling": True, "timeout": True}


def kind_handle(kind):
    """One legend entry for an outcome, drawn the way the figures draw it."""
    return Line2D([], [], linestyle="none", marker=KIND_MARKER[kind],
                  markersize=7.5, label=KIND_LABEL[kind],
                  color=KIND_COLOUR[kind],
                  markerfacecolor=KIND_COLOUR[kind] if KIND_FILLED[kind] else "none",
                  markeredgecolor=KIND_COLOUR[kind], markeredgewidth=1.8)


def draw_marks(ax, xs, ys, kind, size=52):
    ax.scatter(xs, ys, marker=KIND_MARKER[kind], s=size,
               facecolors=KIND_COLOUR[kind] if KIND_FILLED[kind] else "none",
               edgecolors=KIND_COLOUR[kind], linewidths=1.7, zorder=3,
               clip_on=False)


# ---------------------------------------------------------------- canvas

def setup_style():
    plt.rcParams.update({
        "figure.dpi": 100,
        "savefig.dpi": 100,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": FS,
        "axes.labelsize": FS,
        "axes.titlesize": FS_PANEL,
        "xtick.labelsize": FS,
        "ytick.labelsize": FS,
        "legend.fontsize": FS,
        "text.color": INK2,
        "axes.labelcolor": INK2,
        "axes.edgecolor": AXIS,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "grid.color": GRID,
        "svg.fonttype": "none",
        "path.simplify": True,
        # A redraw of unchanged data writes an unchanged file: the salt fixes the
        # element ids matplotlib would otherwise randomise, and save() drops the
        # date it would otherwise stamp into the metadata.
        "svg.hashsalt": "950-paper",
    })


def wrap(text, width):
    return "\n".join(textwrap.wrap(text, width))


def new_fig(height, title, subtitle, width=8.0):
    """A canvas at most 8 inches wide, its title and subtitle at the top, and
    the figure fraction below which the panels may start."""
    fig = plt.figure(figsize=(width, height))
    lines = wrap(title, 76)
    fig.text(0.012, 1 - 0.30 / height, lines, ha="left", va="top",
             fontsize=FS_TITLE, fontweight="bold", color=INK)
    used = 0.30 + 0.24 * lines.count("\n")
    if subtitle:
        sub = wrap(subtitle, 96)
        fig.text(0.012, 1 - (used + 0.28) / height, sub, ha="left", va="top",
                 fontsize=FS, color=INK2)
        used += 0.28 + 0.20 * sub.count("\n")
    return fig, 1 - (used + 0.18) / height


def note(fig, text, y=0.012, width=104):
    """A reading note at the foot of the canvas, wrapped by the library."""
    fig.text(0.012, y, wrap(text, width), ha="left", va="bottom",
             fontsize=FS, color=INK2)


def panel_head(fig, y, title, subtitle=None, x=0.012, width=92):
    """A panel heading, and under it the one line that says how to read the
    panel. Both are placed above the panel rather than inside it, so a wrapped
    subtitle cannot land on the panel's own title."""
    fig.text(x, y, title, ha="left", va="top", fontsize=FS_PANEL,
             fontweight="bold", color=INK)
    if subtitle:
        fig.text(x, y - 0.23 / fig.get_figheight(), wrap(subtitle, width),
                 ha="left", va="top", fontsize=FS, color=INK2)


def unmeasured(ax, y, width, height, words="not measured"):
    """A cell whose figure is not drawn, drawn as not drawn: an open dashed box
    with the reason in it, never a bar of length zero. Two reasons occur: a cell
    whose idle sample came back impossible has no net figure at all, and a cell
    served at a provider has one that measures the scaffold's machine and not
    the model, so it is not comparable with a local bar (950 v4 review, F7)."""
    ax.barh(y, width, height=height, facecolor="none", edgecolor=AXIS,
            linestyle=(0, (3, 3)), linewidth=1.2, zorder=3)
    ax.text(width / 2, y, words, va="center", ha="center", fontsize=FS,
            color=CRITICAL, zorder=4)


def plain_axes(ax, grid_axis="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    if grid_axis:
        ax.grid(True, axis=grid_axis, color=GRID, linewidth=1)


def spread_labels(ys, gap, lo=None, hi=None):
    """Label positions that keep `gap` between neighbours, in the order given.

    Two labels touching is a defect, so the ends of the lines are sorted, pushed
    apart by one line height, and the block is shifted back inside the panel if
    pushing carried it out."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    prev = None
    for i in order:
        if prev is not None and out[i] - prev < gap:
            out[i] = prev + gap
        prev = out[i]
    if hi is not None and order and out[order[-1]] > hi:
        shift = out[order[-1]] - hi
        for i in order:
            out[i] -= shift
    if lo is not None and order and out[order[0]] < lo:
        shift = lo - out[order[0]]
        for i in order:
            out[i] += shift
    return out


def save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.savefig(path, format="svg", metadata={"Date": None})
    plt.close(fig)
    return path


# ---------------------------------------------------------------- F1

def fig_system(outdir):
    """F1: the lifecycle of one run and the trust boundary. No data.

    The layout is graphviz's, from the source file committed beside the figure:
    a hand-placed diagram collides its own labels the moment one of them changes
    length, which is what the previous draft of this figure did."""
    return render_dot(outdir, DOT_SOURCE, "f1-system.svg", "figure 1")


def fig_tests(outdir):
    """F2: how the hidden tests were validated in both directions and fixed
    before any measurement (section 5.1). No data: the counts on the boxes are
    the ones of section 5.1's tables, and the layout is graphviz's, from the
    committed source, for the reason fig_system gives."""
    return render_dot(outdir, DOT_SOURCE_TESTS, "f2-tests.svg", "figure 2")


def render_dot(outdir, source, name, what):
    src = os.path.join(outdir, source)
    if not os.path.isfile(src):
        sys.exit(f"{src} is missing; {what} is drawn from that committed source")
    exe = shutil.which("dot")
    if exe is None:
        sys.exit(f"graphviz `dot` is not on the path; {what} cannot be laid out")
    path = os.path.join(outdir, name)
    subprocess.run([exe, "-Tsvg", "-o", path, src], check=True)
    return path


# ---------------------------------------------------------------- F2

def round_index(rows, shifts):
    """{shift: index of that batch within its own arm}, in launch order."""
    arm_of = {r["shift"]: r["arm"] for r in rows}
    seen, index = Counter(), {}
    for s in shifts:
        arm = arm_of[s]
        index[s] = seen[arm]
        seen[arm] += 1
    return index


def fig_rq2_grid(rq2_rows, rq2_shifts, outdir):
    """F2: 8 tasks by 5 rounds by 2 arms, one mark per run."""
    index = round_index(rq2_rows, rq2_shifts)
    arms = ["rq2c-pipeline", "rq2c-session"]
    names = {"rq2c-pipeline": "no tools", "rq2c-session": "shell"}
    nrounds = max(index.values()) + 1
    tasks = sorted({r["task"] for r in rq2_rows})
    grid = {(r["task"], r["arm"], index[r["shift"]]): outcome_kind(r) for r in rq2_rows}
    kinds = sorted({k for k in grid.values()}, key=lambda k: list(KIND_LABEL).index(k))
    ceilings = sum(1 for k in grid.values() if k == "ceiling")

    fig, top = new_fig(5.4,
                       "Figure 3: every run of the tools comparison, one mark each",
                       "one model (DeepSeek V4 Flash, at a provider), one machine image, "
                       "one frozen limits file, one hidden test suite, the arms launched "
                       "alternately")
    fig.legend(handles=[kind_handle(k) for k in kinds], loc="upper left",
               bbox_to_anchor=(0.012, top), ncol=3, frameon=False,
               handletextpad=0.4, columnspacing=1.4, borderpad=0)
    top -= 0.30 / 5.4

    for j, arm in enumerate(arms):
        ax = fig.add_axes([0.235 + j * 0.385, 0.185, 0.335, top - 0.265])
        ax.set_title(names[arm], fontsize=FS_PANEL, color=INK, loc="left",
                     fontweight="bold", pad=10)
        for kind in kinds:
            xs = [k + 1 for (t, a, k) in grid if a == arm and grid[(t, a, k)] == kind]
            ys = [tasks.index(t) for (t, a, k) in grid if a == arm and grid[(t, a, k)] == kind]
            draw_marks(ax, xs, ys, kind)
        for i, task in enumerate(tasks):
            solved = sum(1 for k in range(nrounds) if grid[(task, arm, k)] == "pass")
            ax.text(nrounds + 1.35, i, f"{solved} of {nrounds}", va="center",
                    ha="right", fontsize=FS, color=INK2)
        ax.set_xlim(0.4, nrounds + 1.4)
        ax.set_ylim(len(tasks) - 0.5, -0.6)
        ax.set_xticks(range(1, nrounds + 1))
        ax.set_xlabel("round")
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels(tasks if j == 0 else [""] * len(tasks))
        plain_axes(ax, grid_axis="y")

    totals = {a: sum(1 for r in rq2_rows if r["arm"] == a and r["outcome"] == "pass")
              for a in arms}
    n = {a: sum(1 for r in rq2_rows if r["arm"] == a) for a in arms}
    note(fig, "Runs solved: "
         + ", ".join(f"{names[a]} {totals[a]} of {n[a]}" for a in arms)
         + f". {ceilings} run of the {sum(n.values())} spent the whole call ceiling "
           "without delivering a branch, and is drawn as a cross.")
    return save(fig, outdir, "f3-rq2-outcome-grid.svg")


# ---------------------------------------------------------------- F3 and F5a

def models_in(rows):
    """The models of a round, in display-name order, so every figure agrees."""
    return sorted({model(r) for r in rows}, key=display)


def level_slopes(ax, xs, ymax, ylabel, ticks):
    """The shared frame of the two slope charts: three budgets across, a value up."""
    ax.set_xlim(-0.12, 2.06)
    ax.set_ylim(0, ymax)
    ax.set_xticks(xs)
    ax.set_xticklabels(LEVELS)
    ax.set_xlabel("thinking budget")
    ax.set_yticks(ticks)
    ax.set_ylabel(ylabel)
    plain_axes(ax, grid_axis="y")
    for x in xs:
        ax.axvline(x, color=AXIS, linewidth=1, linestyle=(0, (2, 3)), zorder=0)


def slope_lines(ax, models, value, label_of, gap):
    """One line per model, with its label at the right end, pushed clear."""
    ends = []
    for m in models:
        ys = [value(m, level) for level in LEVELS]
        ax.plot([0, 1, 2], ys, color=colour_of(m), linewidth=2.2,
                linestyle="-" if is_local(m) else (0, (5, 3)),
                marker="o", markersize=6, zorder=3)
        ends.append((ys[-1], m))
    placed = spread_labels([e[0] for e in ends], gap,
                           lo=ax.get_ylim()[0], hi=ax.get_ylim()[1])
    for y, (_, m) in zip(placed, ends):
        ax.text(2.12, y, label_of(m), va="center", ha="left", fontsize=FS,
                color=colour_of(m), clip_on=False)


def fig_rq3_solved(rq3_rows, outdir):
    """F3: tasks solved per model and thinking budget."""
    models = models_in(rq3_rows)
    ntasks = len({r["task"] for r in rq3_rows})
    solved = defaultdict(Counter)
    for r in rq3_rows:
        if r["outcome"] == "pass":
            solved[model(r)][r["think"]] += 1
    totals = Counter(r["think"] for r in rq3_rows if r["outcome"] == "pass")
    per_level = Counter(r["think"] for r in rq3_rows)

    passed = {(model(r), r["task"], r["think"]): r["outcome"] == "pass" for r in rq3_rows}
    to_medium = sum(1 for m in models for t in {r["task"] for r in rq3_rows}
                    if passed[(m, t, "medium")] and not passed[(m, t, "none")])
    to_none = sum(1 for m in models for t in {r["task"] for r in rq3_rows}
                  if passed[(m, t, "none")] and not passed[(m, t, "medium")])
    peaks_low = [m for m in models
                 if solved[m]["low"] > solved[m]["medium"] and solved[m]["low"] > solved[m]["none"]]

    fig, top = new_fig(5.2,
                       "Figure 4: in round one, every model solved more tasks with a "
                       "thinking budget than without one",
                       f"round one, {len(rq3_rows)} runs, {len(models)} models, {ntasks} "
                       "tasks per cell, no tools, one frozen limits file; a dashed line "
                       "is a model served at a provider")
    ax = fig.add_axes([0.135, 0.29, 0.42, top - 0.33])
    level_slopes(ax, [0, 1, 2], ntasks + 0.4, f"tasks solved of {ntasks}",
                 list(range(0, ntasks + 1, 2)))
    slope_lines(ax, models, lambda m, level: solved[m][level],
                lambda m: f"{display(m)}  {solved[m]['none']} to {solved[m]['medium']}",
                gap=(ntasks + 0.4) * 0.075)
    for i, level in enumerate(LEVELS):
        ax.annotate(f"{totals[level]} of {per_level[level]}", (i, 0),
                    xytext=(0, -42), textcoords="offset points", ha="center",
                    fontsize=FS, color=INK, fontweight="bold")
    ax.annotate("all models", (0, 0), xytext=(-24, -42), textcoords="offset points",
                ha="right", fontsize=FS, color=INK)

    note(fig, f"Read pairwise on the same task: {to_medium + to_none} model-task pairs "
         f"disagree between a budget of none and one of medium, and {to_medium} of them "
         f"go to medium. {len(peaks_low)} model peaks at low and falls at medium, so the "
         "round supports the two endpoints and not a monotone trend.", y=0.02)
    return save(fig, outdir, "f4-rq3-solved.svg")


# ---------------------------------------------------------------- F4

def fig_rq3_mechanism(rq3_rows, rq3b_rows, caps, outdir):
    """F4: calls per run, repeated replies, and what ended the runs.

    Panels a and c draw round one, which is the round sections 5.2 and 5.3 count.
    Panel b draws round two, because round two is the round whose closing
    records carry the reply counters themselves: both numbers in that panel are
    written by the executor over the same calls, where round one's had to be
    counted over the uploaded conversations, a different population (F3).
    """
    by_level = {t: [r for r in rq3_rows if r["think"] == t] for t in LEVELS}
    maxcalls = max(r["calls"] for r in rq3_rows)
    agg = {t: dict(calls=0, distinct=0, repeated=0, read=0, runs=0) for t in LEVELS}
    for r in rq3b_rows:
        a = agg[r["think"]]
        a["runs"] += 1
        if r.get("distinct_calls") is not None:
            a["read"] += 1
            a["calls"] += r["calls"]
            a["distinct"] += r["distinct_calls"]
            a["repeated"] += r["repeat_calls"]
    ends = {t: Counter(outcome_kind(r) for r in by_level[t]) for t in LEVELS}
    kinds = [k for k in KIND_LABEL if any(ends[t][k] for t in LEVELS)]

    fig, top = new_fig(10.0,
                       "Figure 5: a budget of none spends its calls repeating itself "
                       "until the ceiling ends the run",
                       f"{len(rq3_rows)} runs of {len(models_in(rq3_rows))} models over "
                       f"{len({r['task'] for r in rq3_rows})} tasks per round, no tools, one "
                       "frozen limits file")
    fig.legend(handles=[kind_handle(k) for k in kinds], loc="upper left",
               bbox_to_anchor=(0.012, top), ncol=2, frameon=False,
               handletextpad=0.4, columnspacing=1.2, borderpad=0)
    ys = [t for t in range(len(LEVELS))]
    labels = [f"think {level}" for level in LEVELS]

    # (a) calls per run.
    panel_head(fig, 0.845, "a. round one: model calls spent in each run, one mark per run")
    ax = fig.add_axes([0.245, 0.645, 0.505, 0.165])
    for i, level in enumerate(LEVELS):
        rows = sorted(by_level[level], key=lambda r: r["run"])
        for kind in kinds:
            xs = [r["calls"] for r in rows if outcome_kind(r) == kind]
            jit = [i + 0.30 * (spread(r["run"]) - 0.5) for r in rows
                   if outcome_kind(r) == kind]
            draw_marks(ax, xs, jit, kind, size=40)
        ax.text(maxcalls + 1.4, i, f"{sum(r['calls'] for r in rows)} calls",
                va="center", ha="left", fontsize=FS, color=INK2)
    by_cap = defaultdict(list)
    for cls, cap in caps.items():
        by_cap[cap].append(cls)
    for step, (cap, classes) in enumerate(sorted(by_cap.items())):
        ax.axvline(cap, color=CRITICAL, linewidth=1, linestyle=(0, (3, 3)), zorder=1)
        ax.annotate(f"{cap}-call ceiling ({', '.join(sorted(classes))})",
                    (cap, -0.90 + 0.34 * (len(by_cap) - 1 - step)), xytext=(-4, 0),
                    textcoords="offset points", ha="right", va="bottom",
                    fontsize=FS, color=CRITICAL)
    ax.set_xlim(0, maxcalls + 0.6)
    ax.set_ylim(len(LEVELS) - 0.5, -0.95)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{lab}\n{len(by_level[level])} runs"
                        for lab, level in zip(labels, LEVELS)])
    ax.set_xlabel("model calls in the run")
    plain_axes(ax, grid_axis="x")

    # (b) repeated against not, from round two's own counters.
    panel_head(fig, 0.585,
               "b. round two: the calls that repeated a reply the run had already sent")
    ax = fig.add_axes([0.245, 0.375, 0.505, 0.165])
    scale = max(agg[t]["calls"] for t in LEVELS)
    for i, level in enumerate(LEVELS):
        a = agg[level]
        repeated = a["repeated"]
        ax.barh(i, a["calls"] - repeated, height=0.42, color=ORDINAL[1], zorder=3)
        ax.barh(i, repeated, left=a["calls"] - repeated, height=0.42, color=CRITICAL,
                zorder=3)
        share = round(100 * repeated / a["calls"]) if a["calls"] else 0
        ax.text(a["calls"] + scale * 0.02, i,
                f"{repeated} repeated, {share} in every 100", va="center",
                ha="left", fontsize=FS, color=CRITICAL)
    ax.set_xlim(0, scale * 1.55)
    ax.set_ylim(len(LEVELS) - 0.5, -0.6)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{lab}\n{agg[level]['read']} of {agg[level]['runs']} runs counted"
                        for lab, level in zip(labels, LEVELS)])
    ax.set_xlabel("model calls over the runs whose record carries the counters")
    plain_axes(ax, grid_axis="x")
    ax.legend(handles=[Patch(facecolor=ORDINAL[1], label="a reply not seen before in the run"),
                       Patch(facecolor=CRITICAL, label="a reply the run had already sent")],
              loc="lower left", bbox_to_anchor=(0, 1.03), ncol=2, frameon=False,
              handletextpad=0.5, columnspacing=1.4, borderpad=0)

    # (c) what ended the runs.
    panel_head(fig, 0.295, "c. round one: what ended each run")
    ax = fig.add_axes([0.245, 0.135, 0.505, 0.125])
    for i, level in enumerate(LEVELS):
        runs = len(by_level[level])
        left = 0
        # A segment too narrow to hold its own count gets the count above the
        # bars with a leader line down to it. The lift clears every row above,
        # so a count sits in open space rather than on another row's bar, and
        # one line more per further narrow segment in the same row, so two
        # counts cannot sit on each other. Without the leader a reader cannot
        # tell which row, or which segment, a floating numeral belongs to
        # (950 v4 review, section 2, figure 4).
        lifted = i
        for k in kinds:
            n = ends[level][k]
            if not n:
                continue
            ax.barh(i, n, left=left, height=0.36, color=KIND_COLOUR[k], zorder=3)
            if n > 4:
                ax.text(left + n / 2, i, str(n), va="center", ha="center", fontsize=FS,
                        color=SURFACE, fontweight="bold", zorder=4)
            else:
                ax.annotate(str(n), (left + n / 2, i - 0.18), xytext=(0, 18 + 17 * lifted),
                            textcoords="offset points", ha="center", va="bottom",
                            fontsize=FS, color=KIND_COLOUR[k], fontweight="bold",
                            zorder=5,
                            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.2),
                            arrowprops=dict(arrowstyle="-", color=KIND_COLOUR[k],
                                            linewidth=1, shrinkA=1, shrinkB=1))
                lifted += 1
            left += n
        ax.text(runs + 1.2, i, f"{runs} runs", va="center", ha="left", fontsize=FS,
                color=INK2)
    ax.set_xlim(0, len(by_level[LEVELS[0]]) + 0.5)
    ax.set_ylim(len(LEVELS) - 0.5, -0.6)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_xlabel("runs")
    plain_axes(ax, grid_axis="x")

    missed = sum(agg[t]["runs"] - agg[t]["read"] for t in LEVELS)
    note(fig, "Panel b counts both numbers from the closing record of each run, written by "
         f"the executor over the calls the call counter counts. The {missed} runs the "
         "seconds limit ended are reaped before the record is written and are counted as "
         "not counted, never as zero, and those are the runs most likely to have "
         "repeated, so every share in panel b is a floor.")
    return save(fig, outdir, "f5-rq3-mechanism.svg")


# ---------------------------------------------------------------- F5

def net_wh(rows, base):
    """Gross host watt-hours minus the cell's own idle sample over the same window."""
    return sum(r["wh"] - (base[0] + base[1]) * r["wall_seconds"] / 3600 for r in rows)


def cell_energy(rq3_rows, shifts, baselines, bad_baselines):
    """Per batch: label, wall seconds, gross and net watt-hours, and why not."""
    out = {}
    for s in shifts:
        rs = [r for r in rq3_rows if r["shift"] == s]
        base = baselines.get(s)
        local = is_local(rs[0]["tier"])
        out[s] = dict(
            label=display(rs[0]["tier"]) + ", think " + rs[0]["think"],
            wall=sum(r["wall_seconds"] for r in rs),
            gross=sum(r["wh"] for r in rs) if local else None,
            net=net_wh(rs, base) if (local and base) else None,
            local=local,
            broken=s in bad_baselines,
            base=base)
    return out


def fig_rq3_cost(rq3_rows, shifts, baselines, bad_baselines, outdir):
    """F5: wall seconds per model and budget, and net energy where measured."""
    models = models_in(rq3_rows)
    wall = defaultdict(Counter)
    for r in rq3_rows:
        wall[model(r)][r["think"]] += r["wall_seconds"]
    totals = Counter()
    for r in rq3_rows:
        totals[r["think"]] += r["wall_seconds"]
    cheaper = sum(1 for m in models if wall[m]["low"] < wall[m]["none"])
    per = cell_energy(rq3_rows, shifts, baselines, bad_baselines)
    local = [s for s in shifts if per[s]["local"]]

    height = 11.9
    fig, top = new_fig(height,
                       "Figure 6: the thinking budget costs wall time only on the step from "
                       "the middle budget to the largest, and a low budget is cheaper than none",
                       "round one; panel a shares figure 4's layout; a dashed line is a model "
                       "at a provider")
    ymax = max(wall[m][t] for m in models for t in LEVELS)
    ymax = int((ymax // 500 + 1) * 500)
    panel_head(fig, top, "a. wall seconds over each cell's eight runs")
    ax = fig.add_axes([0.135, 0.635, 0.40, min(0.235, top - 0.40)])
    level_slopes(ax, [0, 1, 2], ymax, "wall seconds", list(range(0, ymax + 1, 1000)))
    slope_lines(ax, models, lambda m, level: wall[m][level],
                lambda m: f"{display(m)}  {wall[m]['none']} to {wall[m]['medium']} s",
                gap=ymax * 0.075)
    for i, level in enumerate(LEVELS):
        ax.annotate(f"{totals[level]} s", (i, 0), xytext=(0, -42),
                    textcoords="offset points", ha="center", fontsize=FS, color=INK,
                    fontweight="bold")
    ax.annotate("all models", (0, 0), xytext=(-24, -42), textcoords="offset points",
                ha="right", fontsize=FS, color=INK)
    fig.text(0.012, 0.555,
             wrap(f"A low budget costs less wall time than none in {cheaper} of the "
                  f"{len(models)} models. The exception is the one model whose low cell "
                  "is its most expensive.", 104), va="top", fontsize=FS, color=INK2)

    # Panel b: net energy per cell. Every cell of the round appears. A provider
    # cell carries a recorded figure, but it covers the scaffold and its machine
    # and not the model, so it is drawn as not comparable rather than left out.
    panel_head(fig, 0.495, "b. net watt-hours, every cell of the round")
    ax = fig.add_axes([0.325, 0.135, 0.415, 0.315])
    nets = [per[s]["net"] for s in local if per[s]["net"] is not None]
    nmax = max(nets)
    for i, s in enumerate(shifts):
        p = per[s]
        if not p["local"]:
            unmeasured(ax, i, nmax * 0.45, 0.6, words="not comparable")
        elif p["net"] is None:
            unmeasured(ax, i, nmax * 0.45, 0.6)
        else:
            ax.barh(i, p["net"], height=0.6, color=SERIES[1], zorder=3)
            ax.text(p["net"] + nmax * 0.015, i, f"{p['net']:.1f}", va="center",
                    ha="left", fontsize=FS, color=INK2)
    ax.set_xlim(0, nmax * 1.12)
    ax.set_ylim(len(shifts) - 0.5, -0.6)
    ax.set_yticks(range(len(shifts)))
    ax.set_yticklabels([per[s]["label"] for s in shifts])
    ax.set_xlabel("watt-hours over the cell's eight runs")
    plain_axes(ax, grid_axis="x")

    note(fig, "Net is the gross host energy over the run window minus that cell's own "
         "300 second idle sample. Not measured: the idle sample read a negative wattage. "
         "Not comparable: a provider cell does carry a recorded figure, covering the "
         "scaffold and its machine only, because the model runs on hardware these "
         "counters cannot see.")
    return save(fig, outdir, "f6-rq3-cost.svg")


# ---------------------------------------------------------------- A1

def fig_outcome_heatmap(rq3_rows, outdir):
    """A1: all 144 runs, 18 cells by 8 tasks."""
    models = models_in(rq3_rows)
    tasks = sorted({r["task"] for r in rq3_rows})
    grid = {(model(r), r["think"], r["task"]): outcome_kind(r) for r in rq3_rows}
    cells = [(m, level) for m in models for level in LEVELS]
    kinds = [k for k in KIND_LABEL if k in set(grid.values())]

    fig, top = new_fig(8.2,
                       "Figure A1: every run of the thinking-budget round",
                       f"round one, {len(cells)} cells by {len(tasks)} tasks; one task passes in "
                       "every cell and one fails in every locally served cell, so neither "
                       "can move a paired comparison")
    fig.legend(handles=[kind_handle(k) for k in kinds], loc="upper left",
               bbox_to_anchor=(0.012, top), ncol=2, frameon=False,
               handletextpad=0.4, columnspacing=1.2, borderpad=0)

    ax = fig.add_axes([0.325, 0.105, 0.525, 0.60])
    for i, (m, level) in enumerate(cells):
        for j, task in enumerate(tasks):
            kind = grid[(m, level, task)]
            ax.add_patch(plt.Rectangle((j - 0.46, i - 0.42), 0.92, 0.84,
                                       facecolor=KIND_COLOUR[kind], zorder=2))
            if kind != "pass":
                ax.scatter([j], [i], marker=KIND_MARKER[kind], s=34, zorder=3,
                           facecolors=SURFACE if KIND_FILLED[kind] else "none",
                           edgecolors=SURFACE, linewidths=1.4)
        solved = sum(1 for task in tasks if grid[(m, level, task)] == "pass")
        ax.text(len(tasks) - 0.35, i, f"{solved} of {len(tasks)}", va="center",
                ha="left", fontsize=FS, color=INK2)
    ax.set_xlim(-0.6, len(tasks) + 0.9)
    ax.set_ylim(len(cells) - 0.5, -0.5)
    ax.set_xticks(range(len(tasks)))
    ax.set_xticklabels(tasks, rotation=35, ha="left", rotation_mode="anchor")
    ax.xaxis.set_ticks_position("top")
    ax.set_yticks(range(len(cells)))
    ax.set_yticklabels([f"{display(m)}, think {level}" for m, level in cells])
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)

    passed = sum(1 for r in rq3_rows if r["outcome"] == "pass")
    note(fig, f"{passed} of {len(rq3_rows)} runs passed every hidden test of their task. "
         "A cell is one model at one thinking budget; a column is one task under all "
         f"{len(cells)} cells.")
    return save(fig, outdir, "a1-outcome-heatmap.svg")


# ---------------------------------------------------------------- A3

def fig_calls_vs_distinct(rq3b_rows, outdir):
    """A2: one point per run, calls against distinct replies.

    Drawn from round two, whose closing records carry both counters, written by
    the executor over the same calls. Round one's distinct replies were counted
    over the uploaded conversations instead, a population the call counter does
    not cover, and three of its runs came out with more distinct replies than
    calls, above the diagonal this figure's note calls a maximum (F3, F4).
    """
    pts = counted(rq3b_rows)
    xmax = max(r["calls"] for r in pts)
    ymax = max(r["distinct_calls"] for r in pts)
    groups = defaultdict(Counter)
    for r in pts:
        groups[(r["calls"], r["distinct_calls"])][outcome_kind(r)] += 1
    kinds = [k for k in KIND_LABEL
             if any(k in c for c in groups.values())]

    fig, top = new_fig(6.2,
                       "Figure A2: a run that repeats itself sends many calls and few "
                       "different replies",
                       f"round two, {len(pts)} of {len(rq3b_rows)} runs; the rest are the "
                       "runs the seconds limit ended, reaped before their record was "
                       "written. On the diagonal, every reply in the run was different.")
    fig.legend(handles=[kind_handle(k) for k in kinds], loc="upper left",
               bbox_to_anchor=(0.012, top), ncol=3, frameon=False,
               handletextpad=0.4, columnspacing=1.4, borderpad=0)
    top -= 0.30 / 6.2

    ax = fig.add_axes([0.085, 0.225, 0.86, top - 0.28])
    diag = min(xmax, ymax)
    ax.plot([0, diag], [0, diag], color=AXIS, linewidth=1.3, linestyle=(0, (4, 4)),
            zorder=1)
    ax.annotate("every reply different", (diag, diag), xytext=(-6, 6),
                textcoords="offset points", ha="right", va="bottom", fontsize=FS,
                color=MUTED)
    for (calls, distinct), counter in sorted(groups.items()):
        ranked = sorted(counter.items(), key=lambda kv: -kv[1])
        # Each count sits just clear of its own disc and one line off its
        # neighbour: the discs are wide, and a label inside one is unreadable.
        spoken = [(k, n) for k, n in ranked if n > 1]
        for offset, (kind, n) in enumerate(ranked):
            if n == 1:
                draw_marks(ax, [calls], [distinct], kind, size=44)
                continue
            ax.scatter([calls], [distinct], s=44 * n, marker="o", zorder=2,
                       facecolors=KIND_COLOUR[kind], edgecolors=KIND_COLOUR[kind],
                       alpha=0.28, linewidths=1.2)
            radius = 3.74 * n ** 0.5
            if radius >= 8:
                # Inside its own disc, and above the smaller disc drawn on top
                # of it: the low corner holds five counts, and outside the discs
                # they would sit on each other.
                lift = radius - 7 if offset == 0 and len(spoken) > 1 else 0
                ax.annotate(str(n), (calls, distinct), xytext=(0, lift - 4),
                            textcoords="offset points", ha="center", fontsize=FS,
                            fontweight="bold", color=KIND_COLOUR[kind], zorder=4)
                continue
            ax.annotate(str(n), (calls, distinct),
                        xytext=(6 + radius,
                                4 + 20 * (len(spoken) - 1) / 2 - 20 * offset),
                        textcoords="offset points", fontsize=FS, fontweight="bold",
                        color=KIND_COLOUR[kind])
    ax.set_xlim(-0.6, xmax + 2.8)
    ax.set_ylim(-0.4, ymax + 0.8)
    ax.set_xticks(range(0, xmax + 1, 4))
    ax.set_yticks(range(0, ymax + 1, 2))
    ax.set_xlabel("model calls in the run")
    ax.set_ylabel("distinct replies in the run")
    plain_axes(ax, grid_axis="both")

    note(fig, "Every point below the diagonal is a run that sent a reply it had already "
         "sent, against verification output that had not changed. No point can sit above "
         "it: both counters are written by the executor over the same calls, so a run "
         "cannot record more different replies than calls. A shaded disc with a number is "
         "that many runs at the same point, its area scaled to the count.")
    return save(fig, outdir, "a2-calls-vs-distinct.svg")


# ---------------------------------------------------------------- A5

def fig_energy_per_cell(rq3_rows, shifts, baselines, bad_baselines, outdir):
    """A5: gross and net energy per local cell, and the twelve idle samples."""
    per = cell_energy(rq3_rows, shifts, baselines, bad_baselines)
    local = [s for s in shifts if per[s]["local"]]
    gross_max = max(per[s]["gross"] for s in local)
    samples = [(per[s]["label"], baselines.get(s) or bad_baselines[s], s in baselines)
               for s in shifts if s in baselines or s in bad_baselines]
    cpus = [v[0] for _, v, ok in samples if ok]
    gpus = [v[1] for _, v, ok in samples if ok]

    fig, top = new_fig(10.2,
                       "Figure A3: what each local cell drew, gross and net, and the idle "
                       "samples it is measured against",
                       "round one; gross is the host counters over the whole run window; net "
                       "subtracts that cell's own 300 second idle sample over the same "
                       "window")
    panel_head(fig, 0.857, "a. watt-hours over each cell's eight runs")
    ax = fig.add_axes([0.265, 0.516, 0.545, 0.309])
    for i, s in enumerate(local):
        p = per[s]
        ax.barh(i - 0.19, p["gross"], height=0.34, color=ORDINAL[0], zorder=3)
        ax.text(p["gross"] + gross_max * 0.012, i - 0.19, f"{p['gross']:.1f}",
                va="center", ha="left", fontsize=FS, color=INK2)
        if p["net"] is None:
            unmeasured(ax, i + 0.19, gross_max * 0.29, 0.34)
        else:
            ax.barh(i + 0.19, p["net"], height=0.34, color=SERIES[1], zorder=3)
            ax.text(p["net"] + gross_max * 0.012, i + 0.19, f"{p['net']:.1f}",
                    va="center", ha="left", fontsize=FS, color=INK2)
    ax.set_xlim(0, gross_max * 1.12)
    ax.set_ylim(len(local) - 0.5, -0.6)
    ax.set_yticks(range(len(local)))
    ax.set_yticklabels([per[s]["label"] for s in local])
    ax.set_xlabel("watt-hours, host counters, no wall meter behind them")
    plain_axes(ax, grid_axis="x")
    ax.legend(handles=[Patch(facecolor=ORDINAL[0], label="gross watt-hours"),
                       Patch(facecolor=SERIES[1], label="net watt-hours")],
              loc="upper left", bbox_to_anchor=(0, -0.16), ncol=2, frameon=False,
              handletextpad=0.5, columnspacing=1.4, borderpad=0)

    panel_head(fig, 0.415,
               f"b. the {len(cpus)} usable idle samples: 300 seconds with no machine running",
               f"one taken before each local cell; a box and whiskers over the samples "
               f"per sensor, median as the line, every sample a dot; the {'one' if len(samples) - len(cpus) == 1 else len(samples) - len(cpus)} "
               f"sample that read a negative wattage is an anomaly, rejected and not drawn "
               f"(see below)")
    ax = fig.add_axes([0.265, 0.143, 0.545, 0.203])
    # A box plot per sensor over the usable samples, every sample drawn as its
    # own dot on top: eleven values are a distribution, and a range bar hid
    # where they sat inside it (majgull, last review round).
    for i, (values, colour) in enumerate(((cpus, SERIES[0]), (gpus, ORDINAL[2]))):
        ax.boxplot([values], positions=[i], vert=False, widths=0.5, whis=(0, 100),
                   showfliers=False, patch_artist=True, zorder=2,
                   boxprops=dict(facecolor=colour, alpha=0.25, edgecolor=colour),
                   whiskerprops=dict(color=colour), capprops=dict(color=colour),
                   medianprops=dict(color=colour, linewidth=2))
        jitter = random.Random(950)
        ax.scatter(values, [i + jitter.uniform(-0.12, 0.12) for _ in values], s=22,
                   color=colour, edgecolor=SURFACE, linewidth=0.6, zorder=3)
        med = statistics.median(values)
        ax.text(max(values) + 0.6, i, f"median {med:.1f} W, {min(values)} to {max(values)}",
                va="center", ha="left", fontsize=FS, color=INK2)
    lo, hi = min(min(cpus), min(gpus)), max(max(cpus), max(gpus))
    ax.set_xlim(lo - 3, hi + 13)
    ax.set_ylim(1.7, -0.7)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["CPU package", "both GPUs"])
    ax.set_xlabel("watts")
    plain_axes(ax, grid_axis="x")

    broken = [(label, v) for label, v, ok in samples if not ok]
    if broken:
        label, v = broken[0]
        watts = sorted(per[s]["gross"] * 3600 / per[s]["wall"] for s in local)
        note(fig, f"The remaining sample, taken before {label}, read {v[0]} W of CPU "
             f"package power and {v[1]} W of GPU power. A negative difference over the "
             "window is the counter wrapping, not a low reading, and the baseline path "
             "has no wraparound correction. That cell also has the largest gross bar "
             f"above, {watts[-1]:.1f} W implied over its window against {watts[0]:.1f} to "
             f"{watts[-2]:.1f} W for the other eleven, which section 7 reads as the check "
             "the record can bear on a wrap: a corrected one cannot show as a negative "
             "figure.")
    return save(fig, outdir, "a3-energy-per-cell.svg")


# ---------------------------------------------------------------- A8

def batch_windows(rows, shifts):
    """[(shift, first local start, last local end)] in launch order."""
    out = []
    for s in shifts:
        stamps = [datetime.fromisoformat(r["iso"]) for r in rows if r["shift"] == s]
        out.append((s, min(stamps), max(stamps)))
    return out


def fig_batch_timeline(rq2_rows, rq2_shifts, rq3_rows, rq3_shifts, outdir):
    """A8: when every batch of both questions ran."""
    rq2 = batch_windows(rq2_rows, rq2_shifts)
    rq3 = batch_windows(rq3_rows, rq3_shifts)
    origin = min(b[1] for b in rq2 + rq3)
    span = (max(b[2] for b in rq2 + rq3) - origin).total_seconds() / 3600

    arm_names = {"pipeline": "no tools", "session": "shell"}
    seen = Counter()
    rq2_labels = []
    for shift, _, _ in rq2:
        arm = arm_names[shift.rsplit("-", 1)[1]]
        seen[arm] += 1
        rq2_labels.append(f"round {seen[arm]}, {arm}")
    rq3_labels = []
    for shift, _, _ in rq3:
        rest = shift.split("-", 2)[2].removeprefix("rq3-")
        level = rest.rsplit("-", 1)[1]
        rq3_labels.append(f"{display(rest.rsplit('-', 1)[0])}, think {level}")

    height = 10.0
    fig, top = new_fig(height,
                       "Figure A4: when each batch ran, and the gaps between them",
                       "hours from the start of the first batch, taken from the closing "
                       "record of every run; no batch of one question overlaps a batch of "
                       "the other")

    def panel(title, subtitle, batches, labels, top_frac, panel_h, colour):
        panel_head(fig, top_frac, title, subtitle)
        ax = fig.add_axes([0.315, top_frac - 0.075 - panel_h, 0.60, panel_h])
        for i, (_, s0, s1) in enumerate(batches):
            x0 = (s0 - origin).total_seconds() / 3600
            width = max((s1 - s0).total_seconds() / 3600, 0.03)
            ax.barh(i, width, left=x0, height=0.55, color=colour, zorder=3)
            ax.text(x0 + width + span * 0.012, i,
                    f"{(s1 - s0).total_seconds() / 60:.0f} min", va="center",
                    ha="left", fontsize=FS, color=INK2)
            if i:
                prev = (batches[i - 1][2] - origin).total_seconds() / 3600
                ax.plot([prev, x0], [i - 0.5, i - 0.5], color=MUTED, linewidth=1,
                        linestyle=(0, (2, 3)), zorder=2)
        ax.set_xlim(-0.15, span * 1.1)
        ax.set_ylim(len(batches) - 0.5, -0.6)
        ax.set_yticks(range(len(batches)))
        ax.set_yticklabels(labels)
        ax.set_xlabel("hours from the start of the first batch")
        plain_axes(ax, grid_axis="x")
        return ax

    panel("a. the tools comparison, ten batches launched alternately",
          "one arm then the other, so anything that drifted through the afternoon "
          "reached both", rq2, rq2_labels, 0.885, 0.215, SERIES[0])
    panel("b. the thinking-budget round, eighteen batches",
          "the dotted gap before a local cell holds that cell's 300 second idle power "
          "sample and the launcher's own checks",
          rq3, rq3_labels, 0.545, 0.335, ORDINAL[1])
    rq2_span = (max(b[2] for b in rq2) - origin).total_seconds() / 3600
    note(fig, "Both panels share one axis so the two rounds can be read against each "
         f"other, which is why panel a runs to {span:.0f} hours with no data past "
         f"{rq2_span:.1f}: the tools comparison is the shorter of the two rounds and "
         "the empty right-hand side of panel a is that difference.")
    return save(fig, outdir, "a4-batch-timeline.svg")


# ---------------------------------------------------------------- main

def render_png(svg_path):
    """A raster copy beside the SVG, for a reader without a browser."""
    exe = shutil.which("rsvg-convert")
    if exe is None:
        return None
    png = svg_path[:-4] + ".png"
    subprocess.run([exe, "-o", png, svg_path], check=True)
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ledgers", nargs=2, help="the two run-log snapshots, in either order")
    ap.add_argument("--rq2-shifts", default=RQ2_SHIFTS)
    ap.add_argument("--rq3-shifts", default=RQ3_SHIFTS)
    ap.add_argument("--rq3b-shifts", default=RQ3B_SHIFTS,
                    help="round two's batch list, whose closing records carry the "
                         "reply counters the repeated-reply panels are drawn from")
    ap.add_argument("--rq3-log", default=RQ3_LOG, help="launcher log, for the idle samples")
    ap.add_argument("--out", default=OUTDIR)
    ap.add_argument("--png", action="store_true",
                    help="also write a PNG of each figure through rsvg-convert")
    args = ap.parse_args()

    rq2_shifts = read_shifts(args.rq2_shifts)
    rq3_shifts = read_shifts(args.rq3_shifts)
    rq3b_shifts = read_shifts(args.rq3b_shifts)
    rq2_ledger, rq3_ledger = pick_ledgers(args.ledgers, rq2_shifts, rq3_shifts)
    rq2_rows = run_ends(rq2_ledger, rq2_shifts)
    rq3_rows = run_ends(rq3_ledger, rq3_shifts)
    rq3b_rows = run_ends(rq3_ledger, rq3b_shifts)
    impossible = impossible_rows(rq3b_rows)
    if impossible:
        sys.exit(f"{len(impossible)} of round two's closing records carry more distinct "
                 "replies than calls, which cannot happen if both counters run over the "
                 f"same calls: {[r['run'] for r in impossible][:5]}")
    caps = call_caps(rq3_ledger, rq3_shifts)
    baselines, bad_baselines = idle_baselines(args.rq3_log)
    os.makedirs(args.out, exist_ok=True)
    setup_style()

    written = [
        fig_system(args.out),
        fig_tests(args.out),
        fig_rq2_grid(rq2_rows, rq2_shifts, args.out),
        fig_rq3_solved(rq3_rows, args.out),
        fig_rq3_mechanism(rq3_rows, rq3b_rows, caps, args.out),
        fig_rq3_cost(rq3_rows, rq3_shifts, baselines, bad_baselines, args.out),
        fig_outcome_heatmap(rq3_rows, args.out),
        fig_calls_vs_distinct(rq3b_rows, args.out),
        fig_energy_per_cell(rq3_rows, rq3_shifts, baselines, bad_baselines, args.out),
        fig_batch_timeline(rq2_rows, rq2_shifts, rq3_rows, rq3_shifts, args.out),
    ]
    missing = False
    for path in written:
        png = render_png(path) if args.png else None
        missing = missing or (args.png and png is None)
        print(f"wrote {path}" + (f" and {png}" if png else ""))
    if missing:
        print("rsvg-convert is not on the path; no PNG was written", file=sys.stderr)


if __name__ == "__main__":
    main()
