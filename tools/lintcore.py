"""lintcore.py — the parts every hub prose linter shares.

Three linters now read markdown against a skill: brief-lint against
skills/brief-writing/SKILL.md, lint.py against
skills/paper-writing/SKILL.md, and report-lint against the same paper skill
for a report a stranger reads. Four things must not drift between them, because
a rule that means one thing in a brief and another in a paper is worse than no
rule: the prose masking that separates a mention from a use, the three wording
checks that a document of any kind must pass (em-dash, moral adjective, private
address), and the shape of what a linter prints and exits with.

Masking: text inside backticks or double quotes is blanked out, keeping the line
length so column positions survive. A document may then write `grep -c '—'` or
the word "honest" as the thing it forbids without tripping the check that
forbids it.

Output convention (emit): failures on stdout, one per line, each
`<file>:<lineno>: <check>: <what is wrong>`, sorted by line, followed by a line
naming the skill; warnings on stderr in the same shape with `warning: ` before
the message, and they never change the exit code. Exit 0 on a clean pass with
nothing on stdout, 1 on failures, 2 for usage and read errors.
"""

import re
import sys

CODE_SPAN_RE = re.compile(r"(`+)(?:(?!\1).)*\1")
QUOTED_RE = re.compile(r'"[^"]*"')

EM_DASH = "—"

# The words skills/brief-writing/SKILL.md forbids. lint.py adds to this.
DEFAULT_MORAL_WORDS = ("honest", "trustworthy")

IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
USER_AT_HOST_RE = re.compile(r"\b[\w.+-]+@[\w.-]*\w\b")
LOCAL_HOST_RE = re.compile(r"\b[\w-]+\.(?:local|lan)\b", re.IGNORECASE)


def mask(line):
    """Blank out code spans and double-quoted text, preserving line length."""
    out = line
    for pattern in (CODE_SPAN_RE, QUOTED_RE):
        out = pattern.sub(lambda m: " " * len(m.group(0)), out)
    return out


def moral_re(words=DEFAULT_MORAL_WORDS):
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE)


class Findings:
    """Collects one document's failures and warnings in the shared format."""

    def __init__(self, path):
        self.path = path
        self._failures = []
        self.warnings = []

    def fail(self, lineno, check, message):
        self._failures.append((lineno, f"{self.path}:{lineno}: {check}: {message}"))

    def warn(self, lineno, check, message):
        self.warnings.append(f"{self.path}:{lineno}: {check}: warning: {message}")

    @property
    def failures(self):
        """Failure lines in file order."""
        self._failures.sort(key=lambda f: f[0])
        return [line for _, line in self._failures]


def check_em_dash(found, lines):
    for i, line in enumerate(lines, 1):
        if EM_DASH in mask(line):
            found.fail(i, "em-dash", "em-dash (U+2014) in prose; use a comma, a colon or a "
                                     "full stop")


def check_moral_adjective(found, lines, words=DEFAULT_MORAL_WORDS):
    pattern = moral_re(words)
    for i, line in enumerate(lines, 1):
        m = pattern.search(mask(line))
        if m:
            found.fail(i, "moral-adjective", f"the word \"{m.group(1)}\" is a moral "
                                             "adjective; name the mechanism instead "
                                             "(hidden tests, append-only ledger, hash on "
                                             "every row)")


def check_private_address(found, lines):
    """Reads unmasked lines: an address inside a code span is still an address,
    and a stranger reading the document runs the commands as written."""
    for i, line in enumerate(lines, 1):
        for pattern, what in ((IPV4_RE, "an IPv4 literal"),
                              (USER_AT_HOST_RE, "a user@host token"),
                              (LOCAL_HOST_RE, "a .local or .lan hostname")):
            m = pattern.search(line)
            if m:
                found.fail(i, "private-address",
                           f"\"{m.group(0)}\" is {what}; name hosts by role (the runner "
                           "host, the GPU host) and let the appendix count distinct "
                           "values instead of printing them")


def read_lines(path):
    """(raw bytes, decoded lines) for one document."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw, raw.decode("utf-8", "replace").splitlines()


def emit(failures, warnings, skill):
    """Print in the shared convention and return the exit code."""
    for line in warnings:
        print(line, file=sys.stderr)
    if not failures:
        return 0
    for line in failures:
        print(line)
    print(f"see {skill} for what each check means")
    return 1
