#!/usr/bin/env python3
"""render.py — write the paper by substituting its numbers.

The paper is drafted as `paper.src.md`, in which every number is a token
`{{num:<id>}}` naming a row of `numbers.md`. This substitutes them and writes
the paper a reader gets. A larger run then updates the paper by regenerating
`numbers.md` and running this again: nobody retypes a number into the abstract
and nobody forgets one.

Usage: render.py <paper.src.md> <numbers.md> <paper.md>

Exit 0 and print one summary line on success. Exit 1, print one line per unknown
id and write nothing, when a token names an id the table does not define: a
paper with a hole in it is not a paper, and half-substituted output would be
committed by the next command in the chain. Exit 2 for usage and read errors.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from numbers_table import TOKEN_RE, parse, tokens

USAGE = "usage: render.py <paper.src.md> <numbers.md> <paper.md>"


def render(src_text, rows):
    """(rendered text, [(id, line number) for every unknown id])."""
    unknown = []
    for name, start, _ in tokens(src_text):
        if name not in rows:
            unknown.append((name, src_text.count("\n", 0, start) + 1))
    if unknown:
        return None, unknown
    return TOKEN_RE.sub(lambda m: rows[m.group(1)]["number"], src_text), []


def main(argv):
    if len(argv) != 4:
        print(USAGE, file=sys.stderr)
        return 2
    src_path, numbers_path, out_path = argv[1:]
    try:
        src_text = Path(src_path).read_text()
        rows = parse(Path(numbers_path).read_text())
    except OSError as exc:
        print(f"render.py: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"render.py: {numbers_path}: {exc}", file=sys.stderr)
        return 2

    text, unknown = render(src_text, rows)
    if unknown:
        for name, lineno in unknown:
            print(f"{src_path}:{lineno}: unknown number id: {name}; "
                  f"{numbers_path} defines no row with that id")
        print(f"wrote nothing; {out_path} would have carried a hole")
        return 1

    Path(out_path).write_text(text)
    print(f"wrote {out_path}, {len(tokens(src_text))} numbers from {numbers_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
