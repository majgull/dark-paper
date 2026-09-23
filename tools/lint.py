#!/usr/bin/env python3
"""lint.py — mechanical check of the rules in skills/paper-writing/SKILL.md.

A paper is written for a reader who has never seen the repository and cannot ask
a question. That reader cannot tell a missing section from a section the writer
meant to add, a broken figure path from a figure that was never drawn, or a term
used before it was defined from a term they simply do not know. The rules for
avoiding all three lived only in prose. This makes them checkable before the
paper is committed.

Usage: lint.py [--terms a,b,c] [--coinages A,B] [--names 'Qwen 3.6 27B']
                       [--hedges 'a direction and not'] [--numbers numbers.md]
                       [--summary] <paper.md>   (flags may follow the path)

`--summary` reads the file as a short document rendered from the paper's own
numbers table (the two-page summary beside the paper): the checks that describe
a paper's shape (sections, prior-work, references, contributions-header) and the
unused-number warning are skipped, because a summary has no sections to order
and spends few of the ids. Every check on the prose, the figures, the numbers
and the provenance runs as for the paper, and a bare numeral in its source fails
it the same way.

A path ending in `.src.md` is read as a paper source: the checks below all run,
and two more join them. bare-number reports a numeral in prose that is not a
`{{num:<id>}}` token, so a number the next run will not update cannot hide in
the text; unused-number warns about an id of numbers.md that no token spends.
The numbers table is `--numbers`, or `numbers.md` beside the source. In source
mode the two term checks read the file with its tokens blanked out, because an
id is a name for a number and not prose the reader will ever see.

Exit 0 and print nothing on stdout when the paper passes. Exit 1 and print one
line per failure, each `<file>:<lineno>: <check>: <what is wrong>`, followed by a
line pointing at the skill. Warnings (placeholders, counts, term-uses) go to
stderr and do not change the exit code. Exit 2 for usage and read errors.

Checks: sections, figures, em-dash, moral-adjective, banned-words,
contributions-header, coinages, private-address, body-provenance,
body-code-span, placeholders, terms, term-uses, prior-work, references, counts,
repeated-hedge. The masking, the em-dash,
moral-adjective and private-address scans and the output convention come from
bin/lib/lintcore.py, shared with brief-lint and report-lint.

Mentions versus uses, and where it does not apply: em-dash, moral-adjective,
banned-words and coinages read masked prose, so a paper may quote the word it
forbids inside backticks or double quotes. private-address deliberately does not
mask. An address in a command is exactly the leak the rule is about, and a
stranger reading the paper runs the commands.

Three banned words have ordinary uses, so they are matched by claim shape and
not by the bare word. "first" is skipped when it counts something ("the first
round") and caught when it claims priority ("the first system to ...", "the
first to ..."). "significant" passes in a sentence that names a statistical test
or quotes a p value. "contribution" passes unless the paper is describing its
own ("our contribution", "the contributions of this work").
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lintcore import (CODE_SPAN_RE, DEFAULT_MORAL_WORDS, Findings,
                      check_em_dash, check_moral_adjective,
                      check_private_address, emit, mask, read_lines)
from numbers_table import TOKEN_RE, parse as parse_numbers

SKILL = "skills/paper-writing/SKILL.md"

# "rigorous" joins the brief linter's two: the skill names all three.
MORAL_WORDS = DEFAULT_MORAL_WORDS + ("rigorous",)

# (name for the message, substrings any one of which the heading may contain).
# The order is the order of the skill's structure section, and the check is that
# the level-two headings match this list as a subsequence, in this order.
REQUIRED_SECTIONS = (
    ("Abstract", ("abstract",)),
    ("Motivation", ("motivation",)),
    ("the terms section", ("terms",)),
    ("the questions section", ("question",)),
    ("the setup section", ("setup",)),
    ("Results", ("results",)),
    ("the threats and limits section", ("limits", "threats")),
    ("the reproducing section", ("reproduc",)),
)

# The six names the terms section of paper.md defines and then
# uses, in its own order. The list is per paper and moves with it: the third
# draft replaced most of the second's coinages with the field's own words, and a
# word the paper no longer defines is not a term this check is about.
#
# "task", "run" and "pass" are deliberately not here, and neither are the two
# terms the abstract glosses inline where it first needs them, the reference
# solution and the thinking budget: the skill's abstract rules ask for that
# gloss, and a first-use check cannot tell a glossed use from a jargon one.
DEFAULT_TERMS = ("cell", "batch", "arm", "scaffold", "gold solution", "mutant")

# The display names the paper gives its models. A display name carries version
# and size numerals that belong to the name and that no larger run will update,
# so the bare-number check reads a source with these blanked; without them a
# paper that obeys the terminology rule ("Qwen 3.6 35B", never `my/qwen-3.6-35b`)
# would fail bare-number on every mention. The list is per paper and moves with
# it, like the terms above, and `--names` replaces it.
DEFAULT_NAMES = ("Qwen 3.5 9B", "Qwen 3.6 27B", "Qwen 3.6 35B", "Qwen 3.8 27B",
                 "DeepSeek V4 Flash", "GLM 5.3 Flash", "Claude Sonnet 5")

# The capitalised internal names a paper about this repository tends to inherit.
# A capitalised coinage reads as a product name; the skill forbids it.
DEFAULT_COINAGES = ("Factory", "Bench", "Judge", "Ledger", "Envelope")

# One caveat told once where it bites and once in threats and limits is care;
# told five times it is anxiety, and the fourth telling teaches nothing the
# first did not. These are the phrases the 950 v4 draft repeated: "a direction
# and not a verdict" in 5.2, "a direction and not an effect size" in 5.3, "the
# direction and not the sharper form" in the abstract, "a direction that came
# back twice" in 5.4, and the same point again in threats. The list is per paper
# and moves with it, like the terms and the display names; `--hedges` replaces
# it. More than two occurrences of one phrase is the warning.
DEFAULT_HEDGES = ("a direction and not", "not a verdict", "not an effect size")
HEDGE_LIMIT = 2

# Banned in claims, matched as bare words: no ordinary use survives the rule.
PLAIN_BANNED_RE = re.compile(
    r"\b(novel|powerful|robust|state-of-the-art)\b", re.IGNORECASE)

# "first": the word, plus up to three words after it, so the shape can be read.
FIRST_RE = re.compile(r"\bfirst\b((?:\s+[\w-]+){0,3})", re.IGNORECASE)
# Nouns that make "first" a count rather than a claim of priority.
COUNTING_AFTER_FIRST = frozenset(
    "round rounds run runs call calls line lines row rows column columns use uses "
    "time times page pages day days batch batches step steps attempt attempts "
    "version versions draft drafts entry entries record records sample samples "
    "task tasks model models cell cells shift shifts figure table section "
    "paragraph sentence author authors half element half-hour".split())
# Nouns that make it a claim of priority even without a following "to".
CLAIM_AFTER_FIRST = frozenset(
    "system systems study studies paper papers work works measurement "
    "measurements benchmark benchmarks evaluation evaluations analysis analyses "
    "report reports dataset datasets method methods approach approaches result "
    "results".split())

SIGNIFICANT_RE = re.compile(r"\bsignifican(?:t|tly|ce)\b", re.IGNORECASE)
# A named test, or a quoted p value, makes "significant" a statistical word.
NAMED_TEST_RE = re.compile(
    r"\b(mcnemar|sign test|t-test|wilcoxon|fisher|chi-squared|chi-square|"
    r"binomial|permutation test|bootstrap|mann-whitney|kolmogorov|anova|"
    r"p-value|p\s*[=<>])", re.IGNORECASE)

CONTRIBUTION_RE = re.compile(
    r"\b(?:our|its|main|key|primary|central|this paper's|the paper's)\s+"
    r"(?:[\w-]+\s+){0,2}contributions?\b"
    r"|\bcontributions?\s+of\s+(?:this|our|the)\s+(?:paper|work|study|round)\b"
    r"|\bwe\s+contribute\b", re.IGNORECASE)

# A glossary entry: a bold term first on its line, followed by a colon.
BOLD_DEF_RE = re.compile(r"^\s*(?:[-*+]\s+|>\s*)?\*\*([^*]{1,40}?)\*\*\s*:")

CITATION_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
CITATION_DEF_RE = re.compile(r"^\s*\[\^([^\]\s]+)\]:")

# Source mode. A `.src.md` file writes every number as {{num:<id>}}, so a bare
# numeral in its prose is a number nobody bound to numbers.md. These are what a
# numeral may still be: a cross-reference to a numbered part of the document, a
# four-digit year, an ordered-list marker, a citation mark, or a link target.
CROSS_REF_RE = re.compile(
    r"(?:section|sections|§|figure|figures|fig\.|table|tables|appendix|panel|"
    r"panels|rq|item|items|step|steps)\s*\d+(?:\.\d+)*", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s")
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
FOOTNOTE_MARK_RE = re.compile(r"\[\^[^\]\s]+\]")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# A numeral that stands on its own. A digit inside a word (sha256, RQ1, v4) is
# part of a name, not a number the next run would update.
NUMERAL_RE = re.compile(r"(?<![\w.])\d[\d.,]*")

HEADING_RE = re.compile(r"^##\s+(.*\S)\s*$")
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
FIGURE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
PLACEHOLDER_RE = re.compile(r"\[\[(.*?)\]\]")

PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|per cent|percent)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?:])\s+")


def headings(lines):
    """[(lineno, text)] for every level-two heading, in file order."""
    return [(i, m.group(1)) for i, line in enumerate(lines, 1)
            for m in [HEADING_RE.match(line)] if m]


def check_sections(found, lines):
    heads = headings(lines)
    pos = 0
    last_lineno, last_name = 1, None
    for name, wanted in REQUIRED_SECTIONS:
        hit = None
        for index in range(pos, len(heads)):
            if any(w in heads[index][1].lower() for w in wanted):
                hit = index
                break
        if hit is None:
            after = f" after {last_name}" if last_name else ""
            found.fail(last_lineno, "sections",
                       f"no level-two heading for {name}{after} (a heading containing "
                       + " or ".join(f"\"{w}\"" for w in wanted)
                       + "); the order is "
                       + ", ".join(n for n, _ in REQUIRED_SECTIONS))
            return
        pos = hit + 1
        last_lineno, last_name = heads[hit]


def section_span(lines, wanted):
    """(first, last) 1-based line numbers of the section whose level-two heading
    contains one of `wanted`, or None. The span excludes the heading itself."""
    heads = headings(lines)
    for index, (lineno, text) in enumerate(heads):
        if any(w in text.lower() for w in wanted):
            end = heads[index + 1][0] - 1 if index + 1 < len(heads) else len(lines)
            return (lineno + 1, end)
    return None


def check_figures(found, path, lines):
    base = Path(path).resolve().parent
    for i, line in enumerate(lines, 1):
        for target in FIGURE_RE.findall(line):
            target = target.split()[0].strip("<>")
            if "://" in target:
                found.fail(i, "figures", f"{target} is a URL; a figure is a relative path "
                                         "to a file committed beside the paper")
                continue
            resolved = base / target
            if not resolved.is_file():
                found.fail(i, "figures", f"{target} does not resolve to a file relative to "
                                         f"{base.name}/; the reader sees a broken image")
            elif resolved.stat().st_size == 0:
                found.fail(i, "figures", f"{target} is an empty file; the figure script did "
                                         "not write it")


PROVENANCE_PATTERNS = (
    (re.compile(r"\b(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,64}\b"), "a hash or commit id"),
    (re.compile(r"\b20\d\d-\d\d-\d\d\b"), "an ISO date"),
    (re.compile(r"\b\d{1,2}:\d\d(:\d\d)?\b"), "a clock time"),
    (re.compile(r"\bmy/[a-z]"), "a router prefix on a model name"),
    (re.compile(r":cloud\b"), "a deployment suffix on a model name"),
    (re.compile(r"-nonthink\b"), "a serving-variant name"),
    (re.compile(r"\b(IQ\d_[A-Z0-9]+|Q\d_[0-9A-Z]+|UD-IQ\d)\b"), "a quantisation code"),
)


def body_end(lines):
    """Last 1-based line of the body: everything before the reproducing section.
    The reproducing section and the appendix are where provenance belongs."""
    span = section_span(lines, ("reproduc",))
    return span[0] - 2 if span else len(lines)


def check_body_provenance(found, lines):
    """Hashes, dates, clock times and record identifiers read as machine output in
    the body. They belong in the reproducing section or a provenance appendix, and
    the body refers to them by role (the frozen limits file, the check version)."""
    end = body_end(lines)
    for i, line in enumerate(lines[:end], 1):
        if line.startswith("[^"):
            continue
        for pattern, what in PROVENANCE_PATTERNS:
            m = pattern.search(line)
            if m:
                found.fail(i, "body-provenance",
                           f"\"{m.group(0)}\" is {what} in the body; move it to the "
                           "reproducing section or a provenance appendix and refer to "
                           "it by role here")
                break


def check_body_code_span(found, lines):
    """A code span in sections 1 to 7 is a leak by definition. Whatever is
    inside it is the record's own vocabulary: a field name, an outcome value, a
    batch id, a repository path, a task id, a token like PREFIX-OK. The body has
    plain words for every one of them and the reproducing section keeps the raw
    form, so a backtick in the body is a sentence that stopped translating
    (950 v4 review, section 2, body leaks). The span runs to the reproducing
    section, the same span body-provenance reads."""
    end = body_end(lines)
    in_fence = False
    for i, line in enumerate(lines[:end], 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith("[^"):
            continue
        m = CODE_SPAN_RE.search(line)
        if m:
            span = m.group(0)
            found.fail(i, "body-code-span",
                       f"{span if len(span) <= 40 else span[:37] + '...'} is a code span in "
                       "the body; say it in plain words here and keep the raw form in the "
                       "reproducing section")


def check_repeated_hedge(found, lines, hedges=DEFAULT_HEDGES):
    """One caveat told more than twice reads as anxiety, not as care. A warning:
    which two tellings to keep is the writer's call, not the linter's."""
    text = "\n".join(mask(line) for line in lines).lower()
    for phrase in hedges:
        needle = phrase.lower()
        n = text.count(needle)
        if n <= HEDGE_LIMIT:
            continue
        first = next(i for i, line in enumerate(lines, 1)
                     if needle in mask(line).lower())
        found.warn(first, "repeated-hedge",
                   f"\"{phrase}\" appears {n} times; hedge once where it bites and once "
                   "in threats and limits, and delete the rest")


def check_placeholders(found, lines):
    hits = [(i, m.group(1)) for i, line in enumerate(lines, 1)
            for m in PLACEHOLDER_RE.finditer(line)]
    for number, (lineno, text) in enumerate(hits, 1):
        short = text if len(text) <= 70 else text[:67] + "..."
        found.warn(lineno, "placeholders",
                   f"placeholder {number} of {len(hits)}: [[{short}]]; a number that is "
                   "not yet available stays marked, it is never estimated")


def check_banned_words(found, lines):
    """The style guardrails: words that sell instead of showing."""
    for i, line in enumerate(lines, 1):
        masked = mask(line)

        m = PLAIN_BANNED_RE.search(masked)
        if m:
            found.fail(i, "banned-words",
                       f"\"{m.group(1)}\" sells the result; give the measurement instead "
                       "(measured, consistent with, replicates)")

        for m in FIRST_RE.finditer(masked):
            after = [w.lower().strip(",.;:)\"'") for w in m.group(1).split()]
            if after and after[0] in COUNTING_AFTER_FIRST:
                continue  # "the first round", a count and not a claim
            if "to" in after[:3] or any(w in CLAIM_AFTER_FIRST for w in after[:2]):
                found.fail(i, "banned-words",
                           "\"first\" as a claim of priority; say what was measured and "
                           "let the prior-work section place it")
                break

        for sentence in SENTENCE_SPLIT_RE.split(masked):
            m = SIGNIFICANT_RE.search(sentence)
            if m and not NAMED_TEST_RE.search(sentence):
                found.fail(i, "banned-words",
                           f"\"{m.group(0)}\" outside a named statistical test; name the "
                           "test and its p value, or say large, or delete the word")
                break

        m = CONTRIBUTION_RE.search(masked)
        if m:
            found.fail(i, "banned-words",
                       f"\"{m.group(0).strip()}\" describes the paper's own contribution; "
                       "the prior-work section's two lists are that statement")


def check_contributions_header(found, lines):
    for i, line in enumerate(lines, 1):
        if ANY_HEADING_RE.match(line) and "contribution" in line.lower():
            found.fail(i, "contributions-header",
                       "a contributions section; there is no contributions list, the two "
                       "flat lists of the prior-work section carry it")


def check_coinages(found, lines, coinages):
    """Capitalised internal names. Headings and sentence starts are not read: a
    capital there is grammar, and flagging it would teach nothing."""
    for i, line in enumerate(lines, 1):
        if ANY_HEADING_RE.match(line):
            continue
        masked = mask(line)
        for word in coinages:
            for m in re.finditer(r"\b" + re.escape(word) + r"\b", masked):
                before = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)?", "",
                                masked[:m.start()]).rstrip()
                if not before or before.endswith((".", "!", "?", ":")):
                    continue
                found.fail(i, "coinages",
                           f"\"{word}\" is a capitalised internal name; a capitalised "
                           "coinage reads as a product name, so lowercase it or replace "
                           "it with a plain description")
                break


def check_term_uses(found, lines):
    """A bold-defined term used fewer than three times elsewhere is a definition
    the paper did not need. A warning: the fix is a rewrite, not a typo."""
    masked = [mask(line) for line in lines]
    for i, line in enumerate(lines, 1):
        m = BOLD_DEF_RE.match(line)
        if not m:
            continue
        term = m.group(1).strip()
        pattern = re.compile(r"\b" + re.escape(term) + r"s?\b", re.IGNORECASE)
        uses = sum(len(pattern.findall(text)) for j, text in enumerate(masked, 1) if j != i)
        if uses < 3:
            found.warn(i, "term-uses",
                       f"\"{term}\" is defined here and used {uses} times elsewhere; a "
                       "term used fewer than three times never needed a definition, "
                       "describe it in plain words where it appears")


def check_prior_work(found, lines):
    if section_span(lines, ("prior work",)) is None:
        found.fail(1, "prior-work",
                   "no level-two heading containing \"prior work\"; a paper says which of "
                   "its questions are already answered, in two flat lists, one of what is "
                   "established and one of what looks less examined with its kill-check")


def check_references(found, lines):
    """Citations are markdown footnote marks: `[^key]` in the text, `[^key]: ...`
    in the reference list. Both directions must close."""
    defs, marks = {}, {}
    for i, line in enumerate(lines, 1):
        masked = mask(line)
        m = CITATION_DEF_RE.match(masked)
        if m:
            defs.setdefault(m.group(1), i)
            continue
        for m in CITATION_RE.finditer(masked):
            marks.setdefault(m.group(1), i)

    if not defs:
        found.fail(1, "references",
                   "no reference list; the paper carries ten to fifteen entries written "
                   "`[^key]: author, title, year, link`, cited in the text as `[^key]`")
        return
    for key, lineno in marks.items():
        if key not in defs:
            found.fail(lineno, "references",
                       f"the citation `[^{key}]` has no entry in the reference list")
    for key, lineno in defs.items():
        if key not in marks:
            found.fail(lineno, "references",
                       f"the reference `[^{key}]` is never cited; an entry nobody cites "
                       "is a reading list, not a reference list")


def check_terms(found, lines, terms):
    span = section_span(lines, ("terms",))
    if span is None:
        return  # sections already reports the missing section
    first, last = span
    for term in terms:
        pattern = re.compile(r"\b" + re.escape(term) + r"s?\b", re.IGNORECASE)
        seen = next((i for i, line in enumerate(lines, 1) if pattern.search(line)), None)
        if seen is None:
            found.fail(first, "terms", f"\"{term}\" is on the terms list but the paper "
                                       "never uses it")
        elif seen < first or seen > last:
            found.fail(seen, "terms", f"\"{term}\" is first used here, outside the terms "
                                      f"section (lines {first} to {last}); every invented "
                                      "term is defined once before its first other use")


def check_counts(found, lines):
    for i, line in enumerate(lines, 1):
        if ANY_HEADING_RE.match(line):
            continue
        for sentence in SENTENCE_SPLIT_RE.split(mask(line)):
            m = PERCENT_RE.search(sentence)
            if m and not re.search(r"\bof\b", sentence):
                found.warn(i, "counts", f"the percentage \"{m.group(0).strip()}\" has no "
                                        "\"of\" count in its sentence; rates come with "
                                        "their counts (35 of 40, not 87.5%)")


def blank(pattern, text):
    """Blank out every match, keeping the line length so columns survive."""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def check_bare_numbers(found, lines, names=DEFAULT_NAMES):
    """Source mode: a numeral in prose that is not a token is a number the next
    run will not update. A model's display name is not one of them."""
    name_re = re.compile("|".join(re.escape(n) for n in names)) if names else None
    in_fence = False
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or ANY_HEADING_RE.match(line) or line.lstrip().startswith("|"):
            continue  # a table row carries numbers by design
        if CITATION_DEF_RE.match(line):
            continue  # a reference entry carries its year and its pages
        text = mask(line)
        patterns = [TOKEN_RE, LINK_TARGET_RE, FOOTNOTE_MARK_RE, CROSS_REF_RE,
                    YEAR_RE, LIST_MARKER_RE]
        if name_re is not None:
            patterns.append(name_re)
        for pattern in patterns:
            text = blank(pattern, text)
        m = NUMERAL_RE.search(text)
        if m:
            found.fail(i, "bare-number",
                       f"\"{m.group(0).rstrip('.,')}\" is a bare number; write it as "
                       "{{num:<id>}} against a row of numbers.md, or move it into a "
                       "table row, so a larger run updates it by re-rendering")


