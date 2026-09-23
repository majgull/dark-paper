#!/usr/bin/env python3
"""Restore the evidence files from evidence/MANIFEST.txt.

The ledger, launch logs, derived tables and run directories ship as a Hugging
Face dataset whose tree mirrors this repository (evidence/ledger/..., runs/...). This
script reads the manifest, fetches every file that is missing or whose sha256
does not match, and leaves files that are already correct alone, so appendix.py
and figs.py read the same paths they always did.

    python3 tools/fetch-evidence.py [--source URL_OR_DIR]

The default source is the dataset named by the manifest's first line
(https://huggingface.co/datasets/<handle>/dark-evidence/resolve/<revision>/)
and the run is refused while that line still carries the HANDLE/REVISION
placeholders. --source points at a local directory with the same layout
instead. Run from the repository root. Standard library only.
"""
import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

# The repository root is the directory that holds tools/, whatever the cwd is.
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "evidence" / "MANIFEST.txt"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest(text):
    """Return (header, {path: sha256})."""
    header = None
    entries = {}
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("dataset "):
            header = line
            continue
        digest, _, rel = line.partition("  ")
        if rel:
            entries[rel] = digest
    return header, entries


def dataset_url(header):
    """Build the default URL, refusing an unpinned manifest."""
    fields = (header or "").split()
    if len(fields) < 4 or fields[0] != "dataset" or fields[2] != "revision":
        sys.exit(f"cannot read dataset line: {header!r}")
    repo, revision = fields[1], fields[3]
    handle = repo.partition("/")[0]
    if handle == "HANDLE" or revision == "REVISION":
        sys.exit("manifest is not pinned yet: evidence/MANIFEST.txt still "
                 "carries the HANDLE/REVISION placeholders")
    return f"https://huggingface.co/datasets/{repo}/resolve/{revision}/"


def fetch(source, rel, dest):
    """Copy or download one file from (raw, kind) to dest."""
    raw, kind = source
    dest.parent.mkdir(parents=True, exist_ok=True)
    if kind == "dir":
        shutil.copyfile(Path(raw) / rel, dest)
    else:
        url = raw.rstrip("/") + "/" + rel
        with urllib.request.urlopen(url) as response, dest.open("wb") as out:
            shutil.copyfileobj(response, out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", metavar="URL_OR_DIR",
                    help="dataset base URL or local directory (default: the "
                         "dataset pinned in evidence/MANIFEST.txt)")
    args = ap.parse_args()

    if not MANIFEST.is_file():
        sys.exit(f"missing {MANIFEST.relative_to(ROOT)}")

    header, entries = parse_manifest(MANIFEST.read_text())
    if args.source:
        raw = args.source
        kind = "url" if raw.startswith(("http://", "https://")) else "dir"
    else:
        raw, kind = dataset_url(header), "url"
    source = (raw, kind)

    total = len(entries)
    fetched = 0
    bad = 0
    for rel, digest in sorted(entries.items()):
        dest = ROOT / rel
        if dest.is_file() and sha256(dest) == digest:
            continue
        try:
            fetch(source, rel, dest)
            fetched += 1
        except Exception as exc:  # transfer failed: report, keep counting
            print(f"fetch failed {rel}: {exc}", file=sys.stderr)
            bad += 1
            continue
        if not dest.is_file():
            print(f"missing {rel}", file=sys.stderr)
            bad += 1
        elif sha256(dest) != digest:
            print(f"hash differs {rel}", file=sys.stderr)
            bad += 1

    print(f"{total} files, {fetched} fetched, {bad} bad")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
