"""Loader for input_plans_transport.md — the authoritative inventory of Irish
transport policies, strategies and codes of practice.

The first markdown table is the master inventory (5 columns, row N = policy
#N, in order). Later tables whose header starts with `#` list each policy's
official URL(s). Everything else in the file (prose, `[image]` lines, `+N`
lines left over from the export) is ignored.

Like documents.py, a malformed row here is process-fatal: policy_id is a
permanent public identifier, so a mis-parse must stop the run, not publish.
"""
import re
from pathlib import Path

from lib.body_refs import slugify

POLICIES_PATH = Path(__file__).parent / "input_plans_transport.md"

# Policy numbers (row order in the master table) that are codes of practice.
# Cross-checked against the title so a reordered table fails loudly.
CODE_OF_PRACTICE_NUMBERS = frozenset({20, 21})
CODE_OF_PRACTICE_PREFIX = "Code of Practice"

_MASTER_COLUMNS = 5
_URL_COLUMNS = 3
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_ESCAPE_RE = re.compile(r"\\(.)")
_TRAILING_DIGITS_RE = re.compile(r"\d+$")


def _tables(lines, path):
    """Group consecutive `|` lines into tables of (lineno, cells); separator
    rows (`| --- |`) are dropped, so each table starts with its header row."""
    tables, current = [], []
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line.startswith("|"):
            if current:
                tables.append(current)
                current = []
            continue
        if len(line) < 2 or not line.endswith("|"):
            raise ValueError(f"{path}:{lineno}: malformed table row {line!r}")
        cells = [c.strip() for c in line[1:-1].split("|")]
        if all(_SEPARATOR_CELL_RE.match(c) for c in cells):
            continue
        current.append((lineno, cells))
    if current:
        tables.append(current)
    return tables


def _clean(cell):
    """Drop markdown bold/italic markers and backslash escapes (`\\<`, `\\)`)."""
    return _ESCAPE_RE.sub(r"\1", cell.replace("*", "")).strip()


def strip_footnote(text):
    """Remove the citation-footnote number the export glued onto the end of a
    linkages cell (`CAF)1`, `Strategy27`, and `Ireland 20406` = 2040 + note 6).

    A bare 4-digit tail is a year and is kept; a 1-2 digit tail is a footnote
    only when glued to the previous character (`Strategy 12` is kept).
    Anything else is ambiguous and fatal rather than guessed.
    """
    m = _TRAILING_DIGITS_RE.search(text)
    if m is None:
        return text
    run = m.group()
    if len(run) == 4:
        return text
    if 5 <= len(run) <= 6 and run[:2] in ("19", "20"):
        return text[:m.start() + 4]
    if len(run) <= 2:
        glued = m.start() > 0 and not text[m.start() - 1].isspace()
        return text[:m.start()].rstrip() if glued else text
    raise ValueError(f"ambiguous trailing digits {run!r} in {text!r}")


def load_policies(path=POLICIES_PATH) -> list:
    """Parse and validate the inventory. Raises ValueError on any violation."""
    path = Path(path)
    tables = _tables(path.read_text(encoding="utf-8").splitlines(), path)
    if not tables:
        raise ValueError(f"{path} contains no tables")

    (_, header), *master_rows = tables[0]
    if len(header) != _MASTER_COLUMNS:
        raise ValueError(
            f"{path}: first table must have {_MASTER_COLUMNS} columns, got {len(header)}")
    if not master_rows:
        raise ValueError(f"{path}: first table has no policy rows")

    urls = {}
    for table in tables[1:]:
        (_, url_header), *url_rows = table
        if url_header[0] != "#":
            continue
        for lineno, cells in url_rows:
            where = f"{path}:{lineno}"
            if len(cells) != _URL_COLUMNS:
                raise ValueError(
                    f"{where}: URL row has {len(cells)} cell(s), expected {_URL_COLUMNS}")
            if not cells[0].isdigit():
                raise ValueError(f"{where}: policy number {cells[0]!r} is not an integer")
            number = int(cells[0])
            if number in urls:
                raise ValueError(f"{where}: duplicate policy number {number}")
            urls[number] = [url for _, url in _LINK_RE.findall(cells[2])]

    expected = set(range(1, len(master_rows) + 1))
    if set(urls) != expected:
        raise ValueError(
            f"{path}: master table has {len(master_rows)} policies but the URL tables "
            f"disagree on numbers {sorted(set(urls) ^ expected)}")

    records, seen = [], set()
    for number, (lineno, cells) in enumerate(master_rows, start=1):
        where = f"{path}:{lineno}"
        if len(cells) != _MASTER_COLUMNS:
            raise ValueError(
                f"{where}: policy row has {len(cells)} cell(s), expected {_MASTER_COLUMNS}")
        title, authority, horizon, scope, linkages = (_clean(c) for c in cells)
        if not all((title, authority, horizon, scope, linkages)):
            raise ValueError(f"{where}: policy row has an empty cell")
        linkages = strip_footnote(linkages)

        is_code = title.startswith(CODE_OF_PRACTICE_PREFIX)
        if is_code != (number in CODE_OF_PRACTICE_NUMBERS):
            raise ValueError(
                f"{where}: policy #{number} {title!r} disagrees with CODE_OF_PRACTICE_NUMBERS")

        policy_id = slugify(title)
        if policy_id in seen:
            raise ValueError(f"{where}: duplicate policy_id {policy_id!r}")
        seen.add(policy_id)

        records.append({
            "policy_id": policy_id,
            "number": number,
            "title": title,
            "kind": "code-of-practice" if is_code else "policy",
            "issuing_authority": authority,
            "horizon": horizon,
            "scope": scope,
            "linkages": linkages,
            "source_urls": urls[number],
        })
    return records