def check_unused_numbers(found, lines, numbers_path):
    """Source mode: an id nobody spends is a number the paper stopped quoting."""
    try:
        rows = parse_numbers(Path(numbers_path).read_text())
    except ValueError as exc:
        found.fail(1, "unused-number", f"{numbers_path}: {exc}")
        return
    used = {m.group(1) for line in lines for m in TOKEN_RE.finditer(line)}
    for name in rows:
        if name not in used:
            found.warn(1, "unused-number",
                       f"no token uses the id \"{name}\" of {numbers_path}; either the "
                       "paper stopped quoting that number or the token is misspelled")


def blank_tokens(lines):
    """The same lines with every {{num:<id>}} blanked, length preserved.

    An id is a name for a number, not prose: `runs-per-arm-in-rq2` in the source
    reads as "arm" to a word scan, and the reader never sees it, because the
    render replaces the token with the number. The term checks therefore read a
    source with its tokens blanked, and the rendered paper with its numbers in.
    """
    return [blank(TOKEN_RE, line) for line in lines]


def lint(path, terms=DEFAULT_TERMS, coinages=DEFAULT_COINAGES, numbers=None,
         names=DEFAULT_NAMES, hedges=DEFAULT_HEDGES, summary=False):
    """Return (failure lines, warning lines) for one paper, or for its summary."""
    _, lines = read_lines(path)
    found = Findings(path)
    words = blank_tokens(lines) if str(path).endswith(".src.md") else lines

    if not summary:
        check_sections(found, lines)
    check_figures(found, path, lines)
    check_em_dash(found, lines)
    check_moral_adjective(found, lines, MORAL_WORDS)
    check_banned_words(found, lines)
    if not summary:
        check_contributions_header(found, lines)
    check_coinages(found, lines, coinages)
    check_private_address(found, lines)
    check_body_provenance(found, lines)
    check_body_code_span(found, lines)
    check_placeholders(found, lines)
    check_repeated_hedge(found, words, hedges)
    check_terms(found, words, terms)
    check_term_uses(found, words)
    if not summary:
        check_prior_work(found, lines)
        check_references(found, lines)
    check_counts(found, lines)

    if str(path).endswith(".src.md"):
        check_bare_numbers(found, lines, names)
        numbers_path = numbers or Path(path).resolve().parent / "numbers.md"
        if not summary and (numbers is not None or Path(numbers_path).is_file()):
            check_unused_numbers(found, lines, numbers_path)

    return found.failures, found.warnings


