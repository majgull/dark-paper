#!/usr/bin/env python3
"""Write evidence/MANIFEST.txt, a sha256 per shipped evidence file.

The evidence files no longer live in git: they are shipped as a Hugging Face
dataset whose tree mirrors this repository (evidence/ledger/..., runs/...). This script
walks the four evidence roots, hashes every regular file that ships, and writes
the result to evidence/MANIFEST.txt, one `<sha256>  <path>` line per file with
paths relative to the repository root, sorted. The first line names the dataset and pins the
revision; HANDLE and REVISION are placeholders until the dataset exists.

    python3 tools/manifest.py            write evidence/MANIFEST.txt
    python3 tools/manifest.py --check    rehash and exit 1 on any drift/missing

Run from the repository root. Standard library only.
"""
import argparse
import hashlib
import sys
from pathlib import Path

# The repository root is the directory that holds tools/, whatever the cwd is.
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "MANIFEST.txt"
ROOTS = ("evidence/ledger", "evidence/launch", "evidence/derived", "runs")
EXCLUDE = {"runs/README.md", "evidence/MANIFEST.txt"}
HEADER = "dataset HANDLE/dark-evidence revision REVISION"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def shipped_files():
    """Every regular file that ships, as root-relative paths, sorted."""
    found = []
    for root in ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in EXCLUDE:
                continue
            found.append(rel)
    return sorted(found)


def render():
    # Keep the pinned dataset line once it exists; only a manifest written from
    # nothing starts with the placeholders.
    header = HEADER
    if OUT.exists():
        first = OUT.read_text().splitlines()[0] if OUT.read_text() else ""
        if first.startswith("dataset "):
            header = first
    lines = [header]
    for rel in shipped_files():
        lines.append(f"{sha256(ROOT / rel)}  {rel}")
    return "\n".join(lines) + "\n"


def parse_manifest(text):
    """Return {path: sha256} from a manifest body, ignoring the header."""
    entries = {}
    for line in text.splitlines():
        if not line or line.startswith("dataset "):
            continue
        digest, _, rel = line.partition("  ")
        if rel:
            entries[rel] = digest
    return entries


def check():
    if not OUT.is_file():
        print(f"missing {OUT.relative_to(ROOT)}", file=sys.stderr)
        return 1
    wanted = parse_manifest(OUT.read_text())
    bad = 0
    for rel, digest in sorted(wanted.items()):
        path = ROOT / rel
        if not path.is_file():
            print(f"missing {rel}")
            bad += 1
        elif sha256(path) != digest:
            print(f"hash differs {rel}")
            bad += 1
    for rel in shipped_files():
        if rel not in wanted:
            print(f"not in manifest {rel}")
            bad += 1
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="rehash and report drift instead of writing")
    args = ap.parse_args()
    if args.check:
        return check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render())
    print(f"{len(shipped_files())} files, wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
