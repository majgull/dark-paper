#!/usr/bin/env python3
"""Build the per-cell and per-run tables for 950 RQ3 round one from the
ledger snapshot and launcher log committed under evidence/. Run from this directory."""
import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

DEFAULT_LEDGER = "evidence/ledger/2026-09-06.jsonl"
DEFAULT_LOG = "evidence/launch/rq3-r1-20260905-1923.log"

BASELINE_RE = re.compile(r"idle baseline: 300s, no VM")
SHIFT_RE = re.compile(r"^shift ([^:]+):")


def load_shifts(log_path):
    shifts_path = Path(str(log_path) + ".shifts")
    return [l.strip() for l in shifts_path.read_text().splitlines() if l.strip()]


# An idle baseline is a 300s no-VM power sample. A reading at or below zero is
# not a low measurement, it is a broken one: the sampler differences an energy
# counter, and a counter wraparound inside the window yields a negative delta.
# One of the twelve baselines in round one read cpu_watts -183.8 where the
# other eleven read 33-35. Propagating it made one cell's net energy exceed its
# gross. Such a baseline is dropped, and every net figure that depended on it
# becomes NOT MEASURED — never silently replaced by a neighbouring cell's.
def load_baselines(log_path):
    lines = Path(log_path).read_text().splitlines()
    baselines = {}
    invalid = {}
    for i, line in enumerate(lines):
        if not BASELINE_RE.search(line):
            continue
        if i + 2 >= len(lines):
            continue
        try:
            data = json.loads(lines[i + 1])
        except json.JSONDecodeError:
            continue
        m = SHIFT_RE.match(lines[i + 2])
        if not m:
            continue
        cpu, gpu = data["cpu_watts"], data["gpu_watts"]
        if cpu <= 0 or gpu <= 0:
            invalid[m.group(1)] = (cpu, gpu)
        else:
            baselines[m.group(1)] = (cpu, gpu)
    return baselines, invalid


def load_runs(ledger_path, shift_ids):
    rows = []
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("kind") == "run.end" and obj.get("shift") in shift_ids:
                rows.append(obj)
    return rows


def fail_label(row):
    if row["outcome"] == "pass":
        return None
    if row.get("fail_kind"):
        return row["fail_kind"]
    return row["outcome"].split(":", 1)[1]


def net_wh(row, baselines):
    baseline = baselines.get(row["shift"])
    if baseline is None or row.get("wh") is None:
        return None
    cpu_watts, gpu_watts = baseline
    idle_wh = (cpu_watts + gpu_watts) * row["wall_seconds"] / 3600
    return row["wh"] - idle_wh


def fmt_wh(v):
    return "n/a" if v is None else f"{v:.3f}"


def fmt_seconds(v):
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}"


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--log", default=DEFAULT_LOG)
    args = ap.parse_args()

    shift_ids = load_shifts(args.log)
    baselines, invalid_baselines = load_baselines(args.log)
    rows = load_runs(args.ledger, set(shift_ids))

    if len(rows) != len(shift_ids) * 8:
        print(f"MISMATCH {len(rows)} rows")
        sys.exit(1)

    for r in rows:
        r["_fail_label"] = fail_label(r)
        r["_net_wh"] = net_wh(r, baselines)

    rows_by_shift = {s: [] for s in shift_ids}
    for r in rows:
        rows_by_shift[r["shift"]].append(r)

    # Per-cell table
    cell_headers = [
        "cell", "tier", "think", "pass", "fail kinds", "calls",
        "median seconds", "total Wh (host)", "total net Wh", "total reasoning chars",
    ]
    cell_rows = []
    for s in shift_ids:
        rs = rows_by_shift[s]
        arm = rs[0]["arm"]
        cell = arm[len("rq3-"):] if arm.startswith("rq3-") else arm
        tier = rs[0]["tier"]
        think = rs[0]["think"]
        npass = sum(1 for r in rs if r["outcome"] == "pass")
        fk = Counter(r["_fail_label"] for r in rs if r["_fail_label"])
        fk_str = ", ".join(f"{k} {v}" for k, v in sorted(fk.items())) if fk else "-"
        total_calls = sum(r["calls"] for r in rs)
        median_seconds = statistics.median(r["seconds"] for r in rs)
        whs = [r["wh"] for r in rs]
        total_wh = None if any(w is None for w in whs) else sum(whs)
        nets = [r["_net_wh"] for r in rs]
        total_net = None if any(n is None for n in nets) else sum(nets)
        total_reasoning = sum(r["reasoning_chars"] or 0 for r in rs)
        cell_rows.append([
            cell, tier, think, f"{npass}/8", fk_str, total_calls,
            fmt_seconds(median_seconds), fmt_wh(total_wh), fmt_wh(total_net),
            total_reasoning,
        ])

    # Per-run table
    run_headers = ["shift", "task", "outcome", "fail_kind", "calls", "seconds", "checks", "wh", "net wh"]
    run_rows = []
    for s in shift_ids:
        for r in rows_by_shift[s]:
            run_rows.append([
                r["shift"], r["task"], r["outcome"], r.get("fail_kind") or "-",
                r["calls"], r["seconds"], f"{r['checks_ok']}/{r['checks_total']}",
                fmt_wh(r["wh"]), fmt_wh(r["_net_wh"]),
            ])

    total_runs = len(rows)
    total_passes = sum(1 for r in rows if r["outcome"] == "pass")
    think_groups = {}
    for r in rows:
        think_groups.setdefault(r["think"], []).append(r)
    think_pass_rate = []
    for think in sorted(think_groups):
        grp = think_groups[think]
        p = sum(1 for r in grp if r["outcome"] == "pass")
        think_pass_rate.append((think, p, len(grp)))
    top_calls = sorted(rows, key=lambda r: r["calls"], reverse=True)[:3]

    for shift, (cpu, gpu) in sorted(invalid_baselines.items()):
        print(f"INVALID BASELINE {shift} cpu_watts={cpu} gpu_watts={gpu} "
              f"-- dropped, net Wh for this cell is NOT MEASURED")
    if invalid_baselines:
        print()
    n_null_reasoning = sum(1 for r in rows if r.get("reasoning_chars") is None)
    if n_null_reasoning:
        print(f"NOTE {n_null_reasoning} run(s) have reasoning_chars null (cut by the "
              f"seconds cap before the count was written); they contribute 0 to the "
              f"per-cell totals, which therefore understate those cells.")
        print()
    print(md_table(cell_headers, cell_rows))
    print()
    print(md_table(run_headers, run_rows))
    print()
    print("## Summary")
    print("total Wh (host) is host-side power for the harness and its VM. For a")
    print("cloud tier the model runs elsewhere, so that column is NOT the model's")
    print("energy and does not compare to a local cell's. Only the local cells'")
    print("net Wh, gross minus that cell's own measured idle, is an energy result.")
    print(f"total runs: {total_runs}")
    print(f"total passes: {total_passes}/{total_runs}")
    print("pass rate per think tier (all models):")
    for think, p, n in think_pass_rate:
        print(f"  {think}: {p}/{n}")
    print("top 3 runs by calls:")
    for r in top_calls:
        print(f"  {r['run']} (calls={r['calls']})")


if __name__ == "__main__":
    main()
