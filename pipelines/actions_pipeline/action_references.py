"""Reading the reference a plan prints for an action.

A plan identifies its actions either by an ordinal (`12`) or by a code that
embeds the chapter, the delivery year and a number (`EL/23/6`, with optional
sub-action letter `EL/23/6/A` or `EL/23/10A`). That printed reference is the
published identity of the action, so reading it is a named, tested transform
rather than an incidental regex, and it fails closed: a reference that cannot
be read confidently is rejected with a typed error, never repaired.

Recognised flags (`*`, `**`, `(TF)`) are printed on the reference by the
Climate Action Plan annexes. They are not part of identity: they are stripped
here and reported separately, and the reference as printed is kept too.
"""
import re
from dataclasses import dataclass

# Closed set, reported in this order whatever order the annex printed them.
FLAG_ORDER = ("non_reportable", "duplicate", "taskforce")

_FLAG_TOKENS = (
    (re.compile(r"\(\s*TF\s*\)\s*$"), "taskforce"),
    (re.compile(r"\*\*\s*$"), "duplicate"),
    (re.compile(r"\*\s*$"), "non_reportable"),
)
_CHARSET_RE = re.compile(r"^[A-Za-z0-9/]+$")
_ORDINAL_RE = re.compile(r"^\d{1,3}$")
_CODE_RE = re.compile(r"^[A-Z]{2}/(\d{2})/\d+(?:/[A-Z]|[A-Z])?$")
_SUB_ACTION_RE = re.compile(r"^([A-Z]{2}/\d{2}/\d+)(?:/[A-Z]|[A-Z])$")
_SLUG_YEAR_RE = re.compile(r"^climate-action-plan-(20\d{2})-annex-of-actions$")
_BEL = "\x07"


class InvalidReference(ValueError):
    """A reference that cannot be read. `error_type` is the errors.json type."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


@dataclass(frozen=True)
class ParsedReference:
    number: str        # identity: the reference with flags removed
    printed: str       # as printed, whitespace-normalised
    flags: list        # subset of FLAG_ORDER
    year: int | None   # delivery year embedded in a code; None for an ordinal


def parse_reference(cell) -> ParsedReference:
    text = " ".join(str(cell or "").replace(_BEL, " ").split())
    # A reference wrapped across lines in the text layer reads `EN/23/ 1*`.
    # References contain no spaces, so a space beside a `/` is a wrap.
    printed = re.sub(r"\s*/\s*", "/", text)

    core = printed
    found = set()
    while True:
        for pattern, flag in _FLAG_TOKENS:
            match = pattern.search(core)
            if match:
                found.add(flag)
                core = core[:match.start()].rstrip()
                break
        else:
            break
    flags = [flag for flag in FLAG_ORDER if flag in found]

    if not re.search(r"[A-Za-z0-9]", core):
        raise InvalidReference(
            "UnresolvedActionNumber",
            f"Action reference {text!r} carries no readable reference.")
    if not _CHARSET_RE.match(core) or "//" in core or core.endswith("/") or core.startswith("/"):
        raise InvalidReference(
            "InvalidActionReference",
            f"Action reference {text!r} is outside the permitted characters "
            f"(ASCII letters, digits and '/' with no empty segment) once "
            f"recognised flags are removed; excluded, never escaped.")
    if _ORDINAL_RE.match(core):
        number = str(int(core))
        return ParsedReference(number, number if not flags else printed, flags, None)
    code = _CODE_RE.match(core)
    if code:
        return ParsedReference(core, printed, flags, 2000 + int(code.group(1)))
    raise InvalidReference(
        "UnresolvedActionNumber",
        f"Action reference {text!r} is neither an ordinal nor a recognised "
        f"plan code; excluded.")


def parent_reference(number: str):
    """The parent of a sub-action: the reference with its trailing letter
    removed, whether the letter is its own segment or attached to the number."""
    match = _SUB_ACTION_RE.match(number or "")
    return match.group(1) if match else None


class InvalidEditionSlug(ValueError):
    """A plan carrying coded references whose slug does not name its edition.
    Process-fatal: the legacy check (D4) cannot run without the year."""


def edition_year(plan_slug: str) -> int:
    """The edition's year, from the slug pattern
    `climate-action-plan-<year>-annex-of-actions`. Any other slug raises
    `InvalidEditionSlug`, because guessing a year would silently mis-sort or
    mis-exclude actions."""
    match = _SLUG_YEAR_RE.match(plan_slug or "")
    if not match:
        raise InvalidEditionSlug(
            f"plan slug {plan_slug!r} does not match "
            f"'climate-action-plan-<year>-annex-of-actions', so its edition "
            f"year cannot be read; rename the document or extend the pattern")
    return int(match.group(1))