USAGE = ("usage: lint.py [--terms a,b,c] [--coinages A,B] "
         "[--names 'Qwen 3.6 27B,GLM 5.3 Flash'] [--hedges 'a direction and not'] "
         "[--numbers numbers.md] [--summary] <paper.md>")


def take_value(args, flag):
    """(remaining args, the flag's value or None); () when the flag has no value."""
    if flag not in args:
        return args, None
    at = args.index(flag)
    if at + 1 >= len(args):
        return args, ()
    return args[:at] + args[at + 2:], args[at + 1]


def take_list(args, flag):
    """(remaining args, the flag's comma list or None). The flag is accepted
    before or after the path: a caller writing the paper reaches for
    `lint.py paper.md --terms a,b` as readily as the other order, and
    rejecting one of them teaches nothing."""
    if flag not in args:
        return args, None
    at = args.index(flag)
    if at + 1 >= len(args):
        return args, ()
    value = tuple(t.strip() for t in args[at + 1].split(",") if t.strip())
    return args[:at] + args[at + 2:], value


def main(argv):
    args = argv[1:]
    args, terms = take_list(args, "--terms")
    args, coinages = take_list(args, "--coinages")
    args, names = take_list(args, "--names")
    args, hedges = take_list(args, "--hedges")
    args, numbers = take_value(args, "--numbers")
    summary = "--summary" in args
    args = [a for a in args if a != "--summary"]
    if terms == () or coinages == () or names == () or hedges == () or numbers == ():
        print(USAGE, file=sys.stderr)
        return 2
    terms = DEFAULT_TERMS if terms is None else terms
    coinages = DEFAULT_COINAGES if coinages is None else coinages
    names = DEFAULT_NAMES if names is None else names
    hedges = DEFAULT_HEDGES if hedges is None else hedges
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    path = args[0]
    try:
        failures, warnings = lint(path, terms, coinages, numbers, names, hedges,
                                  summary)
    except OSError as exc:
        print(f"lint.py: {exc}", file=sys.stderr)
        return 2
    return emit(failures, warnings, SKILL)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
