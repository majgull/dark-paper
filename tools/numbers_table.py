"""numbers_table.py — the numbers appendix, read the same way by every tool.

A paper's numbers live in `numbers.md`: one row per number, with the command
that re-derives it. Three tools now read that file and must agree on its shape,
because a number that means one thing to the generator and another to the
renderer is worse than an untracked number: the generator
(`appendix.py`) writes it, `render.py` substitutes
its values into the paper source, and `tools/lint.py` checks that the
source spends every id it defines.

The shape: a markdown table whose first column is `id`, a kebab-case name unique
in the file, followed by the number, the section, the source file, what it is,
and the command. Pipe characters inside a cell are written `\\|` so the table
renders, and are read back as `|`.

The binding: the paper source `paper.src.md` writes each number as
`{{num:<id>}}`. A larger run regenerates `numbers.md` and re-renders the paper,
so no number is retyped and none is forgotten.
"""

import re

CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
TOKEN_RE = re.compile(r"\{\{num:([^{}]*)\}\}")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

COLUMNS = ("id", "number", "section", "source file", "what it is", "command")


def slug(text):
    """A kebab-case id from a row's description. Stable for a stable description."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def escape(text):
    return text.replace("|", "\\|")


def unescape(text):
    return text.replace("\\|", "|")


def parse(text):
    """{id: {column: value}} for every data row, in file order.

    Raises ValueError on a duplicate id: the whole point of the column is that
    one id names one number."""
    rows = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in CELL_SPLIT_RE.split(stripped)[1:-1]]
        if len(cells) < 2 or cells[0] == COLUMNS[0]:
            continue  # the header row
        if set(cells[0]) <= set("-: "):
            continue  # the separator row
        row = {name: unescape(value) for name, value in zip(COLUMNS, cells)}
        if row["id"] in rows:
            raise ValueError(f"duplicate id in the numbers table: {row['id']}")
        rows[row["id"]] = row
    return rows


def tokens(text):
    """[(id, start, end)] for every {{num:<id>}} token, in file order."""
    return [(m.group(1), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
